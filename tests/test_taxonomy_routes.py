"""`POST /v3/cms/taxonomy/terms` of the mock (contract 3.8.0-draft, guide 3, Categories and tags)."""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

from tdkit.mock.state import MockState

from .test_mock_routes import call

ROUTE = "/v3/cms/taxonomy/terms"


def term(cms_term_id: str, name: str, taxonomy: str = "tag", **extra: Any) -> dict[str, Any]:
    return {"taxonomy": taxonomy, "cms_term_id": cms_term_id, "name": name, **extra}


def page(base: str, items: list[dict[str, Any]], **fields: Any) -> tuple[int, Any]:
    status, body, _ = call(base, "POST", ROUTE, body={"items": items, **fields})
    return status, body


def status_taxonomy(base: str) -> Any:
    return call(base, "GET", "/v3/cms/status")[1]["taxonomy"]


def kept(state: MockState) -> set[str]:
    return {cms_term_id for _, cms_term_id in state.taxonomy.terms}


def test_status_shows_no_taxonomy_until_terms_are_sent(base: str) -> None:
    assert status_taxonomy(base) is None
    assert page(base, [term("7", "Budget")]) == (
        200,
        {"results": [{"id": "7", "status": "ok"}], "held_batch_id": None},
    )
    assert status_taxonomy(base) == {"terms": 1, "last_full_sync_at": None}


def test_full_run_over_two_pages_removes_terms_it_did_not_send(state: MockState, base: str) -> None:
    page(base, [term("1", "Old tag"), term("2", "Politics", "category")])
    run = str(uuid.uuid4())
    assert (
        page(base, [term("2", "Politics", "category"), term("3", "Budget")], run_id=run)[0] == 200
    )
    assert kept(state) == {"1", "2", "3"}  # nothing removed before the last page
    status, body = page(base, [term("4", "Mayor")], run_id=run, is_last=True)
    assert status == 200
    assert body["results"] == [{"id": "4", "status": "ok"}]
    assert kept(state) == {"2", "3", "4"}
    taxonomy = status_taxonomy(base)
    assert taxonomy["terms"] == 3
    assert taxonomy["last_full_sync_at"] is not None


def test_an_interrupted_run_removes_nothing_and_a_new_run_decides(
    state: MockState, base: str
) -> None:
    """Review Focus 2: no `is_last` keeps everything; the next run removes only what it missed."""
    first = str(uuid.uuid4())
    page(base, [term("1", "A"), term("2", "B")], run_id=first, is_last=True)
    page(base, [term("1", "A"), term("9", "New")], run_id=str(uuid.uuid4()))  # never finished
    assert kept(state) == {"1", "2", "9"}
    page(base, [term("9", "New")], run_id=str(uuid.uuid4()), is_last=True)
    assert kept(state) == {"9"}


def test_empty_last_page_of_a_full_run_clears_every_term(state: MockState, base: str) -> None:
    page(base, [term("1", "A")])
    assert page(base, [], run_id=str(uuid.uuid4()), is_last=True)[0] == 200
    assert kept(state) == set()
    assert status_taxonomy(base)["terms"] == 0


def test_single_changes_rename_and_delete(state: MockState, base: str) -> None:
    page(base, [term("5", "Budgte")])
    page(base, [term("5", "Budget")])
    assert state.taxonomy.terms[("tag", "5")]["name"] == "Budget"
    status, body = page(base, [term("5", "Budget", deleted=True), term("6", "X", deleted=True)])
    assert status == 200
    assert body["results"] == [{"id": "5", "status": "ok"}, {"id": "6", "status": "unknown"}]
    assert kept(state) == set()


def test_same_id_in_both_taxonomies_is_two_terms(state: MockState, base: str) -> None:
    page(base, [term("3", "Sport", "category"), term("3", "Football")])
    assert set(state.taxonomy.terms) == {("category", "3"), ("tag", "3")}


def test_bodies_the_contract_refuses_are_422(base: str) -> None:
    bad: list[dict[str, Any]] = [
        {"items": []},  # empty outside the last page of a full run
        {"items": [term("1", "A")], "is_last": True},  # is_last needs run_id
        {"items": [term("1", "A"), term("1", "B")]},  # the same term twice
        {"items": [term("1", "")]},  # empty name
        {"items": [term("1", "A", "section")]},
        {"items": [{**term("1", "A"), "color": "red"}]},  # additionalProperties
        {"items": [term(str(i), f"T{i}") for i in range(1001)]},
        {"items": [term("1", "A")], "run_id": "not-a-uuid"},
    ]
    for body in bad:
        status, error, _ = call(base, "POST", ROUTE, body=body)
        assert (status, error["code"]) == (422, "validation_error"), body


def test_token_and_scope(state: MockState, base: str) -> None:
    body = {"items": [term("1", "A")]}
    assert call(base, "POST", ROUTE, token=None, body=body)[0] == 401
    state.tokens["tdcms_reader"] = {"articles:read", "media:write"}
    status, error, _ = call(base, "POST", ROUTE, token="tdcms_reader", body=body)
    assert (status, error["code"]) == (403, "forbidden")


def test_a_run_left_open_for_24_hours_is_409(state: MockState, base: str) -> None:
    run = str(uuid.uuid4())
    page(base, [term("1", "A")], run_id=run)
    started = state.taxonomy.run_started_at
    assert started is not None
    state.taxonomy.run_started_at = started - timedelta(hours=25)
    status, error, _ = call(
        base, "POST", ROUTE, body={"items": [term("2", "B")], "run_id": run, "is_last": True}
    )
    assert (status, error["code"]) == (409, "state_conflict")
    assert kept(state) == {"1"}  # nothing applied
    status, _ = page(base, [term("2", "B")], run_id=str(uuid.uuid4()), is_last=True)
    assert status == 200
    assert kept(state) == {"2"}


def test_taxonomy_does_not_need_the_media_integration(state: MockState, base: str) -> None:
    state.set_enabled(False)
    assert page(base, [term("1", "A")])[0] == 200
