#!/usr/bin/env bash
# Prepare WSL2 Ubuntu 24.04 for the plugin evals (plan E9.6, Task 1). Idempotent: run it again
# after a failure or to refresh the kit; finished steps are skipped.
#
#   bash evals/setup.sh [kit-branch]        # default branch: e9-evals
#
# It installs (sudo): git, bubblewrap and socat (the sandbox `claude plugin eval` runs Bash in),
# PHP 8.3 with the extensions Drupal needs, Composer, uv and Claude Code; then fills the cache
# the eval scaffolds copy from:
#
#   /opt/tribunedesk-evals/kit       clone of the kit (run the evals here) with .venv/bin/tdkit
#   /opt/tribunedesk-evals/docs      contract docs v3.4.1-draft (EVAL_TRIBUNEDESK_DOCS_DIR)
#   /opt/tribunedesk-evals/venvs     Python environment of the Django scaffolds
#   /opt/tribunedesk-evals/django-blog, django-blog-media, drupal
#
# The cache is outside $HOME on purpose: the eval sandbox cannot read the home directory, and
# the agent runs tdkit, Python and the scaffold venv from here. Python environments use the
# system /usr/bin/python3.12 for the same reason (uv's own Pythons live in $HOME).
set -euo pipefail

KIT_BRANCH="${1:-e9-evals}"
CACHE=/opt/tribunedesk-evals
CONTRACT=v3.4.1-draft
CLAUDE_VERSION=2.1.293
UV_VERSION=0.12.20
PY=/usr/bin/python3.12
KIT_REPO=https://github.com/Tribunedesk/tribunedesk-cms-kit

step() { printf '\n== %s\n' "$*"; }

step "System packages"
sudo apt-get update -qq
sudo apt-get install -y -qq git curl unzip bubblewrap socat sqlite3 python3.12-venv \
  php8.3-cli php8.3-sqlite3 php8.3-gd php8.3-xml php8.3-mbstring php8.3-curl php8.3-zip

step "uv $UV_VERSION (in /usr/local/bin, readable inside the sandbox)"
if [ "$(uv --version 2>/dev/null | cut -d' ' -f2)" != "$UV_VERSION" ]; then
  curl -LsSf "https://astral.sh/uv/$UV_VERSION/install.sh" \
    | sudo env UV_INSTALL_DIR=/usr/local/bin UV_NO_MODIFY_PATH=1 sh
fi

step "Composer"
if ! command -v composer >/dev/null; then
  tmp="$(mktemp -d)"
  curl -fsSL https://getcomposer.org/installer -o "$tmp/composer-setup.php"
  expected="$(curl -fsSL https://composer.github.io/installer.sig)"
  actual="$(php -r "echo hash_file('sha384', '$tmp/composer-setup.php');")"
  [ "$expected" = "$actual" ] || { echo "Composer installer signature mismatch" >&2; exit 1; }
  sudo php "$tmp/composer-setup.php" --quiet --install-dir=/usr/local/bin --filename=composer
  rm -rf "$tmp"
fi

step "Claude Code $CLAUDE_VERSION"
if [ "$(claude --version 2>/dev/null | cut -d' ' -f1)" != "$CLAUDE_VERSION" ]; then
  curl -fsSL https://claude.ai/install.sh | bash -s "$CLAUDE_VERSION"
fi

step "Cache $CACHE"
sudo mkdir -p "$CACHE"
sudo chown "$(id -u):$(id -g)" "$CACHE"
mkdir -p "$CACHE/docs" "$CACHE/venvs"

step "Kit ($KIT_BRANCH) and tdkit"
if [ ! -d "$CACHE/kit/.git" ]; then
  git clone -q "$KIT_REPO" "$CACHE/kit"
fi
git -C "$CACHE/kit" fetch -q origin
git -C "$CACHE/kit" checkout -q "$KIT_BRANCH"
git -C "$CACHE/kit" pull -q --ff-only
(cd "$CACHE/kit" && uv sync -q --frozen --python "$PY" --no-python-downloads)
"$CACHE/kit/.venv/bin/tdkit" --version

step "Contract docs $CONTRACT"
(cd "$CACHE" && "$CACHE/kit/.venv/bin/tdkit" docs --contract "$CONTRACT" \
  --dest "$CACHE/docs/cms-api@$CONTRACT")

step "Python environment of the Django scaffolds"
if [ ! -x "$CACHE/venvs/django/bin/python" ]; then
  uv venv -q --python "$PY" --no-python-downloads "$CACHE/venvs/django"
fi
uv pip install -q --python "$CACHE/venvs/django/bin/python" \
  "django~=5.2.0" "requests~=2.32" "pillow~=11.0"
DJ="$CACHE/venvs/django/bin/python"

step "Scaffold django-blog"
if [ ! -f "$CACHE/django-blog/manage.py" ]; then
  tmp="$(mktemp -d)"
  (
    cd "$tmp"
    "$DJ" -m django startproject blogsite .
    "$DJ" manage.py startapp blog
    cat >> blogsite/settings.py <<'EOF'

INSTALLED_APPS += ["blog"]
TIME_ZONE = "Europe/Warsaw"
EOF
    cat > blog/models.py <<'EOF'
from django.db import models
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
EOF
    cat > blog/admin.py <<'EOF'
from django.contrib import admin

from .models import Post


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ["title", "status", "published_at"]
    prepopulated_fields = {"slug": ["title"]}
EOF
    cat > blog/views.py <<'EOF'
from django.shortcuts import get_object_or_404, render

from .models import Post


def post_list(request):
    posts = Post.objects.filter(status=Post.PUBLISHED)
    return render(request, "blog/post_list.html", {"posts": posts})


def post_detail(request, slug):
    post = get_object_or_404(Post, slug=slug, status=Post.PUBLISHED)
    return render(request, "blog/post_detail.html", {"post": post})
EOF
    cat > blog/urls.py <<'EOF'
from django.urls import path

from . import views

app_name = "blog"
urlpatterns = [
    path("", views.post_list, name="post_list"),
    path("<slug:slug>/", views.post_detail, name="post_detail"),
]
EOF
    mkdir -p blog/templates/blog
    cat > blog/templates/blog/post_list.html <<'EOF'
<h1>Blog</h1>
<ul>{% for post in posts %}<li><a href="{{ post.get_absolute_url }}">{{ post.title }}</a></li>{% endfor %}</ul>
EOF
    cat > blog/templates/blog/post_detail.html <<'EOF'
<h1>{{ post.title }}</h1>
<p>{{ post.excerpt }}</p>
{{ post.body|safe }}
EOF
    cat > blog/tests.py <<'EOF'
from django.test import TestCase
from django.utils import timezone

from .models import Post


class PostTests(TestCase):
    def test_published_post_is_shown(self):
        Post.objects.create(
            title="Hello", slug="hello", body="<p>Hi</p>", status=Post.PUBLISHED,
            published_at=timezone.now(),
        )
        self.assertContains(self.client.get("/hello/"), "Hello")
EOF
    cat > blogsite/urls.py <<'EOF'
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("blog.urls")),
]
EOF
    cat > README.md <<'EOF'
# Blog

A small Django 5.2 blog on SQLite. Posts are written in the Django admin.

- Python environment: `.venv` (Django, requests and Pillow are installed).
- Run: `.venv/bin/python manage.py runserver`
- Tests: `.venv/bin/python manage.py test`
EOF
    cat > .gitignore <<'EOF'
__pycache__/
db.sqlite3
.venv
EOF
    "$DJ" manage.py makemigrations -v 0 blog
    "$DJ" manage.py migrate -v 0
  )
  mv "$tmp" "$CACHE/django-blog"
fi

step "Scaffold django-blog-media (photos-only)"
if [ ! -f "$CACHE/django-blog-media/manage.py" ]; then
  tmp="$(mktemp -d)"
  cp -a "$CACHE/django-blog/." "$tmp/"
  (
    cd "$tmp"
    "$DJ" manage.py startapp library
    cat >> blogsite/settings.py <<'EOF'

INSTALLED_APPS += ["library"]
MEDIA_ROOT = BASE_DIR / "media"
MEDIA_URL = "/media/"
EOF
    cat > library/models.py <<'EOF'
from django.db import models


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
EOF
    cat > library/admin.py <<'EOF'
from django.contrib import admin

from .models import Photo


@admin.register(Photo)
class PhotoAdmin(admin.ModelAdmin):
    list_display = ["title", "credit", "uploaded_at"]
EOF
    printf 'media/\n' >> .gitignore
    cat >> README.md <<'EOF'

The photo library is the `library` app (`Photo`); files go to `media/`.
EOF
    "$DJ" manage.py makemigrations -v 0 library
    "$DJ" manage.py migrate -v 0
  )
  mv "$tmp" "$CACHE/django-blog-media"
fi

step "Scaffold drupal (Drupal 11, standard profile, SQLite)"
if [ ! -f "$CACHE/drupal/web/sites/default/files/.ht.sqlite" ]; then
  rm -rf "$CACHE/drupal"
  composer create-project -q --no-interaction drupal/recommended-project:^11 "$CACHE/drupal"
  (
    cd "$CACHE/drupal"
    composer require -q --no-interaction drush/drush
    vendor/bin/drush site:install standard -y -q --site-name="Newsroom" \
      --db-url="sqlite://sites/default/files/.ht.sqlite"
    chmod u+w web/sites/default web/sites/default/settings.php
    cat >> web/sites/default/settings.php <<'EOF'

if (file_exists($app_root . '/' . $site_path . '/settings.local.php')) {
  include $app_root . '/' . $site_path . '/settings.local.php';
}
EOF
    cat > .gitignore <<'EOF'
/vendor/
/web/core/
/web/modules/contrib/
/web/themes/contrib/
/web/profiles/contrib/
/web/libraries/
/web/sites/*/files/
/web/sites/*/settings.local.php
EOF
    cat > README.md <<'EOF'
# Newsroom site

Drupal 11 (standard profile) on SQLite, built with Composer.

- Run: `php -S 127.0.0.1:8888 -t web web/.ht.router.php`
- Drush: `vendor/bin/drush`
- Local settings (not in git): `web/sites/default/settings.local.php`, included by `settings.php`.
EOF
  )
fi
# The scaffold hard-links vendor/ and web/core: read-only files keep a run from changing the cache.
find "$CACHE/drupal/vendor" "$CACHE/drupal/web/core" -type f -perm -u+w -exec chmod a-w {} +

step "Measure the Drupal scaffold (must stay under 120 s)"
work="$(mktemp -d)"
start=$(date +%s%N)
(cd "$work" && bash "$CACHE/kit/plugins/tribunedesk-integration/evals/drupal-l12/scaffold.sh")
end=$(date +%s%N)
echo "drupal-l12 scaffold: $(( (end - start) / 1000000 )) ms"
rm -rf "$work"

step "Done"
cat <<EOF
Next, once: run \`claude\` in this terminal and log in with your subscription, then /exit.
Evals run from $CACHE/kit, for example:
  cd $CACHE/kit && claude plugin eval plugins/tribunedesk-integration --scaffold \\
    --allow-tools Bash Write Edit --runs 1 --ablation none -j 1 --max-cost-usd 15 \\
    --case django-l12
EOF
