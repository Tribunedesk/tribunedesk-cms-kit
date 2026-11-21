# Odmowa importu wraca jako `rejected` z powodem — plan wykonania

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `POST /v3/cms/media` odpowiada `rejected` z powodem `collage`, `screenshot`, `graphic` albo `import_failed` dla pliku, którego import Tribune Desku odmówił; kontrakt `3.6.0-draft` to opisuje, `tdkit` to sprawdza, wtyczka (bez zmian w kodzie) przestaje takie pliki wysyłać, a 72 zdjęcia Styl.fm dostają ten stan.

**Architecture:** zmiana serwera i treści przewodnika w headlinesforge, potem przepływ „kontrakt najpierw” jak w etapie 6 (`docs/plans/2026-11-17-kontrakt-najpierw-etap-6-przewodnik-3-5.md`): PR `sync/latest` w `cms-api` → kit `1.4.1` zna 3.6 → tag `v3.6.0-draft` z `tag.yml` → drift kitu i `1.5.0` ze scenariuszem → drift `cms-php` → drift wtyczki. Na końcu `/deploy` headlinesforge i zapis w produkcji Styl.fm, oba na słowo ownera.

**Tech Stack:** Python 3.12 + uv (headlinesforge, kit), PHP 8.3 + PHPUnit (wtyczka), GitHub Actions.

**Spec:** `docs/specs/2026-11-21-odmowa-importu-rejected-design.md` (ten repo, gałąź `spec/odmowa-importu-rejected`).

## Stan przed planem (sprawdzony 21.11)

| Repo | Stan |
|---|---|
| headlinesforge `origin/master` `15f535fc5` | `CONTRACT_VERSION = "3.5.1-draft"` (`backend/api/cms_v3/routes.py:114`); wersja też w `docs/api/cms-v3.openapi.json`, `docs/api/cms/{README,VERSIONING}.md` + `pl/`, `tests/backend/test_cms_v3_contract.py`, `frontend/public/developers/cms/{guide.html,openapi.json}`; `push_wp_items` w `media_library/service.py:1531`; test `tests/media_library/test_service_wp_push.py` |
| `cms-api` | najnowszy tag `v3.5.1-draft` |
| kit `main` `cd6dd49` | tag `v1.4.0`; `SUPPORTED_MINORS = frozenset({(3, 5)})` (`src/tdkit/docs.py:27`); `ci/contract-tag` = `v3.5.1-draft`; atrapa: `cms_new_files` `src/tdkit/mock/media.py:473`, `import_pending` `:354`, kontrola `c_import` `src/tdkit/mock/media_routes.py:188`; scenariusz `cms_new_file` `src/tdkit/check/scenarios_media.py:259` |
| wtyczka `main` `081767d` (2.4.1) | `tribunedesk.json`: contract `3.5.1-draft`, protocol `1.1.2`, kit `1.4.0`; `MediaPush::candidates` ponawia tylko `rejected:host@` i `rejected:missing_metadata@` (`src/WordPress/MediaPush.php:72-74`); test `tests/test-media-push.php` |
| integracje wzorcowe kitu | Django i Drupal bez poziomu 4 — nowy scenariusz ich nie dotyczy |

## Teksty kontraktu (dosłownie; cytuje je kit)

- `guide/4-media-library.md`, punkt „Per item” (linia 85): przed `or \`excluded_agency\`` zostaje lista; na końcu zdania dopisać:
  > ; or, for a file Tribune Desk already received, the reason its import refused it: `collage`, `screenshot` or `graphic` (judged not to be a photo) or `import_failed` (the download or the import failed).
- Ten sam plik, akapit „To check…” (linia 99): zdania od „If `asset_id` stays `null`, the file is not coming” do „it answers `known`.” zastąpić:
  > When the import refuses the file, sending the item again answers `rejected` with the reason: `collage`, `screenshot` or `graphic` for a file judged not to be a photo, `import_failed` for a failed download (a host problem, `404`, not an image), a file over 25 MB or another failure of the import. This refusal is final: Tribune Desk does not try again and answers the same way every time, so do not send the item again. A file whose bytes Tribune Desk already holds under another record answers `known` and its `asset_id` stays `null`: that record is not paired with your id, and the file does not come back as a `new_asset` to you.
- Nowy punkt „Done when” przewodnika 4 (po punkcie o nowych plikach):
  > - A file answered `rejected` with `collage`, `screenshot`, `graphic` or `import_failed` is not sent to `POST /media` again.
- Opis `POST /media` w OpenAPI (`backend/api/cms_v3/routes.py` ok. 545-560): „it stays `null` if the import refused the file” → „it stays `null` while the import runs”; lista powodów `rejected` + „`collage`, `screenshot`, `graphic`, `import_failed` (the import refused a file it already received)”; „A refusal is not remembered: send the item again after the settings change.” → „A refusal by the settings is not remembered: send the item again after the settings change. A refusal by the import is final.”
- `CHANGELOG.md`:
  ```
  ## 3.6.0-draft – <data lądowania>

  - **Breaking:** `POST /v3/cms/media` answers `rejected` with `collage`, `screenshot`, `graphic` or `import_failed` for a file Tribune Desk already received and its import refused; it used to answer `known` with `asset_id` `null`.

  **Integrators:**

  - `L4`: do not send a file to `POST /media` again after `rejected` with `collage`, `screenshot`, `graphic` or `import_failed`.
  ```
  Wersja PL (`docs/api/cms/pl/…`) tłumaczy budowniczy w tym samym PR-ze.

## Global Constraints

- Każda zmiana w worktree swojego repo; lądowanie `main`/`master` tylko `/ship` na słowo ownera. PR `sync/latest` w `cms-api` scala owner ręcznie. Tagu kontraktu nie stawia sesja — robi to `tag.yml`; ręczny tag = łańcuch oblany, raport zamiast obejścia.
- Teksty z sekcji „Teksty kontraktu” dosłownie wszędzie, gdzie kit je cytuje (`coverage.toml`, `scenarios_media.py`); zmiana słowa po fazie A to nowy patch.
- Pełny `pytest` nie biegnie lokalnie — tylko zawężone cele; całość na CI.
- Kit: wydanie `1.4.1` przed tagiem (tylko `SUPPORTED_MINORS = frozenset({(3, 5), (3, 6)})`), `1.5.0` po tagu (scenariusz, fixture, pokrycie, `frozenset({(3, 6)})`, rytuał parytetu — trzy evale, ok. 16 USD, wiersze w README także przy wyniku oblanym). Pliki wydania jak w etapie 6 Task 3.
- Produkcja: `/deploy` headlinesforge i zapis meta na Styl.fm — każde osobno, na słowo ownera.

## Review Focus

1. **Plik w trakcie importu dostaje `rejected`** (pozycja `pending`/w opisie) — wtyczka przestałaby pytać i para nigdy by nie powstała (anty-cel specu). Test w Task 1.
2. **Duplikat treści (`skipped` `duplicate`/`known_asset`) dostaje `rejected`** — integrator uznałby za odmowę plik, który jest w bibliotece. Test w Task 1.
3. **Klucz powtórzony w jednym żądaniu** — drugi musi zostać `known`, nie odziedziczyć odmowy w złej kolejności wyników. Test w Task 1.
4. **Atrapa sprawdza ustawienia po odmowie importu** (kolejność warunków w `cms_new_files`) — plik odrzucony przy `new_files_cms_to_td = false` ma dalej dostać `new_files_disabled`, jak na serwerze, gdzie `_rejection` idzie przed importem. Test w Task 4.
5. **Wtyczka ponawia `rejected:host` po 7 dniach** — zmiana nie może tego zepsuć; test wtyczki obejmuje oba przypadki (Task 7).

---

## Faza A — headlinesforge: serwer i treść 3.6.0-draft

### Task 1: `push_wp_items` zwraca odmowę importu

**Files** (worktree headlinesforge, gałąź `feat/cms-odmowa-importu-rejected` od `origin/master`):
- Modify: `media_library/service.py:1531-1594` (`push_wp_items`)
- Test: `tests/media_library/test_service_wp_push.py`

**Interfaces:**
- Consumes: `self._repo.import_items_by_keys(org_code, keys) -> list[ImportItem]` (`media_library/db/repository.py:1506`; `ImportItem.status`, `.reason`, `.external_key`), `is_junk` (`media_library/rules.py:263`).
- Produces: wynik `push_wp_items` `rejected:<reason>` dla odmowy importu; `backend/services/cms_media.py:_item_result` już mapuje `rejected:x` na `ItemResult(status="rejected", reason="x")` — bez zmian.

- [ ] **Step 1: testy** w `tests/media_library/test_service_wp_push.py` (wzór istniejących testów tego pliku: wiersz `media_import_items` z kluczem `wp:<id>` w danym stanie, potem `push_wp_items` z tym samym załącznikiem):
  - `test_skipped_collage_answers_rejected_collage` — wiersz `skipped`/`collage` → wynik `"rejected:collage"`; to samo parametryzacją dla `screenshot`, `graphic`.
  - `test_failed_import_answers_rejected_import_failed` — `failed` z `reason` `host`, `model`, `http_404` → `"rejected:import_failed"`.
  - `test_pending_and_imported_stay_known` — `pending`, `imported` → `"known"` (Review Focus 1).
  - `test_duplicate_and_known_asset_stay_known` — `skipped`/`duplicate`, `skipped`/`known_asset` → `"known"` (Review Focus 2).
  - `test_repeated_key_in_one_request_stays_known` — ten sam załącznik dwa razy w jednym wywołaniu przy wierszu `skipped`/`collage`: pierwszy `"rejected:collage"`, drugi `"known"` (Review Focus 3).
  Run: `uv run pytest tests/media_library/test_service_wp_push.py -q` — Expected: nowe testy FAIL (`known` zamiast `rejected:…`).
- [ ] **Step 2: implementacja.** W `push_wp_items` zamień `existing_import_keys` na `import_items_by_keys` dla kluczy z `seen` (wiersze trzymaj w słowniku po `external_key`); funkcja modułowa `_import_refusal(row: ImportItem) -> str | None`: `skipped` + `is_junk(reason)` → `reason`; `failed` → `"import_failed"`; inaczej `None`. Przy `key in known`: odmowa → `results[index] = f"rejected:{refusal}"`, inaczej `"known"`. Wiersze importu wstecznego (`job_rows`, `BACKFILL_KEY_BLOCKING` = `described`/`imported`) bez zmian. Docstring `push_wp_items` dopisuje nowy wynik.
- [ ] **Step 3:** Run jak w Step 1 + `uv run pytest tests/backend/test_cms_v3_media.py -q` (jeśli istnieje; inaczej plik testów trasy `/v3/cms/media` znaleziony `grep -rl "cms/media" tests/backend`) — Expected: PASS.
- [ ] **Step 4:** `uv run ruff check media_library tests/media_library` i `uv run pyright media_library` — Expected: bez błędów. Commit `feat(media): odmowa importu wraca do CMS jako rejected z powodem`.

### Task 2: Przewodnik, OpenAPI, CHANGELOG i wersja 3.6.0-draft

**Files** (ta sama gałąź):
- Modify: `docs/api/cms/guide/4-media-library.md`, `docs/api/cms/pl/guide/4-media-library.md`, `docs/api/cms/CHANGELOG.md` (+ `pl/` jeśli ma własny), `backend/api/cms_v3/routes.py` (opis `POST /media`, `CONTRACT_VERSION = "3.6.0-draft"`), `docs/api/cms-v3.openapi.json`, `docs/api/cms/{README,VERSIONING}.md` + `pl/`
- Regenerate: `frontend/public/developers/cms/guide.html`, `openapi.json` (`uv run python -m scripts.export_cms_guide`)
- Test: `tests/backend/test_cms_v3_contract.py` (asercje wersji)

- [ ] **Step 1:** asercje wersji w `tests/backend/test_cms_v3_contract.py` → `3.6.0-draft`; Run `uv run pytest tests/backend/test_cms_v3_contract.py -q` — Expected: FAIL na wersji.
- [ ] **Step 2:** teksty z sekcji „Teksty kontraktu”, tłumaczenie PL, wersja we wszystkich miejscach z tabeli stanu (`grep -rn "3.5.1-draft" docs/api backend tests/backend frontend/public/developers` po zmianie — Expected: tylko CHANGELOG), regeneracja OpenAPI (`docs/api/cms-v3.openapi.json` = `build_openapi()`) i strony.
- [ ] **Step 3:** `uv run pytest tests/backend/test_cms_v3_contract.py tests/scripts/test_cms_api_public_tree.py -q` i `uv run python -m scripts.cms_contract_guard --base origin/master --head HEAD` — Expected: PASS; strażnik widzi wpis w CHANGELOG.
- [ ] **Step 4:** podgląd tego, co dostanie `cms-api`: `uv run python -m scripts.cms_api_public_tree <klon cms-api>`, w klonie `python .github/scripts/contract_gate.py --repo .` — Expected: jedyny problem to brak wydania `tdkit` znającego 3.6 (minor za nowy punkt „Done when”, CHANGELOG z **Breaking** i `Integrators` przechodzą).
- [ ] **Step 5:** commit `docs(cms): kontrakt 3.6.0-draft — odmowa importu jako rejected`, push gałęzi, PR do `master`, CI zielone.

**STOP A:** raport (diff, wynik kroku 4, CI). Owner: `/ship` headlinesforge. Po lądowaniu: `gh run list --workflow cms-api-docs.yml -L1` zielony, w `cms-api` otwarty PR `sync/latest`, a jego `pr.yml` **czerwony** z komunikatem o `SUPPORTED_MINORS` (sygnał, nie błąd; każdy inny powód = STOP). `/deploy` headlinesforge — osobno, na słowo ownera; łańcuch go nie potrzebuje (atrapa czyta wersję z dokumentacji).

## Faza B — kit `1.4.1`: kit zna 3.6 przed tagiem

### Task 3: `SUPPORTED_MINORS` z (3, 6) i wydanie `1.4.1`

**Files** (worktree kitu, gałąź `feat/supported-3-6`): `src/tdkit/docs.py:27`, `tests/test_docs.py`, pliki wydania jak w etapie 6 Task 3 (wersja `1.4.1`, pin `@v1.4.1`).

**Interfaces:**
- Produces: tag `v1.4.1`, którego `src/tdkit/docs.py` ma dokładnie `SUPPORTED_MINORS = frozenset({(3, 5), (3, 6)})` (kształt czytany przez `_MINORS_LINE` w `cms-api`).

- [ ] **Step 1: test** `test_accepts_3_6_and_still_3_5`: `is_supported("v3.6.0-draft")` i `is_supported("v3.5.1-draft")` prawdziwe, `is_supported("v3.7.0-draft")` fałszywe. Run `uv run pytest tests/test_docs.py -q` — Expected: FAIL.
- [ ] **Step 2:** zmiana linii 27; Run — Expected: PASS.
- [ ] **Step 3:** `uv run tdkit mock --docs <klon cms-api na sync/latest>` i `GET /v3/cms/status` — Expected: `contract_version` `3.6.0-draft`.
- [ ] **Step 4:** pliki wydania, commit `release: tdkit 1.4.1 (kit zna kontrakt 3.6)`, PR, CI zielone.

**STOP B:** owner `/ship` kitu + tag `v1.4.1`; `gh run rerun` `pr.yml` na PR-ze `sync/latest` — Expected: PASS. Owner scala PR. Expected: `tag.yml` zielony, `v3.6.0-draft` adnotowany (`git cat-file -t` = `tag`).

## Faza C — kit `1.5.0`: atrapa, scenariusz, pokrycie

### Task 4: Atrapa pamięta odmowę importu

**Files** (gałąź `contract/latest` z `contract-drift.yml`; jeśli runu nie było — `gh workflow run contract-drift.yml`):
- Modify: `src/tdkit/mock/media.py` (pole `MediaLibrary.refused_imports: dict[str, str]`, `import_pending`, `cms_new_files`), `src/tdkit/mock/media_routes.py` (`c_import`)
- Test: `tests/test_media_state.py`

**Interfaces:**
- Produces: `import_pending(state: MockState, refuse: dict[str, str] | None = None) -> list[str]` — id z `refuse` nie tworzą pliku, trafiają do `lib.refused_imports[id] = reason` i wypadają z `pending_imports`; wynik dalej to lista sparowanych. Kontrola `POST /_tdkit/media/import` przyjmuje opcjonalne `{"refuse": {"<cms_media_id>": "<reason>"}}` i odpowiada `{"paired": [...], "refused": [...]}`.

- [ ] **Step 1:** obejrzyj czerwony CI PR-a driftu — Expected: `test_coverage.py` pada na nowy punkt „Done when” i pozycję `Integrators` 3.6.0-draft (inna lista = błąd fazy A). Zapisz w raporcie.
- [ ] **Step 2: testy** w `tests/test_media_state.py`: `test_refused_import_answers_rejected_with_reason` (`import_pending(st, refuse={"c1": "collage"})` → `[]`; `cms_new_files` z `c1` → `status` `rejected`, `reason` `collage`, `asset_id` `None`); `test_refused_import_still_checks_settings_first` (przy `new_files_cms_to_td` wyłączonym → `new_files_disabled`; Review Focus 4). Run `uv run pytest tests/test_media_state.py -q` — Expected: FAIL.
- [ ] **Step 3:** implementacja: w `cms_new_files` warunek `cms_media_id in lib.refused_imports` → `rejected` z zapisanym powodem, zaraz po sprawdzeniu `new_files_disabled`, przed `known`. Run — Expected: PASS.

### Task 5: Scenariusz `l4-import-refused` i pokrycie

**Files:** `src/tdkit/check/scenarios_media.py`, rejestr scenariuszy (tam, gdzie `cms_new_file` jest zarejestrowany), `src/tdkit/check/coverage.toml`, `README.md` (tabela scenariuszy), `tests/test_check_media.py`.

**Interfaces:**
- Consumes: `import_pending(..., refuse=...)` z Task 4; `ctx.media_add`, `ctx.sync`, `ctx.mark`, `ctx.requests_since` (jak w `cms_new_file`).
- Produces: id scenariusza `l4-import-refused` (cytuje go `coverage.toml` i log `tdkit` wtyczki w Task 7).

- [ ] **Step 1: testy** w `tests/test_check_media.py` (wzór istniejących testów scenariuszy poziomu 4): `test_import_refused_fails_a_cms_that_sends_again` i `test_import_refused_passes_a_cms_that_stops`. Run — Expected: FAIL (brak scenariusza).
- [ ] **Step 2:** `import_refused(ctx: Context) -> str`: `ctx.media_add()`, `ctx.sync()`, `media.import_pending(ctx.state, refuse={id: "collage"})`, `ctx.sync()` (integracja pyta o parę i dostaje `rejected`); `mark = ctx.mark()`; trzy razy `ctx.sync()`; `expect` brak pozycji z tym id w `POST /v3/cms/media` od `mark` — komunikat „a file refused by the import (collage) was sent again”. Stała `D4_IMPORT_REFUSED` = punkt „Done when” dosłownie; `Scenario("l4-import-refused", 4, …, D4_IMPORT_REFUSED, f"{G4}#sending-new-files", import_refused)` (kotwica jak w scenariuszu `cms_new_file`). Run — Expected: PASS.
- [ ] **Step 3:** `coverage.toml`: `[[integrators]]` `version = "3.6.0-draft"`, `action` = tekst pozycji bez „`L4`: ”, `handled_by = ["scenario:l4-import-refused"]`. Run `uv run pytest tests/test_coverage.py tests/test_check_media.py tests/test_check.py -q` — Expected: PASS.
- [ ] **Step 4:** commit, push `contract/latest`, CI zielone (integracje wzorcowe bez poziomu 4 — joby `reference-*` bez zmian).

### Task 6: `1.5.0` — stary minor wypada, parytet, wydanie

Jak etap 6 Task 6: `SUPPORTED_MINORS = frozenset({(3, 6)})` + `test_3_5_is_no_longer_supported`; pliki wydania `1.5.0`; `tests/test_project.py` FAIL na braku wierszy parytetu 1.5; trzy evale `parity-django|laravel|node` (ok. 16 USD), kryterium: `tdkit check` 1–4 zielony z `l4-import-refused`; wiersze w README z wynikiem i kosztem; `tests/test_project.py` PASS, CI zielone.

**STOP C:** raport (CI, evale, koszt). Owner `/ship` kitu + tag `v1.5.0`.

## Faza D — `cms-php` i wtyczka

### Task 7: Drift `cms-php`, drift wtyczki i test wtyczki

- [ ] **Step 1:** PR `contract/latest` w `cms-php` (`VERSION`, `ContractVersion::TESTED` = `3.6.0-draft`), CI zielone. **STOP:** owner `/ship` + tag `cms-php` (następny patch po `v1.1.2`).
- [ ] **Step 2:** PR `contract/latest` wtyczki (`gh workflow run contract-drift.yml -R Tribunedesk/tribunedesk-wordpress`) — Expected: `tribunedesk.json` contract `3.6.0-draft`, protocol = nowy tag `cms-php`, kit `1.5.0`; inny `kit` = STOP. Run w `action_required` → zatwierdzić i zapisać jako znalezisko.
- [ ] **Step 3: test wtyczki** na tej gałęzi, `tests/test-media-push.php`: `test_odmowa_importu_nie_jest_kandydatem` — załącznik z `_hf_media_pushed = rejected:collage@<teraz>` i `rejected:import_failed@<teraz - 8 dni>` nie jest w `MediaPush::candidates(50)`; `test_odmowa_hosta_wraca_po_tygodniu` — `rejected:host@<teraz - 8 dni>` jest (Review Focus 5). Expected: PASS bez zmian w `src/` (jeśli FAIL — STOP, spec zakłada brak zmian kodu). Commit na gałęzi driftu.
- [ ] **Step 4:** CI — Expected: PHPUnit zielony, job `tdkit` z `l4-import-refused … pass`.

**STOP D:** owner `/ship` wtyczki. Wydanie wtyczki (wersja, ZIP, `Publish manifest`) — osobno, poza planem.

## Faza E — produkcja

### Task 8: `/deploy` headlinesforge i 72 zdjęcia Styl.fm

- [ ] **Step 1:** po `/deploy` headlinesforge (słowo ownera): `GET https://api.tribunedesk.com/v3/cms/openapi.json` ma `info.version` `3.6.0-draft`.
- [ ] **Step 2: odczyt** (Git Bash, `MSYS_NO_PATHCONV=1`, kontekst `da`): lista ID załączników Styl.fm z `_hf_media_pushed` `known@%`/`accepted@%`, bez `_hf_asset_id`, starszych niż 3 dni (`MediaPush::PAIR_CHECK`) — zapytanie jak w `## Pomiar` czeku `ledger/done/2026-11-16-tribunedesk-wordpress-po-wdrozeniu-2-4-0.md`, z `GROUP_CONCAT(p.ID)`. Pokaż ownerowi liczbę i ID.
- [ ] **Step 3: zapis — tylko na słowo ownera:** `delete_post_meta($id, '_hf_media_pushed')` dla tych ID (`kubectl -n stylfm exec deploy/stylfm -c app -- php -r '…wp-load.php…'`). Najbliższe wysłanie wtyczki (godzinny cron) traktuje je jak nowe.
- [ ] **Step 4:** po ok. 2 h ten sam odczyt — Expected: 0 zdjęć `known@`/`accepted@` bez pary sprzed 3 dni; nowy rozkład `_hf_media_pushed` (`rejected:collage@`, `rejected:screenshot@` …) w raporcie.

**STOP E:** raport ownerowi; `/ledger close 2026-11-21-tribunedesk-wordpress-zdjecia-known-bez-asset-id done "<wynik>"`.
