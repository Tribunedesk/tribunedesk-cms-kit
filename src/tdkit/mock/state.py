"""In-memory state of the mock: sends, the change feed, link backs, results, file pulls and the
categories and tags the CMS sent (`POST /v3/cms/taxonomy/terms`).

Behaviour (cursor, `awaiting`, 409/410) is written by hand from guide 1 and the README of
the contract; shapes come from the OpenAPI document (see `server.py`).
"""

from __future__ import annotations

import re
import secrets
import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from tdkit.mock.media import MediaLibrary

ALL_SCOPES = (
    "media:read",
    "media:write",
    "settings:read",
    "settings:write",
    "backfill:write",
    "articles:read",
    "articles:write",
)
DEFAULT_TOKEN = "tdcms_mock"
ORG_CODE = "tdkit-mock"

SendState = Literal["awaiting", "delivered", "failed", "superseded"]
TAXONOMY_RUN_TTL = timedelta(hours=24)


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass
class Send:
    """One "Send to CMS" of an article: `delivery_id` is its `X-Delivery-Id`/`webhook-id`."""

    delivery_id: str
    article_id: str
    sent_at: str
    body: dict[str, Any]
    state: SendState = "awaiting"
    seq: int = 0  # order of creation; ties of `sent_at` and `/awaiting` cursors use it

    @property
    def key(self) -> tuple[str, int]:
        return (self.sent_at, self.seq)


@dataclass
class Change:
    seq: int
    kind: str
    changed_at: str
    article_id: str | None = None
    cursor: str = ""
    payload: dict[str, Any] = field(default_factory=dict)


class CursorError(Exception):
    """A cursor the feed cannot take: `status` 422 (not ours) or 410 (expired)."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


_CURSOR = re.compile(r"c([0-9a-f]{6})-(\d+)-(\d+)")


@dataclass(frozen=True)
class Recorded:
    """One request the integration made to the mock, with what the mock answered."""

    method: str
    path: str
    query: dict[str, list[str]]
    status: int
    body: Any
    answer: Any


@dataclass
class ResultCall:
    """One `POST /result` the integration made, with the status the mock answered."""

    article_id: str
    body: dict[str, Any]
    status: int
    delivery_id: str | None


class TaxonomyConflict(Exception):
    """A full run left open for more than 24 hours: `409 state_conflict`, nothing applied."""


@dataclass
class Taxonomy:
    """The CMS's categories and tags as Tribune Desk holds them (guide 3, Categories and tags).

    `terms` maps `(taxonomy, cms_term_id)` to the item as sent plus `last_run_id`, the full
    run that last sent it. The page with `is_last` removes every term another run sent last.
    """

    terms: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)
    run_id: str | None = None
    run_started_at: datetime | None = None
    last_full_sync_at: str | None = None

    def view(self) -> dict[str, Any] | None:
        """`taxonomy` of `GET /status`: `null` until the CMS sends anything."""
        if not self.terms and self.last_full_sync_at is None:
            return None
        return {"terms": len(self.terms), "last_full_sync_at": self.last_full_sync_at}

    def apply_page(self, body: dict[str, Any], now: datetime | None = None) -> list[dict]:
        """One page, already valid against `TaxonomyPageRequest`; its `results`.

        `ValueError` for the rules the schema cannot say (422), `TaxonomyConflict` (409).
        """
        items: list[dict[str, Any]] = body["items"]
        run_id, is_last = body.get("run_id"), bool(body.get("is_last"))
        if not items and not (run_id is not None and is_last):
            raise ValueError("items may be empty only on the last page of a full run")
        if is_last and run_id is None:
            raise ValueError("is_last needs run_id")
        keys = [(i["taxonomy"], i["cms_term_id"]) for i in items]
        if len(keys) != len(set(keys)):
            raise ValueError("each term may appear at most once per page")
        moment = now or datetime.now(UTC)
        started = self.run_started_at
        if run_id is not None and run_id != self.run_id:
            started = moment  # a new run_id abandons the previous run
        if is_last and (started is None or moment - started > TAXONOMY_RUN_TTL):
            raise TaxonomyConflict("the full run was left open for more than 24 hours")
        if run_id is not None and run_id != self.run_id:
            self.run_id, self.run_started_at = run_id, moment
        seen_by = run_id or self.run_id
        results = []
        for item, key in zip(items, keys, strict=True):
            known = key in self.terms
            if item.get("deleted"):
                self.terms.pop(key, None)
                results.append({"id": key[1], "status": "ok" if known else "unknown"})
                continue
            stored = {k: v for k, v in item.items() if k != "deleted"}
            # A single change keeps the run that last sent a known term; a new term counts
            # as seen by the open run, so its last page does not remove it.
            last = self.terms[key]["last_run_id"] if known and run_id is None else seen_by
            self.terms[key] = {**stored, "last_run_id": last}
            results.append({"id": key[1], "status": "ok"})
        if is_last:
            self.terms = {k: t for k, t in self.terms.items() if t["last_run_id"] == run_id}
            self.last_full_sync_at = moment.isoformat(timespec="seconds")
        return results


@dataclass
class MockState:
    read_mode: bool = False
    integration_enabled: bool = True
    image_hosts: list[str] = field(default_factory=lambda: ["127.0.0.1"])
    tokens: dict[str, set[str]] = field(default_factory=lambda: {DEFAULT_TOKEN: set(ALL_SCOPES)})
    # Scenario switches: the next `GET /changes` with a cursor answers 410 and drops the feed
    # before it; a `GET /articles/{id}` of a listed article makes a newer send right after.
    expire_cursor_once: bool = False
    supersede_after_get: set[str] = field(default_factory=set)

    sends: dict[str, list[Send]] = field(default_factory=dict)
    changes: list[Change] = field(default_factory=list)
    seq: int = 0
    send_seq: int = 0
    floor: int = 0
    last_changes_poll_at: str | None = None
    published: dict[str, dict[str, Any]] = field(default_factory=dict)
    reports: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    results: list[ResultCall] = field(default_factory=list)
    pulls: dict[str, int] = field(default_factory=dict)
    # TLS handshakes refused by a client (it does not trust the test CA, D5).
    tls_failures: int = 0
    calls: list[tuple[str, str, int]] = field(default_factory=list)
    requests: list[Recorded] = field(default_factory=list)
    lock: threading.RLock = field(default_factory=threading.RLock, repr=False)
    # Cursors are `c<run>-<epoch>-<seq>`: `run` tells this mock from an earlier one (a cursor an
    # integration kept from another `tdkit check`), `epoch` grows when the integration is enabled
    # again, which expires the cursors from before the break (guide 4, Cursors and expiry).
    run: str = field(default_factory=lambda: secrets.token_hex(3))
    epoch: int = 1
    switched: bool = False  # the first GET /changes since the integration was enabled came
    acked: int = 0  # the highest feed position any client passed as cursor
    media: MediaLibrary = field(default_factory=MediaLibrary)
    taxonomy: Taxonomy = field(default_factory=Taxonomy)

    def cursor_for(self, seq: int) -> str:
        return f"c{self.run}-{self.epoch}-{seq}"

    def parse_cursor(self, value: str) -> int:
        """The position of `value`; `CursorError` for a foreign or expired cursor."""
        match = _CURSOR.fullmatch(value)
        if match is None:
            raise CursorError(422, "validation_error", "cursor: not a cursor of this feed")
        run, epoch, seq = match.group(1), int(match.group(2)), int(match.group(3))
        if run != self.run:
            raise CursorError(
                422,
                "validation_error",
                "cursor from an earlier tdkit run: clear the integration's state or pass "
                "--reset-cmd",
            )
        if epoch != self.epoch or seq < self.floor:
            raise CursorError(410, "cursor_expired", "the cursor has expired")
        return seq

    def add_change(
        self,
        kind: str,
        *,
        article_id: str | None = None,
        payload: dict[str, Any] | None = None,
        changed_at: str | None = None,
    ) -> Change:
        with self.lock:
            self.seq += 1
            change = Change(
                self.seq,
                kind,
                changed_at or now_iso(),
                article_id,
                self.cursor_for(self.seq),
                payload or {},
            )
            self.changes.append(change)
            return change

    def set_enabled(self, enabled: bool) -> None:
        """The super admin's switch. Enabling after a break expires the earlier cursors."""
        with self.lock:
            if enabled and not self.integration_enabled:
                self.epoch += 1
                self.floor = self.seq
                self.switched = False
                self.on_reenable()
            self.integration_enabled = enabled

    def on_reenable(self) -> None:
        """Hook for level 4 state (resync sessions and held batches from before the break)."""

    def add_send(self, body: dict[str, Any], *, delivery_id: str | None = None) -> Send:
        """Record a new send of `body["article_id"]`; it supersedes older waiting sends.

        In read mode it also appears in the feed as an `article_sent` change.
        """
        with self.lock:
            article_id = str(body["article_id"])
            for older in self.sends.get(article_id, []):
                if older.state == "awaiting":
                    older.state = "superseded"
            self.send_seq += 1
            send = Send(
                delivery_id=delivery_id or str(uuid.uuid4()),
                article_id=article_id,
                sent_at=str(body["sent_at"]),
                body=body,
                seq=self.send_seq,
            )
            self.sends.setdefault(article_id, []).append(send)
            if self.read_mode:
                self.add_change("article_sent", article_id=article_id)
            return send

    def newest_send(self, article_id: str) -> Send | None:
        with self.lock:
            sends = self.sends.get(article_id)
            return sends[-1] if sends else None

    def send_by_seq(self, seq: int) -> Send | None:
        with self.lock:
            return next((s for v in self.sends.values() for s in v if s.seq == seq), None)

    def awaiting(self) -> list[Send]:
        with self.lock:
            waiting = [s for sends in self.sends.values() for s in sends if s.state == "awaiting"]
            return sorted(waiting, key=lambda s: s.key)

    def record_link_back(
        self,
        article_id: str,
        url: str,
        *,
        published_at: str | None,
        social_queue_exclude: bool | None,
        source: str,
    ) -> str:
        """Store a reported address; returns `ok`, `not_found` or `invalid_url` (guide 2)."""
        with self.lock:
            report = {
                "url": url,
                "published_at": published_at,
                "social_queue_exclude": social_queue_exclude,
                "source": source,
            }
            if article_id not in self.sends:
                return "not_found"
            if not url.startswith(("http://", "https://")):
                return "invalid_url"
            self.reports.setdefault(article_id, []).append(report)
            stored = self.published.get(article_id, {})
            stored.update(url=url, published_at=published_at)
            if social_queue_exclude is not None:
                stored["social_queue_exclude"] = social_queue_exclude
            self.published[article_id] = stored
            return "ok"

    def record_pull(self, name: str) -> None:
        with self.lock:
            self.pulls[name] = self.pulls.get(name, 0) + 1

    def record_call(
        self,
        method: str,
        path: str,
        status: int,
        query: dict[str, list[str]] | None = None,
        body: Any = None,
        answer: Any = None,
    ) -> None:
        with self.lock:
            self.calls.append((method, path, status))
            self.requests.append(Recorded(method, path, query or {}, status, body, answer))
