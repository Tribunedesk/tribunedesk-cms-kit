# Kontrakt najpierw — etap 3: kontrole i tag w `tribunedesk-cms-api` — plan wykonania

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** w publicznym repo `Tribunedesk/tribunedesk-cms-api` PR synchronizacji dokumentacji jest czerwony, gdy wersja, CHANGELOG albo minor się nie zgadzają albo kit nie zna nowego minora, a scalenie na `main` samo stawia adnotowany tag `v<info.version>` — pod tymi samymi warunkami.

**Architecture:** jeden skrypt `.github/scripts/contract_gate.py` (biblioteka standardowa) porównuje drzewo checkoutu z eksportem najnowszego tagu i zwraca decyzję: brak zmiany kontraktu / tag do postawienia / lista problemów. `pr.yml` uruchamia go na PR do `main`, `tag.yml` na push `main` (i ręcznie) i — gdy decyzja to tag — stawia `git tag -a` i pcha go `GITHUB_TOKEN`-em. Strażnik D2c klonuje najnowszy tag kitu i czyta linię `SUPPORTED_MINORS` z `src/tdkit/docs.py`.

**Tech Stack:** Python 3 z obrazu runnera (bez instalacji zależności — jak `cms_api_public_tree.py` w headlinesforge), `unittest`, git, GitHub Actions (`actions/checkout@v6`, runner `ubuntu-26.04` jak `cms-api-docs.yml`).

**Spec:** `docs/specs/2026-11-13-kontrakt-najpierw-automaty-design.md` (repo kitu), D2a, D2c, D1 (droga klasy (a)/(b) przez wersję i CHANGELOG) i sekcja 8, etap 3.

## Stan przed etapem (sprawdzony 16.11)

- Kit `origin/main` `2fd334a`, najnowszy tag `v1.3.0`; `ci/contract-tag` = `v3.4.2-draft`; `src/tdkit/docs.py:27` `SUPPORTED_MINORS = frozenset({(3, 4)})`, a `tests/test_docs.py::test_supported_minors_line_is_machine_readable` pilnuje formatu linii regexem `^SUPPORTED_MINORS = frozenset\(\{(\(\d+, \d+\)(, )?)+\}\)$`. `contract-drift.yml` jest (05:30 UTC, `ls-remote` + PR `contract/latest`). Skill przypina `tdkit` tagiem (`SKILL.md`: `@v1.3.0`).
- headlinesforge `origin/master` `9da895931`: `cms-api-docs.yml` pada bez `CMS_API_DOCS_TOKEN` (D2d) i otwiera/aktualizuje PR `sync/latest` **tokenem PAT** — więc `pull_request` w `cms-api` się na nim uruchomi (blokada dotyczy tylko `GITHUB_TOKEN`). Strażnik API → CHANGELOG wylądował (`858cae33f`). `scripts/cms_api_public_tree.py` **usuwa z repo publicznego każdy plik spoza mapy** poza `.git/`, `.github/` i `SECURITY.md`, `CODEOWNERS`, `.gitignore`.
- `cms-api` `main` `2c1e94b`: `openapi.json` `info.version` = `3.4.2-draft` = najnowszy tag; tagi `v3.2.0-draft` … `v3.4.2-draft` są **lekkie**; brak `.github/`, brak ochrony gałęzi i rulesetów; repo publiczne. Kit też publiczny.
- Nagłówek CHANGELOG: `## 3.4.2-draft – 2026-11-12`; blok `**Integrators:**` z wypunktowaniem (`- Nothing to do.` albo `` - `L1`: … ``).

## Global Constraints

- Wszystko, co dodaje ten etap, leży pod `.github/` — inaczej następna synchronizacja to skasuje.
- Ścieżki kontraktu (D2a): `openapi.json`, `CHANGELOG.md`, `guide/**`, `examples/**`. Zmiana poza nimi (`README.md`, `VERSIONING.md`, `pl/**`, `LICENSE`, `.github/**`) nie wymaga wersji i nie stawia tagu.
- Porządek wersji jak `tdkit.integrators.version_key`: `(major, minor, patch, 0 dla -draft / 1 bez)`; nowa wersja musi być **ostro** większa od najnowszego tagu.
- Punkty „Done when” zbierane jak `tests/test_coverage.py::done_when_points` w kicie: sekcja od `\n## Done when\n` do następnego `\n## `, każda linia zaczynająca się od `- ` (razem z listą po „In read mode, also:”), klucz `(guide/<plik>, tekst)`. Różnica zbiorów względem tagu → `(major, minor)` nowej wersji > tagu.
- Strażnik D2c: gdy `(major, minor)` nowej wersji ≠ najnowszego tagu → najnowszy tag kitu `vX.Y.Z` z `git ls-remote --tags --refs https://github.com/Tribunedesk/tribunedesk-cms-kit`, `git clone --depth 1 --branch <tag>`, regex jak wyżej na `src/tdkit/docs.py`. Brak pary → komunikat `release tdkit that knows X.Y first (tdkit vA.B.C supports …)`. Linia nieczytelna albo brak tagu kitu → **błąd**, nigdy przepuszczenie.
- Tag: adnotowany, `v<info.version>`, wiadomość `Contract v<version>`, autor `github-actions[bot]`; uprawnienia `contents: write` tylko w `tag.yml`, `pr.yml` ma `contents: read`. Żadnego nowego sekretu.
- Sieć: tylko `git ls-remote`/`git clone` publicznego repo kitu, tylko w CI (jak `ci/contract_drift.py` kitu).
- Lokalnie testy skryptu: `python -m unittest discover -s .github/scripts -v` (to nie pytest, hook pełnego suite go nie dotyczy).
- Praca w worktree klonu `C:/Users/czarn/Documents/A_PYTHON/tribunedesk-cms-api` (sklonowany 16.11, czysty `main`), gałąź `ci/contract-gate`. Lądowanie na `main` tylko `/ship` na słowo ownera; żadnego ręcznego tagu.

## Review Focus

1. **PR scalony mimo czerwonego `pr.yml`** (brak ochrony gałęzi): `tag.yml` liczy to samo i pada bez tagu, skill dalej widzi stary tag. Test w Task 2 (`test_decide_changed_without_version_is_a_problem`).
2. **Kit wydany po scaleniu** (tag.yml czerwony na D2c, potem release kitu): ponowny run `tag.yml` przez `workflow_dispatch` stawia tag bez nowego commita. Task 3 (`workflow_dispatch` w `tag.yml`) + weryfikacja w Task 4, krok 3.
3. **Zmiana linii `SUPPORTED_MINORS` w kicie na inny zapis** (np. wieloliniowy): strażnik pada z „cannot read SUPPORTED_MINORS”, nie przepuszcza. Test w Task 1 (`test_parse_supported_minors_rejects_other_forms`).
4. **Patch, który dodaje albo przeredagowuje punkt „Done when”** (dokładnie przypadek 3.4.2): odrzucony z „bump at least the minor”. Test w Task 2 (`test_decide_new_done_when_point_needs_minor`) i weryfikacja na prawdziwej historii w Task 4, krok 1.
5. **Synchronizacja dotyka tylko `pl/**` albo README**: zielono, bez tagu. Test w Task 2 (`test_decide_outside_contract_paths_is_no_change`).

---

## Mapa plików (repo `tribunedesk-cms-api`)

| Plik | Odpowiedzialność |
|---|---|
| `.github/scripts/contract_gate.py` | reguły D2a/D2c na katalogach + cienka warstwa git + CLI |
| `.github/scripts/test_contract_gate.py` | `unittest`: reguły na katalogach tymczasowych, CLI na repo tymczasowym |
| `.github/workflows/pr.yml` | PR do `main`: testy skryptu + `contract_gate.py` |
| `.github/workflows/tag.yml` | push `main` + `workflow_dispatch`: `contract_gate.py`, tag adnotowany |

### Task 1: reguły bez gita

**Files:** Create `.github/scripts/contract_gate.py`, `.github/scripts/test_contract_gate.py`

**Interfaces — Produces:**
- `CONTRACT_PATHS: tuple[str, ...] = ("openapi.json", "CHANGELOG.md", "guide", "examples")`
- `version_key(version: str) -> tuple[int, int, int, int]` — przyjmuje z `v` i bez; `ValueError` na inne.
- `latest_tag(tags: list[str]) -> str | None` — najnowszy `v*` wg `version_key`; obce nazwy pomija.
- `contract_files(root: Path) -> dict[str, bytes]` — ścieżka posix → bajty dla `CONTRACT_PATHS`.
- `done_when_points(root: Path) -> frozenset[tuple[str, str]]` — z `root/guide/*.md`.
- `changelog_problems(changelog: str, version: str) -> list[str]`
- `parse_supported_minors(docs_py: str) -> frozenset[tuple[int, int]]` — `ValueError("cannot read SUPPORTED_MINORS …")`.

- [ ] **Step 1: testy** — `test_version_key_orders_draft_before_release` (`version_key("3.5.0-draft") < version_key("v3.5.0")`, `version_key("3.4.10-draft") > version_key("3.4.9-draft")`), `test_latest_tag_ignores_foreign_names` (`["v3.4.1-draft", "v3.4.2-draft", "latest", "v3.4.2"]` → `"v3.4.2"`), `test_done_when_points_include_read_mode_list` (guide z dwoma punktami, „In read mode, also:” i trzecim, potem `## Next` z `- x` → dokładnie 3 punkty), `test_changelog_needs_heading_and_integrators` (brak `## 3.5.0-draft` → problem z wersją w treści; nagłówek bez `**Integrators:**` → problem; `**Integrators:**` bez punktu przed następnym `## ` → problem; `- Nothing to do.` → `[]`; blok `Integrators` innej wersji się nie liczy), `test_parse_supported_minors_reads_the_kit_line` (`SUPPORTED_MINORS = frozenset({(3, 4), (3, 5)})` → `{(3,4),(3,5)}`; plik z v1.3.0 → `{(3,4)}`), `test_parse_supported_minors_rejects_other_forms` (brak linii; wersja wieloliniowa; `SUPPORTED_MINOR = (3, 4)` → `ValueError`).
- [ ] **Step 2:** `python -m unittest discover -s .github/scripts -v` → FAIL (import).
- [ ] **Step 3:** implementacja w `contract_gate.py`; `changelog_problems` szuka nagłówka regexem `^## {re.escape(version)}(\s|$)`, sekcji do następnego `^## `, linii dokładnie `**Integrators:**` i co najmniej jednej linii `- ` po niej w tej sekcji.
- [ ] **Step 4:** testy → PASS.
- [ ] **Step 5:** commit `ci: contract gate rules (version, CHANGELOG, Done when, SUPPORTED_MINORS)`.

### Task 2: decyzja, warstwa git i CLI

**Files:** Modify `.github/scripts/contract_gate.py`, `.github/scripts/test_contract_gate.py`

**Interfaces — Consumes:** wszystko z Task 1. **Produces:**
- `@dataclass(frozen=True) class Decision: tag: str | None; problems: list[str]` — `tag` tylko gdy `problems == []` i kontrakt się zmienił.
- `decide(head: Path, base: Path, base_tag: str, kit: Callable[[], tuple[str, frozenset[tuple[int, int]]]]) -> Decision` — `kit` wołane tylko przy zmianie `(major, minor)`; zwraca `(tag kitu, minory)`.
- `export_tag(repo: Path, tag: str, dest: Path) -> None` — `git archive <tag> -- <CONTRACT_PATHS istniejące w tagu>` + `tarfile` do `dest`.
- `kit_minors() -> tuple[str, frozenset[tuple[int, int]]]` — `ls-remote` kitu, najnowszy `vX.Y.Z` po krotce liczb, płytki klon do `tempfile.TemporaryDirectory`, `parse_supported_minors`.
- `main(argv: list[str] | None = None) -> int` — `contract_gate.py [--repo DIR]`: problemy na stderr jako `::error::…` i `1`; inaczej `0`, a przy `GITHUB_OUTPUT` dopisuje `tag=<v…>` albo `tag=`. Brak tagów `v*`, nieczytelny `openapi.json` / brak `info.version` → `::error::` i `1`.

- [ ] **Step 1: testy `decide`** (katalogi tymczasowe z `openapi.json`, `CHANGELOG.md`, `guide/1-a.md`; `kit` jako lambda, która w testach „bez minora” rzuca `AssertionError`):
  `test_decide_no_change_is_no_tag` (`Decision(None, [])`),
  `test_decide_outside_contract_paths_is_no_change` (różny `README.md` i `pl/guide/1-a.md`),
  `test_decide_changed_without_version_is_a_problem` (zmieniony `guide/1-a.md`, wersja = tag → problem `changed without a new version`),
  `test_decide_patch_bump_tags` (3.4.2-draft → 3.4.3-draft, sekcja CHANGELOG z `- Nothing to do.` → `tag == "v3.4.3-draft"`),
  `test_decide_new_done_when_point_needs_minor` (nowy punkt + patch → problem `bump at least the minor`),
  `test_decide_new_minor_unknown_to_kit_is_refused` (3.5.0-draft, `kit` → `("v1.3.0", {(3,4)})` → problem zawiera `release tdkit that knows 3.5 first`),
  `test_decide_new_minor_known_to_kit_tags` (`kit` → `{(3,4),(3,5)}` → `tag == "v3.5.0-draft"`),
  `test_decide_older_version_is_a_problem` (3.4.1-draft przy tagu 3.4.2-draft).
- [ ] **Step 2: test CLI na repo tymczasowym** — `test_main_on_repo_writes_tag_output`: `git init`, commit 3.4.2-draft, lekki tag `v3.4.2-draft`, commit 3.4.3-draft z CHANGELOG; `main(["--repo", tmp])` z `GITHUB_OUTPUT` w pliku tymczasowym → `0` i linia `tag=v3.4.3-draft`; `test_main_without_tags_fails` → `1`.
- [ ] **Step 3:** testy → FAIL; implementacja; testy → PASS (`kit_minors` bez testu jednostkowego — sieć; sprawdza go Task 4, krok 2).
- [ ] **Step 4:** commit `ci: contract gate decision and CLI`.

### Task 3: workflowy

**Files:** Create `.github/workflows/pr.yml`, `.github/workflows/tag.yml`

- `pr.yml`: `on: pull_request: branches: [main]` (bez filtra `paths` — skrypt sam rozpoznaje brak zmiany); `permissions: contents: read`; `actions/checkout@v6` z `fetch-depth: 0`, `fetch-tags: true`; kroki `python3 -m unittest discover -s .github/scripts -v` i `python3 .github/scripts/contract_gate.py`. Komentarz nagłówkowy: po co (D2a/D2c, link do specu kitu), że PR `sync/latest` przychodzi z PAT-a headlinesforge, więc to się uruchamia, i że wszystko musi leżeć pod `.github/`.
- `tag.yml`: `on: push: branches: [main]` + `workflow_dispatch`; `permissions: contents: write`; `concurrency: {group: contract-tag, cancel-in-progress: false}`; checkout jak wyżej; krok `id: gate` z `contract_gate.py`; krok `if: steps.gate.outputs.tag != ''`: `git config user.name "github-actions[bot]"`, `user.email "41898282+github-actions[bot]@users.noreply.github.com"`, `git tag -a "$TAG" -m "Contract $TAG"`, `git push origin "refs/tags/$TAG"`. Komentarz: tag stawia tylko ten workflow; po czerwonym D2c i wydaniu kitu → „Run workflow”.

- [ ] **Step 1:** oba pliki, commit `ci: pr.yml and tag.yml (contract gate, annotated tag)`; składnię sprawdza GitHub w kroku 2.
- [ ] **Step 2:** push gałęzi `ci/contract-gate`, PR do `main` (`gh pr create`); `pr.yml` uruchamia się na tym PR-ze i jest **zielony** (zmiana tylko w `.github/` → brak zmiany kontraktu). Odczyt: `gh pr checks`.
- [ ] **Step 3:** commit(y) już na gałęzi; nic na `main`.

### Task 4: weryfikacja na prawdziwej historii (lokalnie, przed lądowaniem)

Na kopiach worktree, bez pushowania czegokolwiek z tych kroków.

- [ ] **Step 1: przypadek 3.4.2.** Klon testowy w scratchpadzie (`git clone` roboczego klonu), `git checkout v3.4.2-draft`, `git tag -d v3.4.2-draft` (najnowszym tagiem zostaje `v3.4.1-draft`) → `python3 <skrypt z gałęzi> --repo <klon testowy>` → `1` i `bump at least the minor` (3.4.2 dodał punkty „Done when” jako patch). Wynik do opisu PR — dowód, że strażnik łapie znany przypadek.
- [ ] **Step 2: D2c z siecią.** W klonie testowym commit podbijający `info.version` na `3.5.0-draft` + sekcja CHANGELOG → `1` i `release tdkit that knows 3.5 first (tdkit v1.3.0 supports 3.4)`; drugi wariant z wersją `3.4.3-draft` i samą zmianą opisu → `0`, `tag=v3.4.3-draft`.
- [ ] **Step 3: lądowanie (tylko na słowo ownera, `/ship`).** Po scaleniu `tag.yml` na `main` zielony i **bez** nowego tagu (`main` = `v3.4.2-draft` w ścieżkach kontraktu): `gh run list --workflow tag.yml`, `git ls-remote --tags origin` bez zmian. Pierwszy prawdziwy tag postawi następna synchronizacja.

### Task 5: dokumentacja w kicie

**Files:** Modify spec `docs/specs/2026-11-13-kontrakt-najpierw-automaty-design.md` (repo kitu) — tabela sekcji 2 nie jest historią, więc tylko krótka „Poprawka po etapie 3” w sekcji 7/8: skrypt pod `.github/` (powód: `cms_api_public_tree.py` kasuje resztę), tagi od teraz adnotowane, wcześniejsze lekkie zostają. Rollout `projects/tribunedesk-cms-kit/wiki.md` (vault) — przez `/checkpoint`, nie ręcznie w tym etapie.

- [ ] **Step 1:** poprawka w specu, commit w kicie `docs(spec): stage 3 notes`.

## Decyzje tego planu (do akceptacji)

- **Tag kitu, nie `main` kitu, dla D2c.** Why: skill uruchamia `tdkit` z tagu przypiętego w `SKILL.md`, a wiki mówi „tag kitu przed tagiem dokumentacji”; `main` z podbitym zbiorem, ale bez tagu, przepuściłby dokumentację, której nikt z użytkowników jeszcze nie umie czytać. Odrzucone: `main` (zadanie tak to nazwało) — przegrywa właśnie tym oknem. Rewizja: gdy kit przestanie przypinać `tdkit` tagiem w `SKILL.md`.
- **Jeden skrypt, jedna decyzja dla `pr.yml` i `tag.yml`, porównanie z eksportem najnowszego tagu (nie z bazą PR-a).** Why: `tag.yml` musi powtórzyć kontrole (brak ochrony gałęzi), a „tag już jest, a treść się zmieniła” wychodzi z tej samej reguły „wersja > tag”. Odrzucone: logika w bashu w YAML-u — nietestowalna lokalnie. Rewizja: brak.
- **Bez wymaganego statusu na `main` w `cms-api`.** Why: tag i tak nie powstanie z czerwonego stanu, a czerwony `tag.yml` przychodzi mailem; ochrona to zmiana ustawień repo, której owner nie zlecił. Odrzucone: required check — wymaga ustawienia repo i nic nie dodaje do gwarancji tagu. Rewizja: pierwszy czerwony `pr.yml` scalony mimo to.
