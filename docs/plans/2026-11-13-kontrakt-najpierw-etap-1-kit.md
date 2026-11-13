# Kontrakt najpierw — etap 1: kit — plan wykonania

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** kit sam zauważa nowy tag kontraktu (PR podbicia + czerwony run), nie przepuszcza punktu „Done when” ani pozycji `Integrators` bez obsługi, przyjmuje dwa minory naraz i ma rytuał evalu parytetu na trzech CMS-ach; wydanie `tdkit` 1.2.0.

**Architecture:** Przypinka kontraktu w jednym miejscu (`CONTRACT_TAG` w `ci.yml`), fixture `tests/fixtures/cms-api` jest kopią tego tagu. Pokrycie to dane (`src/tdkit/check/coverage.toml`) sprawdzane testem na fixture. Drift to skrypt `ci/contract_drift.py` (czyste funkcje + `main`) i workflow `contract-drift.yml` na `GITHUB_TOKEN`. Evale parytetu to trzy nowe scenariusze istniejącego `evals/run.py`.

**Tech Stack:** Python 3.12, biblioteka standardowa (`tomllib`) + `jsonschema==4.23.0`, pytest, ruff, pyright, GitHub Actions, `gh`.

**Spec:** `docs/specs/2026-11-13-kontrakt-najpierw-automaty-design.md` (zatwierdzony 13.11, wariant 1). Ten plan wykonuje etap 1 z sekcji 8; etapy 2–6 dostaną osobne plany po etapie 1.

## Global Constraints

- Żadnej nowej zależności; TOML przez `tomllib`.
- pathlib, `encoding="utf-8"` na każdej operacji na plikach, bez `shell=True`. Sieć tylko w `docs.py` (istniejący clone tagu) i w `ci/contract_drift.py` (`git ls-remote`/`git clone` publicznego repo, uruchamiany tylko w CI) — oba to GitHub, jak już opisuje docstring `docs.py`.
- `SUPPORTED_MINORS = frozenset({(3, 4)})` po tym etapie: (3, 5) dochodzi dopiero w wydaniu dla kontraktu 3.5 (spec D2c). Etap zmienia kształt, nie zakres.
- Strażnik w `cms-api` (etap 3) czyta `SUPPORTED_MINORS` wyrażeniem regularnym — linia w `docs.py` ma dokładnie postać `SUPPORTED_MINORS = frozenset({(3, 4)})` / `frozenset({(3, 4), (3, 5)})`, w jednej linii.
- Punkt „Done when” jest pokryty, gdy `done_when` jakiegoś scenariusza jest jego podciągiem (ta sama relacja co w `test_done_when_quotes_are_literal`), albo gdy ma wpis w `coverage.toml`.
- PR podbicia: gałąź `contract/latest`, jeden otwarty PR, tytuł `contract: v<stary> → v<nowy>`; nigdy auto-merge; run driftu kończy się błędem, póki przypinka jest w tyle.
- Wersje po etapie: `tdkit` 1.2.0 (`src/tdkit/__init__.py`), `plugin.json` 1.2.0, `SKILL.md` przypina `@v1.2.0` (test `test_skill_pins_tdkit_tag` już tego pilnuje).
- Pełny `pytest` nie biegnie lokalnie (hook): lokalnie `uv run pytest tests/<plik>.py` lub `-k`; całość na CI.
- Lądowanie tylko `/ship` na słowo ownera; tag `v1.2.0` przed `main` (Rollout w wiki).

## Review Focus

1. **Punkt „Done when” przeformułowany w patchu** (ten sam sens, inne słowa): stary cytat scenariusza przestaje być podciągiem → `test_done_when_quotes_are_literal` i test pokrycia są czerwone na PR-ze `contract/latest`, a nie zielone z przestarzałym wpisem. Test w Task 3 (`test_stale_entry_is_reported`).
2. **Ten sam tekst pozycji `Integrators` w dwóch wersjach** (np. „Nothing to do.” albo powtórzona rada): klucz wpisu to `version` + tekst, więc dwie pozycje → dwa wpisy. Test w Task 3 (`test_integrators_key_includes_version`).
3. **Tag tylko `-draft` vs wydanie tej samej wersji** (`v3.4.2-draft` i `v3.4.2`): drift uznaje `v3.4.2` za nowszy i otwiera PR. Test w Task 4 (`test_release_after_draft_is_newer`).
4. **Przypinka nowsza niż najnowszy tag** (ktoś przypiął tag, który potem usunięto): drift nie otwiera PR-a „w dół”, tylko pada z komunikatem. Test w Task 4 (`test_pin_ahead_of_latest_fails`).
5. **Fixture z plikami, których nowy tag już nie ma** (usunięty przykład): kopia zastępuje katalog w całości, nie nakłada się na stary. Test w Task 4 (`test_refresh_fixture_removes_stale_files`).

---

## Mapa plików

| Plik | Odpowiedzialność |
|---|---|
| `src/tdkit/docs.py` | `SUPPORTED_MINORS`, `is_supported` |
| `src/tdkit/integrators.py` | nowe `changelog_items` (wszystkie pozycje), `integrators` filtruje je |
| `src/tdkit/check/coverage.toml` | wpisy pokrycia: punkty „Done when” i pozycje `Integrators` |
| `tests/test_coverage.py` | test pokrycia na fixture |
| `ci/contract_drift.py` | porównanie przypinki z tagiem, podbicie `ci.yml`, odświeżenie fixture, treść PR-a |
| `.github/workflows/ci.yml` | `CONTRACT_TAG` w `env` workflowu, `workflow_dispatch` |
| `.github/workflows/contract-drift.yml` | harmonogram, gałąź, PR, dispatch CI, czerwony run |
| `tests/test_contract_drift.py` | testy czystych funkcji driftu |
| `evals/run.py`, `evals/scenarios/parity-*.md` | trzy scenariusze parytetu, sprawdzenie „bez lokalnych źródeł” |
| `tests/test_project.py` | tabela evalów ma wiersze parytetu bieżącego minora |
| `README.md`, `evals/README.md` | opis pokrycia, driftu, parytetu, tabela |

---

### Task 1: `SUPPORTED_MINORS` — zbiór minorów

**Files:**
- Modify: `src/tdkit/docs.py:22-31`
- Modify: `README.md:80` (zdanie o obsługiwanych wersjach)
- Test: `tests/test_docs.py`

**Interfaces:**
- Produces: `SUPPORTED_MINORS: frozenset[tuple[int, int]]`; `is_supported(version: str) -> bool` (sygnatura bez zmian). Nazwa `SUPPORTED_MINOR` znika.

- [ ] **Step 1: Testy.** Istniejący `test_every_patch_of_the_supported_minor_is_accepted` zostaje bez zmian (dziś zbiór = {(3, 4)}). Nowe:

```python
def test_two_minors_are_accepted_in_a_transition(monkeypatch):
    monkeypatch.setattr(docs, "SUPPORTED_MINORS", frozenset({(3, 4), (3, 5)}))
    assert docs.is_supported("3.4.2-draft") and docs.is_supported("3.5.0-draft")
    assert not docs.is_supported("3.6.0-draft")

def test_supported_minors_line_is_machine_readable():
    # the cms-api tag guard (spec D2c) reads this line with a regex
    text = Path(docs.__file__).read_text(encoding="utf-8")
    assert re.search(r"^SUPPORTED_MINORS = frozenset\(\{(\(\d+, \d+\)(, )?)+\}\)$", text, re.M)
```

- [ ] **Step 2:** `uv run pytest tests/test_docs.py -q` → FAIL (`SUPPORTED_MINORS` nie istnieje).
- [ ] **Step 3:** W `docs.py` `SUPPORTED_MINORS = frozenset({(3, 4)})`, komentarz nad nim: wydanie dla nowego minora przyjmuje też poprzedni do wydania po tagu nowego (spec D2c); `is_supported` sprawdza przynależność. README:80 — jedno zdanie o oknie przejściowym.
- [ ] **Step 4:** `uv run pytest tests/test_docs.py -q` → PASS; `uv run ruff check . && uv run pyright` → czysto.
- [ ] **Step 5:** commit `feat: SUPPORTED_MINORS, a set of contract minors for the transition window`.

### Task 2: jedna przypinka kontraktu w CI i fixture równy tagowi

**Files:**
- Modify: `.github/workflows/ci.yml` (env workflowu, joby `examples`, `reference-django`, `reference-drupal`; wyzwalacz)
- Modify: `tests/test_docs.py` (`test_fixture_is_3_4_2_with_guide_4` → `test_fixture_is_the_ci_contract_tag`)

**Interfaces:**
- Produces: w `ci.yml` jedna linia `  CONTRACT_TAG: v3.4.2-draft` w `env:` na poziomie workflowu (wcięcie 2 spacje), czytana przez Task 4; `tests/conftest.py`/`test_docs.py` helper `ci_contract_tag() -> str` (regex `^  CONTRACT_TAG: (v\S+)$` na `ci.yml`), używany w Task 3.

- [ ] **Step 1: Test.**

```python
def test_fixture_is_the_ci_contract_tag():
    assert "v" + load_docs(FIXTURE).version == ci_contract_tag()

def test_ci_names_the_contract_once():
    text = CI_YML.read_text(encoding="utf-8")
    assert len(re.findall(r"v\d+\.\d+\.\d+(-draft)?", text)) == 1
```

- [ ] **Step 2:** `uv run pytest tests/test_docs.py -q` → FAIL (CI ma `v3.4.1-draft` trzy razy, fixture to 3.4.2).
- [ ] **Step 3:** `env: CONTRACT_TAG: v3.4.2-draft` na poziomie workflowu; job `examples` traci własne `env`; joby reference używają `--contract "$CONTRACT_TAG"`. Wyzwalacze: dochodzi `workflow_dispatch:` (spec D2b krok 3). Podbicie z 3.4.1 na 3.4.2 jest tu świadome: fixture już jest 3.4.2, a test wymaga równości.
- [ ] **Step 4:** `uv run pytest tests/test_docs.py -q` → PASS.
- [ ] **Step 5:** commit `ci: one CONTRACT_TAG (v3.4.2-draft) for every job; workflow_dispatch`. Na PR-ze sprawdzić, że `examples`, `reference-django`, `reference-drupal` są zielone na 3.4.2 — jeśli nie, to rzeczywisty dryf, który ten etap ma ujawnić: zatrzymać się i zgłosić ownerowi.

### Task 3: test pokrycia

**Files:**
- Modify: `src/tdkit/integrators.py` (wydzielenie parsera)
- Create: `src/tdkit/check/coverage.toml`
- Create: `tests/test_coverage.py`
- Test: `tests/test_integrators.py` (bez zmian zachowania — musi zostać zielony)

**Interfaces:**
- Produces: `changelog_items(changelog: str) -> list[dict[str, Any]]` w `integrators.py` — każda pozycja każdego bloku `**Integrators:**`: `{"version": str, "tags": list[str] (wszystkie, także nieznane), "action": str}`, pomija „Nothing to do.” i linie bez tagów. `integrators(...)` filtruje wynik `changelog_items` (wersje, poziomy, tryb, ostrzeżenie o nieznanych tagach) — zachowanie bez zmian.
- Produces: format `coverage.toml`:

```toml
[[done_when]]           # punkt bez scenariusza, którego done_when jest jego podciągiem
guide = "guide/2-link-back.md"
point = "<dosłowny tekst punktu>"
scenarios = ["l2-reports-url"]   # albo:
# reason = "<dlaczego tdkit tego nie sprawdza>"

[[integrators]]
version = "3.4.0-draft"
action = "<dosłowny tekst pozycji>"
handled_by = ["scenario:l1-bad-signature", "skill:references/update-mode.md"]   # albo ["none"] + reason
```

- [ ] **Step 1: Testy** w `tests/test_coverage.py` (na `FIXTURE`; parser punktów „Done when” to helper w tym pliku: wypunktowania `- ` w sekcji `## Done when` do następnego `## `, łącznie z listą po „In read mode, also:”):

```python
def test_every_done_when_point_is_covered():        # brak → lista punktów w komunikacie
def test_every_integrators_item_is_handled():        # klucz (version, action)
def test_stale_entry_is_reported():                  # wpis bez pasującego punktu/pozycji → FAIL
def test_entries_name_real_scenarios_and_files():    # scenario:<id> istnieje; skill:<ścieżka> istnieje względem katalogu skilla
def test_entry_has_exactly_one_of_scenarios_or_reason():   # ["none"] wymaga reason
def test_integrators_key_includes_version():          # dwie pozycje o tym samym tekście w dwóch wersjach → dwa wymagane wpisy
def test_unknown_level_tag_fails():                   # changelog_items na tekście z `L5` → test pokrycia czerwony
```

Testy „stale”, „key”, „unknown tag” działają na małych tekstach w pamięci przez funkcję `problems(guide_dir: Path, changelog: str, entries: dict) -> list[str]` w `tests/test_coverage.py`; dwa pierwsze testy wołają ją na fixture i `coverage.toml` i sprawdzają `== []`.

- [ ] **Step 2:** `uv run pytest tests/test_coverage.py tests/test_integrators.py -q` → FAIL (brak `changelog_items`, brak `coverage.toml`).
- [ ] **Step 3:** `changelog_items` + przepięcie `integrators`; `coverage.toml` z wpisami dla 3.4.2. Stan sprawdzony 13.11 — punkty bez scenariusza-podciągu (do wpisania):
  - G1 „Two attempts of one send that overlap…” → `l1-overlapping-attempts`
  - G1 „Images are downloaded only from the hosts…” → `l1-image-host`
  - G1 read: „Every result carries the `delivery_id`…” → `read-delivers-result`
  - G1 read: „After `409 state_conflict`…” → `read-superseded-409`
  - G1 read: „After `410 cursor_expired`…” → `read-cursor-expired`
  - G2 „Your token for this route is a `tdcms_` token…” → sprawdzić w atrapie: jeśli trasa `/v3/cms/articles/published` odrzuca token bez `articles:write` lub nie-`tdcms_` i `l2-reports-url` przez to by oblał → `l2-reports-url`; inaczej `reason`.
  - G2 „If your CMS has a setting that keeps a post off Facebook…” → `l2-social-flag`

  Pozycje `Integrators` (19, od 3.0.0 do 3.4.0): każdą przypisać do scenariusza, który ją sprawdza, albo do `skill:` pliku, który ją prowadzi, albo `none` z powodem (np. 3.3.0 „move from `POST /v2/cms/published-urls`…” → `none`, „trasa usunięta, atrapa jej nie ma; nowa integracja nie może jej użyć”). Wątpliwe przypisania wypisać w opisie PR-a.
- [ ] **Step 4:** `uv run pytest tests/test_coverage.py tests/test_integrators.py tests/test_check.py tests/test_check_media.py -q` → PASS; ruff, pyright czysto.
- [ ] **Step 5:** commit `test: every Done-when point and Integrators item is covered or explicitly exempt`.

### Task 4: drift kontraktu — skrypt i workflow

**Files:**
- Create: `ci/contract_drift.py`
- Create: `.github/workflows/contract-drift.yml`
- Test: `tests/test_contract_drift.py`

**Interfaces:**
- Consumes: `tdkit.docs.latest_tag(lines: list[str]) -> str`, `tdkit.integrators.version_key`, `changelog_items` (Task 3), linia `  CONTRACT_TAG:` (Task 2).
- Produces (w `ci/contract_drift.py`):
  - `pinned_tag(ci_yml: str) -> str`
  - `with_pin(ci_yml: str, tag: str) -> str` — zmienia tylko linię `CONTRACT_TAG`
  - `compare(pinned: str, latest: str) -> Literal["current", "behind", "ahead"]`
  - `refresh_fixture(source: Path, fixture: Path) -> None` — usuwa `fixture` i kopiuje `source` bez `.git` i `.github`
  - `pr_body(changelog: str, pinned: str, latest: str) -> str` — link do CHANGELOG tagu i wszystkie pozycje `Integrators` z wersji `> pinned`, `<= latest`, z tagami
  - `main(argv) -> int` — `ls-remote`, porównanie; `current` → 0; `ahead` → komunikat na stderr, 1; `behind` → clone tagu do katalogu tymczasowego, `with_pin`, `refresh_fixture`, zapis `pr_body` do pliku z `--body-out`, `behind=true`/`tag=` do `$GITHUB_OUTPUT`, 0 (czerwień robi workflow po otwarciu PR-a).

- [ ] **Step 1: Testy** (bez sieci, na tekstach i `tmp_path`):

```python
def test_pin_is_read_and_replaced_alone():     # with_pin zmienia jedną linię, reszta ci.yml bajt w bajt
def test_compare_orders_versions():             # 3.4.1-draft < 3.4.2-draft < 3.5.0-draft
def test_release_after_draft_is_newer():        # compare("v3.4.2-draft", "v3.4.2") == "behind"
def test_pin_ahead_of_latest_fails():           # main z podmienionym ls-remote → 1, brak plików zmienionych
def test_refresh_fixture_removes_stale_files(): # plik obecny tylko w starym fixture znika
def test_pr_body_lists_integrators_between():   # 3.4.1→3.4.2 z fixture: „Nothing to do.” nie jako pozycja; 3.2.0→3.4.2: pozycje 3.3.0 i 3.4.0, bez 3.2.0
```

`ls-remote` i `clone` idą przez jedną funkcję `_git(args: list[str]) -> str`, podmienianą w testach `monkeypatch`.

- [ ] **Step 2:** `uv run pytest tests/test_contract_drift.py -q` → FAIL.
- [ ] **Step 3:** skrypt. Workflow `contract-drift.yml`: `on: schedule: - cron: "30 5 * * *"` + `workflow_dispatch`; `permissions: contents: write, pull-requests: write, actions: write`; kroki: checkout, setup-uv (wersja jak w `ci.yml`), `uv run python ci/contract_drift.py --body-out "$RUNNER_TEMP/body.md"`; gdy `behind`: `git checkout -B contract/latest`, commit `contract: v<stary> → v<nowy>` (autor `tribunedesk-contract-drift`), `git push --force origin contract/latest`, `gh pr create` albo `gh pr edit` (jak w `cms-api-docs.yml` headlinesforge: jeden otwarty PR na gałęzi), `gh workflow run ci.yml --ref contract/latest`, na końcu `echo "::error::contract pin v… is behind v…" && exit 1`.
- [ ] **Step 4:** `uv run pytest tests/test_contract_drift.py -q` → PASS; ruff, pyright czysto.
- [ ] **Step 5:** commit `ci: daily contract drift job opens a bump PR and stays red while behind`. Sprawdzenie na GitHubie po wypchnięciu gałęzi roboczej: `gh workflow run contract-drift.yml --ref <gałąź>` → przy 3.4.2 = najnowszy tag run zielony, „current”. (Pełnej ścieżki „behind” nie da się sprawdzić bez nowego tagu — test `main` z podmienionym `_git` ją pokrywa; pierwsza prawdziwa próba to etap 6.)

### Task 5: evale parytetu

**Files:**
- Create: `evals/scenarios/parity-django.md`, `evals/scenarios/parity-laravel.md`, `evals/scenarios/parity-node.md`
- Modify: `evals/run.py` (setupy `laravel_app`, `node_app`; zestaw `PARITY` sprawdzeń; check `no_local_sources`; wpisy w `SCENARIO`)
- Modify: `evals/README.md` (tabela scenariuszy, wymagania: PHP 8.3 + Composer dla Laravela, Node 22 dla Node)
- Test: `tests/test_eval_runner.py`, `tests/test_project.py`

**Interfaces:**
- Consumes: istniejące `django_blog`, `report_green`, `manifest`, `skill_fired`, `final_message_complete`, `no_secret_in_git`, `env_ignored`, `Run`.
- Produces: `no_local_sources(run: Run) -> tuple[bool, str]` — fałsz, gdy wywołanie `Read`/`Glob`/`Grep` ma ścieżkę wewnątrz `KIT`, albo gdy komenda `Bash` zawiera `tribunedesk-wordpress`, `headlinesforge` lub `src/tdkit` (wywołania przez `TDKIT_CMD` nie liczą się: ścieżka `KIT` w samej komendzie `tdkit` jest dozwolona). `PARITY: dict[str, Check]`: skill fired, final message stands alone, tdkit check ran, report green `[1, 2, 3, 4]` `webhook`, manifest (levels 1–4, webhook, passed 1–4, `contract=CONTRACT`), report and manifest not written by hand, no secret in git, .env ignored, no local sources.

- [ ] **Step 1: Testy.**

```python
# tests/test_eval_runner.py
def test_parity_scenarios_are_registered():          # {"parity-django","parity-laravel","parity-node"} ⊆ SCENARIO, każdy z PARITY
def test_no_local_sources_flags_a_read_of_the_kit(): # Run z Read(KIT/"src/tdkit/docs.py") → False
def test_no_local_sources_allows_tdkit_cmd():        # Bash z '"uv" run --project "<KIT>" tdkit check ...' → True

# tests/test_project.py
def test_readme_has_parity_rows_for_this_minor():
    # każdy z trzech scenariuszy ma wiersz w tabeli „Evals” README z „tdkit X.Y” równym major.minor __version__
```

- [ ] **Step 2:** `uv run pytest tests/test_eval_runner.py tests/test_project.py -q` → FAIL.
- [ ] **Step 3:** Scenariusze: prompt po polsku (django) i angielsku (laravel, node), ten sam sens: „Zbuduj integrację z Tribune Desk taką, jak oficjalna wtyczka WordPress: poziomy 1–4, webhook, plan zatwierdzam z góry” + adres publiczny jak w `django-l12`. Sekcja `## Review`: plan przed kodem, podsumowania etapów, każda reguła z nazwą pliku przewodnika, końcowe podsumowanie z wynikiem `tdkit check` dla poziomów 1–4. Setupy: `laravel_app` = `composer create-project laravel/laravel:^12 project` (minimalny model posta + migracja, commit), `node_app` = Express 5 z `package.json`, plikiem `app.js` i SQLite przez `better-sqlite3` (blog z modelem posta, commit); wersje przypiąć w setupie. `TDKIT_CMD` i `--plugin-dir` bez zmian (kandydat wydania = ten checkout, spec D4). Wpis w README zostaje z Task 6 — test `test_readme_has_parity_rows_for_this_minor` będzie czerwony aż do Task 6; oznaczyć go `xfail(strict=True)` z powodem „wiersze dochodzą w Task 6”, Task 6 zdejmuje znacznik.
- [ ] **Step 4:** `uv run pytest tests/test_eval_runner.py tests/test_project.py -q` → PASS (z jednym xfail); ruff, pyright czysto. Próba sucha bez kosztu: `uv run python evals/run.py parity-node --max-budget-usd 0.01` buduje projekt i pada na budżecie — sprawdza setup.
- [ ] **Step 5:** commit `evals: parity scenarios on Django, Laravel and Node, no local sources`.

### Task 6: wydanie 1.2.0 i pierwsza runda parytetu

**Files:**
- Modify: `src/tdkit/__init__.py`, `plugins/tribunedesk-integration/.claude-plugin/plugin.json`, `plugins/tribunedesk-integration/skills/tribunedesk-integration/SKILL.md` (`@v1.2.0`)
- Modify: `README.md` (sekcje: pokrycie przewodnika, drift kontraktu, tabela „Evals” z trzema wierszami parytetu)
- Modify: `tests/test_project.py` (zdjęcie `xfail`)

- [ ] **Step 1:** podbicie wersji w trzech miejscach; `uv run pytest tests/test_plugin_layout.py tests/test_skill_text.py -q` → PASS.
- [ ] **Step 2: Zgoda ownera na koszt** (szacunek ~10 USD, trzy runy) — zapytać w wiadomości końcowej tury, nie uruchamiać bez niej.
- [ ] **Step 3:** `uv run python evals/run.py parity-django --max-budget-usd 15`, potem `parity-laravel`, `parity-node`. Każdy: sprawdzenia automatyczne + przegląd sekcji „Review”. Czerwony wynik → stop, diagnoza (skill, przewodnik czy scenariusz), raport ownerowi; nie poprawiać skilla w tym zadaniu bez jego słowa.
- [ ] **Step 4:** wiersze w tabeli README (data, `tdkit 1.2`, `v3.4.2-draft`, wynik `tdkit`, przegląd, koszt); zdjąć `xfail`; `uv run pytest tests/test_project.py -q` → PASS.
- [ ] **Step 5:** commit `release: tdkit 1.2.0 (coverage test, contract drift, parity evals)`; wypchnąć gałąź roboczą, CI zielone. Lądowanie (`/ship`, tag `v1.2.0` przed `main`) i aktualizacja Rollout w `projects/tribunedesk-cms-kit/wiki.md` (drift, `SUPPORTED_MINORS`, rytuał parytetu) — dopiero na słowo ownera.

---

## Po etapie 1

Zatrzymanie i podsumowanie dla ownera. Etapy 2 (headlinesforge), 3 (`cms-api`, czyta format `SUPPORTED_MINORS` z Task 1), 4 (`cms-php`), 5 (wtyczka) i 6 (przewodnik 3.5) — osobne plany.
