"""Run one scenario of the Claude Code plugin on this machine and check what it built.

    uv run python evals/run.py django-l12 [--max-budget-usd 15]

The runner builds the scenario's project in a new folder under the system temp directory,
starts `claude -p` there with only this plugin (no user settings, hooks or CLAUDE.md), and
then runs the scenario's checks: did the skill fire, did `tdkit check` run and pass, is the
manifest right, is no signing secret in a file git would commit. What a person has to judge
(the conversation, the message for Tribune Desk) is listed under "Review" in
`evals/scenarios/<name>.md`; the runner prints those files for that review.

The agent runs Bash with the user's rights, outside any sandbox: run only these scenarios.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

KIT = Path(__file__).resolve().parents[1]
PLUGIN = KIT / "plugins" / "tribunedesk-integration"
SCENARIOS = KIT / "evals" / "scenarios"
TOOLS = ["Bash", "Write", "Edit", "Read", "Glob", "Grep", "Skill", "TodoWrite"]
SECRET = re.compile(r"whsec_[A-Za-z0-9+/=]{20,}")
TDKIT = r"[Tt][Dd][Kk][Ii][Tt]\S*"


# -- the run's record ---------------------------------------------------------------------


@dataclass
class Run:
    workspace: Path
    events: list[dict[str, Any]]

    def tool_calls(self, name: str) -> list[dict[str, Any]]:
        calls = []
        for event in self.events:
            if event.get("type") != "assistant":
                continue
            for block in event.get("message", {}).get("content", []):
                if block.get("type") == "tool_use" and block.get("name") == name:
                    calls.append(block.get("input", {}))
        return calls

    def bash(self, pattern: str) -> list[str]:
        return [
            c.get("command", "")
            for c in self.tool_calls("Bash")
            if re.search(pattern, c.get("command", ""))
        ]

    @property
    def result(self) -> dict[str, Any]:
        return next((e for e in reversed(self.events) if e.get("type") == "result"), {})

    def text(self, path: str) -> str | None:
        file = self.workspace / path
        return file.read_text(encoding="utf-8") if file.is_file() else None


Check = Callable[[Run], tuple[bool, str]]


def skill_fired(run: Run) -> tuple[bool, str]:
    names = [c.get("skill", "") for c in run.tool_calls("Skill")]
    return any("tribunedesk-integration" in n for n in names), f"Skill calls: {names}"


def final_message_complete(run: Run) -> tuple[bool, str]:
    """The last message stands alone (SKILL.md, "The last message of a turn"): the stages with
    their results (5+ stage numbers), the plan as built (3+ file paths) and the welcome's promise
    that nothing was ordered or deployed."""
    text = run.result.get("result", "") or ""
    stages = set(re.findall(r"(?i)(?:etap\w*|stage)\s*([0-7])", text))
    stages |= set(re.findall(r"(?m)^\|\s*([0-7])\.", text))
    files = set(re.findall(r"[\w/.-]+\.(?:py|php|md|json|example)(?!\w)", text))
    promise = re.search(r"(?i)deploy|wdra[żz]|produkc|production", text) is not None
    ok = len(stages) >= 5 and len(files) >= 3 and promise
    return ok, f"stages {sorted(stages)}, {len(files)} file(s), deploy/production named: {promise}"


def welcome_in_final(run: Run) -> tuple[bool, str]:
    """Section 1: no tokens ordered for the user, nothing deployed."""
    text = run.result.get("result", "") or ""
    tokens = re.search(r"(?i)token", text) is not None
    deploy = re.search(r"(?i)deploy|wdra[żz]|produkc|production", text) is not None
    return tokens and deploy, f"tokens named: {tokens}, deploy/production named: {deploy}"


def ran(pattern: str, *, expected: bool = True) -> Check:
    def check(run: Run) -> tuple[bool, str]:
        found = run.bash(pattern)
        return bool(found) == expected, f"{len(found)} Bash call(s) match {pattern!r}"

    return check


def file_matches(path: str, pattern: str, *, expected: bool = True) -> Check:
    def check(run: Run) -> tuple[bool, str]:
        text = run.text(path)
        if text is None:
            return not expected, f"{path} does not exist"
        found = re.search(pattern, text) is not None
        return found == expected, f"{path} {'matches' if found else 'does not match'}"

    return check


def report_green(levels: list[int], mode: str) -> Check:
    """The report `tdkit check --json` wrote: these levels and mode, no failure, a pass."""

    def check(run: Run) -> tuple[bool, str]:
        text = run.text(".tribunedesk/tdkit-report.json")
        if text is None:
            return False, "no .tribunedesk/tdkit-report.json"
        report = json.loads(text)
        outcomes = [r.get("passed") for r in report.get("results", [])]
        ok = (
            str(report.get("tdkit", "")).startswith("1.")
            and report.get("levels") == levels
            and report.get("mode") == mode
            and True in outcomes
            and False not in outcomes
        )
        return ok, (
            f"tdkit {report.get('tdkit')}, levels {report.get('levels')}, mode "
            f"{report.get('mode')}, passed {outcomes.count(True)}, failed {outcomes.count(False)}"
        )

    return check


def manifest(**expected: Any) -> Check:
    def check(run: Run) -> tuple[bool, str]:
        text = run.text("tribunedesk.json")
        if text is None:
            return False, "no tribunedesk.json"
        data = json.loads(text)
        wrong = {}
        for key, value in expected.items():
            actual = data.get("conformance", {}).get("passed") if key == "passed" else data.get(key)
            if actual != value:
                wrong[key] = actual
        return not wrong, f"wrong: {wrong}" if wrong else "as expected"

    return check


def no_secret_in_git(run: Run) -> tuple[bool, str]:
    """No signing secret in a file that is committed or would be by `git add -A`.

    Test files are skipped: they carry the contract's public test vectors and the mock's
    secret, which are not secrets (first django-l12 run)."""
    files = _git(run.workspace, "ls-files", "--cached", "--others", "--exclude-standard")
    leaks = []
    for name in files.splitlines():
        path = run.workspace / name
        if any("test" in part.lower() for part in Path(name).parts):
            continue
        if path.is_file():
            try:
                if SECRET.search(path.read_text(encoding="utf-8")):
                    leaks.append(name)
            except UnicodeDecodeError:
                continue
    return not leaks, f"secret in {leaks}" if leaks else "none"


def env_ignored(run: Run) -> tuple[bool, str]:
    if not (run.workspace / ".env").exists():
        return True, "no .env"
    done = subprocess.run(["git", "check-ignore", "-q", ".env"], cwd=run.workspace, check=False)
    return done.returncode == 0, "ignored" if done.returncode == 0 else ".env is not ignored"


def _git(cwd: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", check=False
    )
    return done.stdout


# -- projects -----------------------------------------------------------------------------


def _write(root: Path, files: dict[str, str]) -> None:
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def _run(cwd: Path, *args: str) -> None:
    subprocess.run(list(args), cwd=cwd, check=True)


def django_blog(root: Path, *, photos: bool = False) -> None:
    uv = shutil.which("uv")
    assert uv, "uv is required"
    _run(root, uv, "venv", "-q", "--python", "3.12", ".venv")
    python = root / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    _run(root, uv, "pip", "install", "-q", "--python", str(python), "django~=5.2.0",
         "requests~=2.32", "pillow~=11.0")  # fmt: skip
    _run(root, str(python), "-m", "django", "startproject", "blogsite", ".")
    _run(root, str(python), "manage.py", "startapp", "blog")
    _write(root, DJANGO_FILES)
    settings = root / "blogsite" / "settings.py"
    extra = '\nINSTALLED_APPS += ["blog"]\nTIME_ZONE = "Europe/Warsaw"\n'
    if photos:
        _run(root, str(python), "manage.py", "startapp", "library")
        _write(root, PHOTO_FILES)
        extra += 'INSTALLED_APPS += ["library"]\nMEDIA_ROOT = BASE_DIR / "media"\nMEDIA_URL = "/media/"\n'
        with (root / ".gitignore").open("a", encoding="utf-8") as ignore:
            ignore.write("media/\n")
        with (root / "README.md").open("a", encoding="utf-8") as readme:
            readme.write(
                "\nThe photo library is the `library` app (`Photo`); files go to `media/`.\n"
            )
    settings.write_text(settings.read_text(encoding="utf-8") + extra, encoding="utf-8")
    _run(root, str(python), "manage.py", "makemigrations", "-v", "0")
    _run(root, str(python), "manage.py", "migrate", "-v", "0")


def intranet(root: Path) -> None:
    django_blog(root)
    with (root / "README.md").open("a", encoding="utf-8") as readme:
        readme.write(
            "\n## Deployment\n\nProduction runs on the newsroom intranet behind the company "
            "firewall. Nothing on the internet can reach it; it may call out over https.\n"
        )


def ghost(root: Path) -> None:
    _write(
        root,
        {
            "README.md": "# Newsroom site\n\nOur site runs on Ghost(Pro), the hosted Ghost "
            "service: we manage it in Ghost Admin and cannot run our own code or plugins on its "
            "servers. Theme and content are edited in Ghost Admin.\n"
        },
    )


def commit(root: Path, message: str) -> None:
    _run(root, "git", "init", "-q")
    _run(root, "git", "config", "user.name", "Eval Developer")
    _run(root, "git", "config", "user.email", "developer@example.com")
    _run(root, "git", "add", "-A")
    _run(root, "git", "commit", "-qm", message)


@dataclass(frozen=True)
class Scenario:
    build: Callable[[Path], None]
    checks: dict[str, Check]
    review_files: tuple[str, ...] = ("tribunedesk-request.md",)


WEBHOOK_L12: dict[str, Check] = {
    "skill fired": skill_fired,
    "final message stands alone": final_message_complete,
    "tdkit check ran": ran(rf"{TDKIT} check"),
    "report green (1,2 webhook)": report_green([1, 2], "webhook"),
    "manifest": manifest(contract="3.4.1-draft", levels=[1, 2], delivery="webhook", passed=[1, 2]),
    "no secret in git": no_secret_in_git,
    ".env ignored": env_ignored,
}

SCENARIO: dict[str, Scenario] = {
    "django-l12": Scenario(django_blog, WEBHOOK_L12),
    "photos-only": Scenario(
        lambda root: django_blog(root, photos=True),
        {
            "skill fired": skill_fired,
            "final message stands alone": final_message_complete,
            "manifest written by tdkit": ran(rf"{TDKIT} manifest write"),
            "no tdkit check": ran(rf"{TDKIT} check", expected=False),
            "manifest (4, none, no conformance)": manifest(
                levels=[4], delivery="none", passed=None
            ),
            "no webhook route": file_matches("blogsite/urls.py", r"(?i)webhook", expected=False),
            "no secret in git": no_secret_in_git,
            ".env ignored": env_ignored,
        },
    ),
    "no-public-endpoint": Scenario(
        intranet,
        {
            "skill fired": skill_fired,
            "final message stands alone": final_message_complete,
            "tdkit check in read mode": ran(rf"{TDKIT} check[^\n]*--mode read"),
            "report green (1 read)": report_green([1], "read"),
            "manifest": manifest(levels=[1], delivery="read", passed=[1]),
            "no secret in git": no_secret_in_git,
            ".env ignored": env_ignored,
        },
    ),
    "ghost": Scenario(
        ghost,
        {
            "skill fired": skill_fired,
            "no code written": lambda run: (not run.tool_calls("Write"), "Write calls"),
            "welcome in the final message": welcome_in_final,
        },
        review_files=(),
    ),
}


# -- running ------------------------------------------------------------------------------


def prompt_of(name: str) -> str:
    text = (SCENARIOS / f"{name}.md").read_text(encoding="utf-8")
    return text.split("## Prompt\n", 1)[1].split("\n## ", 1)[0].strip()


def run_claude(workspace: Path, prompt: str, transcript: Path, budget: float) -> list[dict]:
    claude = shutil.which("claude")
    assert claude, "claude is required"
    uv = shutil.which("uv")
    assert uv, "uv is required"
    tdkit = f'"{Path(uv).as_posix()}" run --project "{KIT.as_posix()}" tdkit'
    env = {**os.environ, "TDKIT_CMD": tdkit}
    command = [
        claude, "-p", prompt,
        "--setting-sources", "local",
        "--plugin-dir", str(PLUGIN),
        "--allowedTools", *TOOLS,
        "--max-turns", "200",
        "--max-budget-usd", str(budget),
        "--no-session-persistence",
        "--output-format", "stream-json", "--verbose",
    ]  # fmt: skip
    events = []
    with transcript.open("w", encoding="utf-8") as out:
        process = subprocess.Popen(
            command, cwd=workspace, env=env, stdout=subprocess.PIPE, text=True, encoding="utf-8"
        )
        assert process.stdout is not None
        for line in process.stdout:
            out.write(line)
            try:
                event = json.loads(line)
            except ValueError:
                continue
            events.append(event)
            _progress(event)
        process.wait()
    return events


def _progress(event: dict[str, Any]) -> None:
    if event.get("type") != "assistant":
        return
    for block in event.get("message", {}).get("content", []):
        if block.get("type") == "tool_use":
            detail = block["input"].get("command") or block["input"].get("file_path") or ""
            print(f"  [{block['name']}] {str(detail)[:110]}", flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("scenario", choices=sorted(SCENARIO))
    parser.add_argument("--max-budget-usd", type=float, default=15.0)
    args = parser.parse_args(argv)
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")  # Polish text in a redirected log
    scenario = SCENARIO[args.scenario]

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base = Path(tempfile.gettempdir()) / "tribunedesk-evals" / f"{args.scenario}-{stamp}"
    workspace = base / "project"
    workspace.mkdir(parents=True)
    print(f"Project: {workspace}", flush=True)
    scenario.build(workspace)
    commit(workspace, "Project before the integration")

    events = run_claude(
        workspace, prompt_of(args.scenario), base / "transcript.jsonl", args.max_budget_usd
    )
    run = Run(workspace, events)
    result = run.result
    print(f"\nCost: {result.get('total_cost_usd')} USD, turns: {result.get('num_turns')}, "
          f"stop: {result.get('subtype')}")  # fmt: skip
    failed = 0
    for label, check in scenario.checks.items():
        ok, detail = check(run)
        failed += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {label}: {detail}")
    print(f"\nTranscript: {base / 'transcript.jsonl'}")
    for name in scenario.review_files:
        text = run.text(name)
        print(f"\n--- {name} ---\n{text if text is not None else '(missing)'}")
    print(f"\n--- final message ---\n{result.get('result', '')}")
    return 1 if failed else 0


DJANGO_FILES = {
    "blog/models.py": """from django.db import models
from django.urls import reverse


class Post(models.Model):
    DRAFT = "draft"
    PUBLISHED = "published"
    STATUS_CHOICES = [(DRAFT, "Draft"), (PUBLISHED, "Published")]

    title = models.CharField(max_length=300)
    slug = models.SlugField(max_length=300, unique=True)
    excerpt = models.TextField(blank=True)
    body = models.TextField(help_text="HTML")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=DRAFT)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-published_at"]

    def __str__(self) -> str:
        return self.title

    def get_absolute_url(self) -> str:
        return reverse("blog:post_detail", args=[self.slug])
""",
    "blog/admin.py": """from django.contrib import admin

from .models import Post


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ["title", "status", "published_at"]
    prepopulated_fields = {"slug": ["title"]}
""",
    "blog/views.py": """from django.shortcuts import get_object_or_404, render

from .models import Post


def post_list(request):
    posts = Post.objects.filter(status=Post.PUBLISHED)
    return render(request, "blog/post_list.html", {"posts": posts})


def post_detail(request, slug):
    post = get_object_or_404(Post, slug=slug, status=Post.PUBLISHED)
    return render(request, "blog/post_detail.html", {"post": post})
""",
    "blog/urls.py": """from django.urls import path

from . import views

app_name = "blog"
urlpatterns = [
    path("", views.post_list, name="post_list"),
    path("<slug:slug>/", views.post_detail, name="post_detail"),
]
""",
    "blog/templates/blog/post_list.html": "<h1>Blog</h1>\n<ul>{% for post in posts %}"
    '<li><a href="{{ post.get_absolute_url }}">{{ post.title }}</a></li>{% endfor %}</ul>\n',
    "blog/templates/blog/post_detail.html": "<h1>{{ post.title }}</h1>\n<p>{{ post.excerpt }}"
    "</p>\n{{ post.body|safe }}\n",
    "blog/tests.py": """from django.test import TestCase
from django.utils import timezone

from .models import Post


class PostTests(TestCase):
    def test_published_post_is_shown(self):
        Post.objects.create(
            title="Hello", slug="hello", body="<p>Hi</p>", status=Post.PUBLISHED,
            published_at=timezone.now(),
        )
        self.assertContains(self.client.get("/hello/"), "Hello")
""",
    "blogsite/urls.py": """from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("blog.urls")),
]
""",
    "README.md": """# Blog

A small Django 5.2 blog on SQLite. Posts are written in the Django admin.

- Python environment: `.venv` (Django, requests and Pillow are installed).
- Run: `.venv\\Scripts\\python manage.py runserver`
- Tests: `.venv\\Scripts\\python manage.py test`
""",
    ".gitignore": "__pycache__/\ndb.sqlite3\n.venv/\n",
}

PHOTO_FILES = {
    "library/models.py": '''from django.db import models


class Photo(models.Model):
    """The newsroom's photo library."""

    image = models.ImageField(upload_to="photos/%Y/%m/")
    title = models.CharField(max_length=300)
    alt = models.CharField(max_length=500, blank=True)
    caption = models.TextField(blank=True)
    credit = models.CharField(max_length=200, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.title
''',
    "library/admin.py": """from django.contrib import admin

from .models import Photo


@admin.register(Photo)
class PhotoAdmin(admin.ModelAdmin):
    list_display = ["title", "credit", "uploaded_at"]
""",
}


if __name__ == "__main__":
    sys.exit(main())
