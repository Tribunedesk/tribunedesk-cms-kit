"""What a scenario works with: the running mock, sends, and the integration's commands."""

from __future__ import annotations

import copy
import json
import os
import re
import shutil
import tempfile
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from tdkit.check.commands import CommandError, run_template
from tdkit.docs import ContractDocs
from tdkit.mock import tls
from tdkit.mock.png import png
from tdkit.mock.state import DEFAULT_TOKEN, MockState, Recorded
from tdkit.sender import DeliveryResult, deliver
from tdkit.signing import MOCK_SECRET


def image_hosts_for(webhook: str | None) -> tuple[str, str]:
    """`(allowed, forbidden)` image hosts, both served by the mock on 127.0.0.1.

    A receiver without a token may download from the host of its own webhook (guide 1), so
    the forbidden host is never the webhook's host.
    """
    host = urlsplit(webhook).hostname if webhook else None
    if host == "localhost":
        return "localhost", "127.0.0.1"
    return "127.0.0.1", "localhost"


class Fail(Exception):
    """A scenario's condition did not hold; the message says what the integration did."""


@dataclass(frozen=True)
class CheckOptions:
    docs: ContractDocs
    inspect_cmd: str | None = None
    webhook: str | None = None
    secret: str | None = None
    publish_cmd: str | None = None
    poll_cmd: str | None = None
    social_flag: bool = False
    port: int = 8787
    # Level 4 (media library): the integration's sync and its library, as commands.
    sync_cmd: str | None = None
    media_inspect_cmd: str | None = None
    media_add_cmd: str | None = None
    media_edit_cmd: str | None = None
    media_delete_cmd: str | None = None
    reset_cmd: str | None = None
    backfill: bool = False
    media_fields: tuple[str, ...] = ("alt",)
    media_hosts: tuple[str, ...] = ()

    LEVEL4_COMMANDS = (
        "sync_cmd",
        "media_inspect_cmd",
        "media_add_cmd",
        "media_edit_cmd",
        "media_delete_cmd",
    )


class Context:
    def __init__(
        self, opts: CheckOptions, mode: str, state: MockState, port: int, tls_port: int = 0
    ) -> None:
        self.opts, self.mode, self.state, self.port = opts, mode, state, port
        self.tls_port = tls_port
        self.api_base = f"http://127.0.0.1:{port}"
        self.image_host, self.forbidden_image_host = image_hosts_for(opts.webhook)
        state.image_hosts = [self.image_host]
        self.secret = opts.secret or MOCK_SECRET
        self.started = time.monotonic()
        self._folder: Path | None = None

    def close(self) -> None:
        """Remove the files this check wrote for `--media-add-cmd`."""
        if self._folder is not None:
            shutil.rmtree(self._folder, ignore_errors=True)
            self._folder = None

    # -- articles --------------------------------------------------------------------------

    def article(self, *, minutes: int = 0, **fields: Any) -> dict[str, Any]:
        """A level 1 delivery body made from the tag's sample, with a new `article_id`.

        The body has no internal links, no AI label and no `backlink_sources`, so a level 3
        integration stores `html` as sent; its image is on an allowed host (the mock).
        """
        body = copy.deepcopy(self.opts.docs.sample_delivery)
        article_id = str(uuid.uuid4())
        image_url = f"{self.files_base(self.image_host)}/files/{article_id}.jpg"
        for image in [body.get("featured_image"), *(body.get("generated_images") or [])]:
            if isinstance(image, dict):
                image["url"] = image_url
        body.pop("backlink_sources", None)
        body.update(
            article_id=article_id,
            sent_at=self.sent_at(minutes),
            title=f"tdkit test article {article_id[:8]}",
            html=(
                f"<p>tdkit test article {article_id[:8]}.</p>\n"
                "<p>The city council approved the budget on Tuesday.</p>"
            ),
            excerpt="The city council approved the budget on Tuesday.",
            internal_links=[],
            ai_provenance=None,
        )
        body.update(fields)
        return body

    def files_base(self, host: str) -> str:
        """Files are served over https with the test certificate (D5), on the TLS port."""
        return f"https://{host}:{self.tls_port}"

    def sent_at(self, minutes: int = 0) -> str:
        moment = datetime.now(UTC) + timedelta(minutes=minutes)
        return moment.isoformat(timespec="seconds")

    # -- sends -----------------------------------------------------------------------------

    def send(
        self,
        body: dict[str, Any],
        *,
        delivery_id: str | None = None,
        attempt: int = 1,
        timestamp: int | None = None,
        secrets: list[str] | None = None,
    ) -> DeliveryResult:
        """One send of `body`: a webhook attempt, or in read mode a send plus `--poll-cmd`.

        In read mode the result is the last `POST /result` the integration made for it.
        """
        known = delivery_id is not None and any(
            s.delivery_id == delivery_id for s in self.state.sends.get(body["article_id"], [])
        )
        send = None if known else self.state.add_send(body, delivery_id=delivery_id)
        if self.mode == "read":
            target = send.delivery_id if send else delivery_id
            mark = len(self.state.results)
            self.poll()
            calls = [r for r in self.state.results[mark:] if r.delivery_id == target]
            if not calls:
                raise Fail("after --poll-cmd the integration reported no result for the send")
            last = calls[-1]
            if last.body.get("error"):
                raise Fail(f"the integration reported the send as failed: {last.body['error']!r}")
            return DeliveryResult(
                status=last.status,
                body=json.dumps(last.body).encode(),
                json=last.body,
                error=None,
            )
        assert self.opts.webhook is not None
        result = deliver(
            self.opts.webhook,
            json.dumps(body, ensure_ascii=False).encode("utf-8"),
            secrets=secrets or [self.secret],
            delivery_id=delivery_id or (send.delivery_id if send else str(uuid.uuid4())),
            attempt=attempt,
            timestamp=timestamp,
        )
        if result.status is not None and 200 <= result.status < 300:
            if send is not None:
                send.state = "delivered"
            answer = result.json or {}
            if isinstance(answer.get("permalink"), str) and answer["permalink"]:
                # A permalink in the answer is a link back, as in production (guide 2).
                exclude = answer.get("social_queue_exclude")
                self.state.record_link_back(
                    body["article_id"],
                    answer["permalink"],
                    published_at=None,
                    social_queue_exclude=exclude if isinstance(exclude, bool) else None,
                    source="answer",
                )
        return result

    def delivered(self, body: dict[str, Any], **kwargs: Any) -> DeliveryResult:
        """`send`, failing the scenario unless the integration answered 2xx."""
        result = self.send(body, **kwargs)
        if result.status is None:
            raise Fail(f"the webhook did not answer: {result.error}")
        if not 200 <= result.status < 300:
            raise Fail(f"the integration answered {result.status}: {_snippet(result.body)}")
        return result

    # -- the integration's commands --------------------------------------------------------

    def _env(self) -> dict[str, str]:
        return {
            **os.environ,
            "TD_API_BASE": self.api_base,
            "TD_CMS_TOKEN": DEFAULT_TOKEN,
            "TD_CA_BUNDLE": str(tls.CA_BUNDLE),
        }

    def inspect(self, article_id: str) -> dict[str, Any] | None:
        if not self.opts.inspect_cmd:
            raise Fail("this scenario needs --inspect-cmd")
        out = self._run(self.opts.inspect_cmd, "--inspect-cmd", article_id)
        try:
            post = json.loads(out)
        except ValueError as exc:
            raise Fail(f"--inspect-cmd printed something that is not JSON: {out[:200]!r}") from exc
        if post is not None and not isinstance(post, dict):
            raise Fail("--inspect-cmd must print a JSON object or null")
        return post

    def must_inspect(self, article_id: str) -> dict[str, Any]:
        post = self.inspect(article_id)
        if post is None:
            raise Fail("--inspect-cmd found no post for the article")
        return post

    def publish(self, article_id: str) -> None:
        if not self.opts.publish_cmd:
            raise Fail("this scenario needs --publish-cmd")
        self._run(self.opts.publish_cmd, "--publish-cmd", article_id)

    def poll(self) -> None:
        if not self.opts.poll_cmd:
            raise Fail("read mode needs --poll-cmd")
        self._run(self.opts.poll_cmd, "--poll-cmd", "")

    def _run(self, template: str, name: str, article_id: str, **values: str) -> str:
        try:
            return run_template(template, env=self._env(), article_id=article_id, **values)
        except CommandError as exc:
            raise Fail(f"{name} failed: {exc}") from exc

    # -- level 4 ---------------------------------------------------------------------------

    @property
    def field(self) -> str:
        """The field level 4 scenarios edit (`--media-fields`, default `alt`)."""
        return self.opts.media_fields[0]

    def _media_cmd(self, name: str) -> str:
        template = getattr(self.opts, name)
        if not template:
            raise Fail(f"level 4 needs --{name.removesuffix('_cmd').replace('_', '-')}-cmd")
        return str(template)

    def sync(self) -> None:
        self._run(self._media_cmd("sync_cmd"), "--sync-cmd", "")

    def reset(self) -> None:
        if self.opts.reset_cmd:
            self._run(self.opts.reset_cmd, "--reset-cmd", "")

    def media_inspect(self, cms_media_id: str) -> dict[str, Any] | None:
        out = self._run(
            self._media_cmd("media_inspect_cmd"),
            "--media-inspect-cmd",
            "",
            cms_media_id=cms_media_id,
        )
        try:
            item = json.loads(out)
        except ValueError as exc:
            raise Fail(
                f"--media-inspect-cmd printed something that is not JSON: {out[:200]!r}"
            ) from exc
        if item is not None and not isinstance(item, dict):
            raise Fail("--media-inspect-cmd must print a JSON object or null")
        return item

    def must_media(self, cms_media_id: str) -> dict[str, Any]:
        item = self.media_inspect(cms_media_id)
        if item is None:
            raise Fail(f"--media-inspect-cmd found no file {cms_media_id!r}")
        return item

    def media_add(self) -> str:
        """Add a 1200x800 PNG to the CMS's library as an editor would; its `cms_media_id`."""
        if self._folder is None:
            self._folder = Path(tempfile.mkdtemp(prefix="tdkit-"))
        path = self._folder / f"tdkit-{uuid.uuid4().hex[:8]}.png"
        path.write_bytes(png(1200, 800, (40, 90, 160)))
        out = self._run(self._media_cmd("media_add_cmd"), "--media-add-cmd", "", file=str(path))
        try:
            answer = json.loads(out)
        except ValueError as exc:
            raise Fail(
                f"--media-add-cmd printed something that is not JSON: {out[:200]!r}"
            ) from exc
        cms_media_id = answer.get("cms_media_id") if isinstance(answer, dict) else None
        if not isinstance(cms_media_id, str) or not cms_media_id:
            raise Fail('--media-add-cmd must print {"cms_media_id": "…"}')
        return cms_media_id

    def media_edit(self, cms_media_id: str, field: str, value: str) -> None:
        self._run(
            self._media_cmd("media_edit_cmd"),
            "--media-edit-cmd",
            "",
            cms_media_id=cms_media_id,
            field=field,
            value=value,
        )

    def media_delete(self, cms_media_id: str) -> None:
        self._run(
            self._media_cmd("media_delete_cmd"),
            "--media-delete-cmd",
            "",
            cms_media_id=cms_media_id,
        )

    def mark(self) -> int:
        return len(self.state.requests)

    def requests_since(self, mark: int, method: str, path: str) -> list[Recorded]:
        """Requests the integration made after `mark` whose path matches regex `path`."""
        return [
            r
            for r in self.state.requests[mark:]
            if r.method == method and re.fullmatch(path, r.path)
        ]


def _snippet(raw: bytes) -> str:
    text = raw.decode("utf-8", errors="replace").strip()
    return text[:200] if text else "(empty body)"
