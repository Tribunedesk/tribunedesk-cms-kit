"""What a scenario works with: the running mock, sends, and the integration's commands."""

from __future__ import annotations

import copy
import json
import os
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from tdkit.check.commands import CommandError, run_template
from tdkit.docs import ContractDocs
from tdkit.mock.state import DEFAULT_TOKEN, MockState
from tdkit.sender import DeliveryResult, deliver
from tdkit.signing import MOCK_SECRET


class Fail(Exception):
    """A scenario's condition did not hold; the message says what the integration did."""


@dataclass(frozen=True)
class CheckOptions:
    docs: ContractDocs
    inspect_cmd: str
    webhook: str | None = None
    secret: str | None = None
    publish_cmd: str | None = None
    poll_cmd: str | None = None
    social_flag: bool = False
    port: int = 8787


class Context:
    def __init__(self, opts: CheckOptions, mode: str, state: MockState, port: int) -> None:
        self.opts, self.mode, self.state, self.port = opts, mode, state, port
        self.api_base = f"http://127.0.0.1:{port}"
        self.secret = opts.secret or MOCK_SECRET
        self.started = time.monotonic()

    # -- articles --------------------------------------------------------------------------

    def article(self, *, minutes: int = 0, **fields: Any) -> dict[str, Any]:
        """A level 1 delivery body made from the tag's sample, with a new `article_id`.

        The body has no internal links, no AI label and no `backlink_sources`, so a level 3
        integration stores `html` as sent; its image is on an allowed host (the mock).
        """
        body = copy.deepcopy(self.opts.docs.sample_delivery)
        article_id = str(uuid.uuid4())
        image_url = f"{self.api_base}/files/{article_id}.jpg"
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
            self.poll()
            calls = [r for r in self.state.results if r.article_id == body["article_id"]]
            if not calls:
                raise Fail("after --poll-cmd the integration reported no result for the send")
            last = calls[-1]
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
        return {**os.environ, "TD_API_BASE": self.api_base, "TD_CMS_TOKEN": DEFAULT_TOKEN}

    def inspect(self, article_id: str) -> dict[str, Any] | None:
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

    def _run(self, template: str, name: str, article_id: str) -> str:
        try:
            return run_template(template, env=self._env(), article_id=article_id)
        except CommandError as exc:
            raise Fail(f"{name} failed: {exc}") from exc


def _snippet(raw: bytes) -> str:
    text = raw.decode("utf-8", errors="replace").strip()
    return text[:200] if text else "(empty body)"
