# Kontrakt najpierw — etap 4: drift kontraktu w `tribunedesk-cms-php` — plan wykonania

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** biblioteka `Tribunedesk/tribunedesk-cms-php` codziennie sama sprawdza, czy jej przypinka kontraktu (`tests/fixtures/contract/VERSION`) jest najnowszym tagiem `tribunedesk-cms-api`; gdy nie jest — buduje gałąź `contract/latest`, otwiera albo aktualizuje jeden PR, uruchamia na nim CI i pozostaje czerwona, póki PR nie wyląduje.

**Architecture:** port `ci/contract_drift.py` kitu na PHP: klasa `ci/ContractDrift.php` (statyczne metody, bez zależności; git wołany przez `proc_open` z tablicą argumentów, wstrzykiwany w testach) i cienki `ci/contract-drift.php` dla CLI. `contract-drift.yml` jest kopią przebiegu z kitu (krok „pin na otwartej gałęzi” → skrypt → push/PR/`gh workflow run ci.yml` → czerwień), `ci.yml` dostaje `workflow_dispatch`. Testy skryptu wchodzą do istniejącego zestawu PHPUnit.

**Tech Stack:** PHP 8.3 (minimum z `composer.json`), PHPUnit 9.6 (już w `require-dev`), git, GitHub Actions (`actions/checkout@v6`, `shivammathur/setup-php@v2`, runner `ubuntu-26.04` jak `ci.yml`), `gh` z obrazu runnera.

**Spec:** `docs/specs/2026-11-13-kontrakt-najpierw-automaty-design.md` (repo kitu): D2b, sekcja 6 (uprawnienia), sekcja 7 (zadanie ledgera `…-wordpress-cms-php-kontrakt-3-4-2` i poprawka „przypinki poza `.github/workflows/`”), sekcja 8 punkt 4. Wzór: kit `.github/workflows/contract-drift.yml`, `ci/contract_drift.py`, `tests/test_contract_drift.py` na `main` (`d1efcfe`).

## Stan przed etapem (sprawdzony 16.11)

- `cms-php` `origin/main` = `6614183` = tag `v1.1.0` (tagi: `v1.0.0`, `v1.1.0`, `ship-lock`). Repo publiczne, `main` bez ochrony, jedyny workflow `ci.yml` (`push: main` + `pull_request`, matrix PHP 8.3/8.5, zbiorczy job `test`). Krok CI `curl … /$(cat tests/fixtures/contract/VERSION)/examples/vectors/webhook-signature.json | cmp -` pilnuje kopii wektorów.
- Przypinka kontraktu żyje w **czterech** miejscach, nie dwóch: `tests/fixtures/contract/VERSION` (`v3.4.1-draft`), `tests/fixtures/contract/webhook-signature.json`, `src/ContractVersion.php` (`TESTED = '3.4.1-draft'`; test `ProtocolUnitsTest::test_contract_version_matches_fixture` wymaga `'v' . TESTED == VERSION`) i 11 linków `https://github.com/Tribunedesk/tribunedesk-cms-api/blob/v3.4.1-draft/…` w tabeli klas `README.md`. Żadne nie leży w `.github/workflows/` — poprawka sekcji 7 jest tu spełniona z natury.
- `cms-api`: najnowszy tag `v3.4.2-draft`; wektory podpisu `v3.4.1-draft` i `v3.4.2-draft` są bajt w bajt równe kopii w `cms-php` (sha256 `99070171…`). Wszystkie kotwice z README istnieją w `v3.4.2-draft`. CHANGELOG 3.4.2: `**Integrators:**` → „Nothing to do.”. Pierwszy run driftu ma więc otworzyć PR `contract: v3.4.1-draft → v3.4.2-draft` z zielonym CI.
- **Ustawienie repo blokuje mechanizm:** `gh api repos/Tribunedesk/tribunedesk-cms-php/actions/permissions/workflow` → `can_approve_pull_request_reviews: false` („Allow GitHub Actions to create and approve pull requests” wyłączone) — `gh pr create` `GITHUB_TOKEN`-em się nie uda. Kit ma to samo ustawienie; jego drift nigdy nie tworzył PR-a (przypinka od etapu 1 aktualna; runy 14–15.11 zielone), więc tego nie złapał. Ustawienia organizacji nie da się odczytać tym tokenem (403).
- Ledger `2026-11-13-tribunedesk-wordpress-cms-php-kontrakt-3-4-2`: kryteria 1–4 (linki README, `TESTED`, `VERSION`, wektory, PHPUnit) to dokładnie zawartość pierwszego PR-a driftu; kryterium „przejrzyj diff przewodnika 3.4.1→3.4.2” pokrywa lista `Integrators` w opisie PR-a („Nothing to do.”).
- Rollout (vault `projects/tribunedesk-cms-php/wiki.md`): tag `vX.Y.Z` = wydanie dla wszystkich (`^1.0`); wtyczka trzyma kopię `src/` (`diff -r` z tagiem `cms-php`) — więc zmiana `src/ContractVersion.php` dociera do wtyczki dopiero przez tag biblioteki i drift `"protocol"` wtyczki (etap 5).

## Global Constraints

- Praca w worktree klonu `C:/Users/czarn/Documents/A_PYTHON/tribunedesk-cms-php` (`git worktree add .claude/worktrees/contract-drift -b ci/contract-drift origin/main`). Lądowanie na `main` tylko `/ship` na słowo ownera; tag biblioteki, zmiana ustawień repo i zamknięcie zadania ledgera — też tylko na słowo ownera.
- Nic z etapu nie trafia do `src/` (wtyczka kopiuje `src/` bajt w bajt). Skrypt w `ci/`, test w `tests/`.
- PHP: `declare(strict_types=1);`, styl repo (klasa `final`, metody statyczne, 4 spacje), bez nowych zależności Composera, `composer.json` bez zmian (test ładuje klasę `require_once`).
- Git tylko przez `proc_open` z **tablicą** argumentów (bez powłoki); niezerowy kod → `RuntimeException` ze stderr gita. Sieć: wyłącznie `git ls-remote --tags --refs` i `git -c core.autocrlf=false clone --quiet --depth 1 --branch <tag>` publicznego `https://github.com/Tribunedesk/tribunedesk-cms-api`, tylko w CLI.
- Porządek wersji jak `tdkit.integrators.version_key`: `[major, minor, patch, 0 dla -draft / 1 bez]`; tag `^v\d+\.\d+\.\d+(-draft)?$`, obce nazwy pomijane.
- Pliki zapisywane z `\n` (`.gitattributes`: `* text eol=lf`); wektory kopiowane bajt w bajt (`copy`).
- Uprawnienia workflowu driftu: `contents: write`, `pull-requests: write`, `actions: write`; `GITHUB_TOKEN`, żadnego sekretu. PR nigdy nie scala się sam.
- Lokalnie: `composer install` w worktree, potem `vendor/bin/phpunit` (zestaw ma kilkadziesiąt testów, hook pełnego suite dotyczy tylko `pytest`).

## Review Focus

1. **Klon tagu na Windows z `core.autocrlf=true`** zamieniłby wektory na CRLF i `cmp` w CI by padł: klon zawsze z `-c core.autocrlf=false`. Test w Task 2 (`test_clone_args_disable_autocrlf`).
2. **Przewodnik zmienia nagłówek, do którego linkuje README** — przepięty link prowadzi donikąd, a CI jest zielone (anty-cel „zieleń bez dowodu”): opis PR-a wymienia każdy link, którego plik albo kotwica nie istnieje w nowym tagu. Test w Task 1 (`test_missing_anchors_lists_gone_headings`).
3. **Ktoś dopisał commit do otwartej gałęzi `contract/latest`**, a tag się nie zmienił: następny run nie przebudowuje gałęzi (`rebuild=false`), dalej czerwony. Test w Task 2 (`test_run_open_pr_at_latest_is_left_alone`).
4. **`ContractVersion.php` w innym zapisie** (np. ktoś zmieni stałą na `TESTED = "…"`): skrypt pada przed zapisaniem czegokolwiek, zamiast przepiąć trzy z czterech miejsc. Test w Task 2 (`test_apply_pin_fails_before_writing_without_tested_constant`).
5. **Przypinka przed najnowszym tagiem** (tag skasowany w `cms-api`): błąd, nic nie zmienione. Test w Task 2 (`test_run_ahead_fails`).

---

## Mapa plików (repo `tribunedesk-cms-php`)

| Plik | Odpowiedzialność |
|---|---|
| `ci/ContractDrift.php` | reguły (wersje, CHANGELOG, kotwice, opis PR), przepięcie czterech miejsc, przebieg CLI z wstrzykiwanym gitem |
| `ci/contract-drift.php` | CLI: `php ci/contract-drift.php --body-out FILE [--open-pr-pin TAG]` |
| `tests/ContractDriftTest.php` | PHPUnit na katalogach tymczasowych i fałszywym gicie |
| `.github/workflows/contract-drift.yml` | 05:30 UTC + `workflow_dispatch`: przebieg D2b |
| `.github/workflows/ci.yml` | + `workflow_dispatch` |
| `README.md` | akapit w „Versioning” o drifcie |

### Task 1: reguły bez gita i bez zapisu

**Files:** Create `ci/ContractDrift.php`, `tests/ContractDriftTest.php`

**Interfaces — Produces** (klasa `TribuneDesk\Ci\ContractDrift`, `final`):
- `REPO_URL = 'https://github.com/Tribunedesk/tribunedesk-cms-api'`
- `versionKey(string $version): array` — `list{int,int,int,int}`, przyjmuje z `v` i bez; `InvalidArgumentException` na inne.
- `latestTag(array $lsRemoteLines): string` — linie `"<sha>\trefs/tags/<tag>"`; `RuntimeException('no v* tag found in …')`, gdy brak.
- `compare(string $pinned, string $latest): string` — `'current' | 'behind' | 'ahead'`.
- `changelogItems(string $changelog): array` — `list<array{version: string, tags: list<string>, action: string}>`, wierne `changelog_items` z `tdkit/integrators.py` (nagłówek `^## (\d+)\.(\d+)\.(\d+)(-draft)?\b`, lista po linii `**Integrators:**`, pozycja `` ^- ((?:`[^`]+`(?:,\s*|\s+)?)+):\s*(.+)$ ``, „Nothing to do.” pomijane).
- `missingAnchors(string $readme, string $tagRoot): array` — `list<string>`: każdy link `…/tribunedesk-cms-api/blob/v<ver>/<ścieżka>[#kotwica]` z README, którego `<ścieżka>` nie ma w `$tagRoot` albo którego kotwicy nie daje żaden nagłówek `#{1,6} ` tego pliku. Kotwica nagłówka jak na GitHubie: `mb_strtolower`, usunąć wszystko poza `\p{L}\p{N}\p{M}`, spacją, `-`, `_`; spacje → `-`.
- `prBody(string $changelog, string $pinned, string $latest, array $missingAnchors): string`

- [ ] **Step 1: testy** — `test_version_key_orders_draft_before_release` (`versionKey('3.5.0-draft') < versionKey('v3.5.0')`, `versionKey('3.4.10-draft') > versionKey('3.4.9-draft')`, `'latest'` → wyjątek); `test_latest_tag_ignores_foreign_names` (linie z `v3.4.1-draft`, `v3.4.2-draft`, `ship-lock`, `v3.4.2` → `'v3.4.2'`; same obce → `RuntimeException`); `test_compare` (trzy przypadki); `test_changelog_items_skip_nothing_to_do` (dwie wersje: jedna z `` - `L1`, `read`: verify `` i `- Nothing to do.`, druga z `` - `L3`: x ``; lista „Integrators” poza blokiem się nie liczy → dokładnie 2 pozycje, najnowsza pierwsza, `tags == ['L1','read']`); `test_pr_body_lists_integrators_between` (pozycje z `> pinned` i `<= latest` tylko; link `REPO_URL/blob/<latest>/CHANGELOG.md`; bez pozycji → `- Nothing to do.`; z `$missingAnchors` → sekcja „Links in README.md that the new tag does not have” z każdym linkiem; bez nich sekcji nie ma); `test_missing_anchors_lists_gone_headings` (tag-katalog z `guide/3-full-content.md` z `## The “read more” box` i `README.md` z `## Errors`; README z linkami `…#the-read-more-box`, `…README.md#errors` → brak; `…#gone` i `…/guide/9-none.md` → oba na liście).
- [ ] **Step 2:** `vendor/bin/phpunit tests/ContractDriftTest.php` → FAIL (brak klasy).
- [ ] **Step 3:** implementacja w `ci/ContractDrift.php`. Treść opisu PR jak `pr_body` kitu, z jedną zmianą akapitu: „This pull request moves `tests/fixtures/contract/` (VERSION and the signature vectors), `ContractVersion::TESTED` and the guide links in README.md to the new tag; its CI shows what the new tag breaks. Landing it does not release the library: a `vX.Y.Z` tag is a separate decision.”
- [ ] **Step 4:** test → PASS.
- [ ] **Step 5:** commit `ci: contract drift rules (versions, Integrators, README anchors)`.

### Task 2: przepięcie, git i przebieg CLI

**Files:** Modify `ci/ContractDrift.php`, `tests/ContractDriftTest.php`; Create `ci/contract-drift.php`

**Interfaces — Consumes:** Task 1. **Produces:**
- `git(array $args): string` — `proc_open(['git', ...$args], …)`; `RuntimeException` przy kodzie ≠ 0.
- `cloneArgs(string $tag, string $dest): array` — `['-c','core.autocrlf=false','clone','--quiet','--depth','1','--branch',$tag,REPO_URL,$dest]`.
- `applyPin(string $repo, string $tagRoot, string $latest): void` — najpierw sprawdza (`src/ContractVersion.php` ma dokładnie jedno `public const TESTED = '<…>';`, `$tagRoot/examples/vectors/webhook-signature.json` istnieje — inaczej `RuntimeException`, nic nie zapisane), potem: `VERSION` = `"$latest\n"`, `copy` wektorów, `TESTED` = `$latest` bez `v`, w README każde `tribunedesk-cms-api/blob/v<ver>/` → `…/blob/$latest/`.
- `run(array $argv, string $repo, callable $git): int` — `$git(array $args): string`. Opcje `--body-out FILE` (wymagana) i `--open-pr-pin TAG`. Przebieg jak `main` kitu: `current` → `behind=false`, `0`; `ahead` → komunikat na stderr, `1`, nic nie zmienione; `behind` i `--open-pr-pin == latest` → `behind=true rebuild=false pinned=… tag=…`, `0`, bez klonu; inaczej klon do katalogu tymczasowego (`sys_get_temp_dir()`, usuwany w `finally`), `missingAnchors` na **nowym** README po `applyPin`, opis PR do `--body-out`, `behind=true rebuild=true pinned=… tag=…`, `0`. Wyjścia dopisywane do pliku z `getenv('GITHUB_OUTPUT')`, gdy jest.
- `ci/contract-drift.php`: `require __DIR__ . '/ContractDrift.php'; exit(ContractDrift::run($argv, dirname(__DIR__), [ContractDrift::class, 'git']));`

- [ ] **Step 1: testy** (repo = kopia `VERSION`, wektorów, `ContractVersion.php` i README w katalogu tymczasowym; fałszywy git zwraca linie `ls-remote` i na `clone` buduje tag-katalog pod ostatnim argumentem, licząc wywołania) — `test_clone_args_disable_autocrlf`; `test_apply_pin_moves_all_four` (VERSION `"v3.4.2-draft\n"`, wektory równe `md5_file` źródła, `TESTED = '3.4.2-draft'`, w README zero `blob/v3.4.1-draft/`, 11 × `blob/v3.4.2-draft/`, reszta README bez zmian); `test_apply_pin_fails_before_writing_without_tested_constant` (`ContractVersion.php` z `TESTED = "3.4.1-draft"` → wyjątek, VERSION i README bajt w bajt jak przed); `test_run_current_changes_nothing` (`0`, `behind=false`, brak klonu); `test_run_ahead_fails` (przypinka `v3.5.0-draft`, tag `v3.4.2-draft` → `1`, pliki bez zmian); `test_run_open_pr_at_latest_is_left_alone` (`0`, `rebuild=false`, brak klonu, pliki bez zmian); `test_run_behind_rebuilds` (`0`, `GITHUB_OUTPUT` zawiera `behind=true`, `rebuild=true`, `pinned=v3.4.1-draft`, `tag=v3.4.2-draft`; body zawiera `v3.4.1-draft` → `v3.4.2-draft`; katalog klonu usunięty).
- [ ] **Step 2:** test → FAIL.
- [ ] **Step 3:** implementacja.
- [ ] **Step 4:** `vendor/bin/phpunit` (cały zestaw biblioteki) → PASS, w tym `test_contract_version_matches_fixture`.
- [ ] **Step 5:** commit `ci: contract drift moves VERSION, vectors, ContractVersion and README links`.

### Task 3: workflowy i README

**Files:** Create `.github/workflows/contract-drift.yml`; Modify `.github/workflows/ci.yml`, `README.md`, `tests/ContractDriftTest.php`

- `ci.yml`: `on:` dostaje `workflow_dispatch:`; komentarz: drift uruchamia nim CI na `contract/latest`, bo PR otwarty `GITHUB_TOKEN`-em nie odpala `pull_request`.
- `contract-drift.yml`: kopia przebiegu kitu (nagłówek-komentarz po angielsku jak w kicie, z dopiskiem, że wydanie biblioteki to osobny tag), z różnicami: `runs-on: ubuntu-26.04`; zamiast `setup-uv`/`uv sync` — `shivammathur/setup-php@v2` z `php-version: '8.3'`, `coverage: none` (bez `composer install`); pin otwartej gałęzi z `git show FETCH_HEAD:tests/fixtures/contract/VERSION`; skrypt `php ci/contract-drift.php --body-out "$RUNNER_TEMP/body.md" --open-pr-pin "$OPEN_PR_PIN"`; `git add -A tests/fixtures/contract src/ContractVersion.php README.md`; `gh workflow run ci.yml --ref "$branch"`; komunikat czerwieni `tests/fixtures/contract/VERSION $PINNED is behind $TAG: land the contract/latest pull request`. Cron `30 5 * * *`, `concurrency: contract-drift`, `cancel-in-progress: false`.
- `README.md` „Versioning”: jedno zdanie — `contract-drift.yml` raz dziennie porównuje `tests/fixtures/contract/VERSION` z najnowszym tagiem kontraktu i otwiera PR `contract/latest`, który przepina wszystkie cztery miejsca; tag biblioteki nie powstaje sam.

- [ ] **Step 1: test** `test_workflow_commits_no_workflow_file` — w `contract-drift.yml` linia `git add` nie zawiera `.github`, a zawiera `tests/fixtures/contract`, `src/ContractVersion.php`, `README.md` (każde miejsce, które `applyPin` zmienia, jest dodawane).
- [ ] **Step 2:** pliki; `vendor/bin/phpunit` → PASS; `php -l` na `ci/*.php`.
- [ ] **Step 3:** commit `ci: contract-drift.yml and workflow_dispatch for CI`; push `ci/contract-drift`, PR do `main` (`gh pr create`, opis po polsku z linkiem do specu); CI PR-a zielone na 8.3 i 8.5 (`gh pr checks`). YAML sprawdza GitHub dopiero przy pierwszym runie po lądowaniu (workflow musi być na gałęzi domyślnej) — patrz Task 4 krok 3.

### Task 4: weryfikacja na prawdziwym stanie, potem uruchomienie

- [ ] **Step 1: lokalnie, z siecią, bez pushowania.** Kopia worktree w scratchpadzie (`git clone` worktree), `GITHUB_OUTPUT` na plik w scratchpadzie, `php ci/contract-drift.php --body-out body.md` → `0`; `behind=true`, `rebuild=true`, `pinned=v3.4.1-draft`, `tag=v3.4.2-draft`; `git diff --stat` = dokładnie 3 pliki (`VERSION`, `ContractVersion.php`, `README.md`; wektory bez zmian, bo równe); body: „Nothing to do.”, bez sekcji brakujących linków; `git ls-files --eol tests/fixtures/contract` → `w/lf`; `vendor/bin/phpunit` w kopii → PASS. Drugi run z `--open-pr-pin v3.4.2-draft` na świeżej kopii → `rebuild=false`. Wyniki do opisu PR-a.
- [ ] **Step 2: ustawienie repo (na słowo ownera).** `gh api -X PUT repos/Tribunedesk/tribunedesk-cms-php/actions/permissions/workflow -f default_workflow_permissions=read -F can_approve_pull_request_reviews=true`; odczyt GET → `true`. Jeśli PUT zwróci 409/403 (polityka organizacji) — owner włącza to w ustawieniach organizacji `Tribunedesk` → Actions → General; bez tego krok 3 nie przejdzie.
- [ ] **Step 3: lądowanie i pierwszy run (na słowo ownera).** `/ship` gałęzi; `gh workflow run contract-drift.yml -R Tribunedesk/tribunedesk-cms-php`; oczekiwane: run **czerwony** z `::error::… v3.4.1-draft is behind v3.4.2-draft`, PR `contract: v3.4.1-draft → v3.4.2-draft` otwarty z `contract/latest`, run `ci.yml` (event `workflow_dispatch`) na tej gałęzi zielony i widoczny w `gh pr checks`. Drugi ręczny run → czerwony, ten sam PR, bez nowego force-pusha (`rebuild=false`).
- [ ] **Step 4: domknięcie (każde osobno na słowo ownera).** Lądowanie PR-a `contract/latest` przez `/ship` → następny run driftu zielony („is the newest tag”). Potem: zamknięcie ledgera `2026-11-13-tribunedesk-wordpress-cms-php-kontrakt-3-4-2` (`/ledger close … done`), decyzja o tagu biblioteki (`v1.1.1`: zmiana `TESTED` to nie zmiana zachowania — patch), które odblokowuje drift `"protocol"` wtyczki w etapie 5.

### Task 5: dokumentacja

- [ ] **Step 1:** spec w kicie, sekcja 7 — „Poprawka po etapie 4”: przypinka `cms-php` to cztery miejsca (VERSION, wektory, `ContractVersion::TESTED`, linki README) i drift przepina wszystkie; skrypt w PHP (`ci/ContractDrift.php`); mechanizm wymaga ustawienia „Allow GitHub Actions to create … pull requests” w każdym repo konsumenta (kit i wtyczka też). Commit w kicie `docs(spec): kontrakt najpierw - poprawka po etapie 4`.
- [ ] **Step 2:** Rollout `projects/tribunedesk-cms-php/wiki.md` (vault): akapit o `contract-drift.yml` zamiast zapowiedzi „etap 4 doda tu job driftu” — przez `/checkpoint` na końcu sesji wykonania.

## Decyzje tego planu (do akceptacji)

- **Drift przepina cztery miejsca, nie dwa ze specu (VERSION + wektory).** Why: `test_contract_version_matches_fixture` czyni PR z samym VERSION czerwonym z konstrukcji, a stare linki README to dokładnie problem zadania ledgera, które drift ma zastąpić — przy dwóch miejscach każde podbicie wymagałoby ręcznego commita, czyli „pamięci sesji”. Odrzucone: tylko VERSION + wektory — PR zawsze czerwony, człowiek dopisuje resztę. Odrzucone: usunąć `ContractVersion` — zmiana publicznego API biblioteki (major) dla wygody automatu. Rewizja: gdy pojawi się piąte miejsce z wersją kontraktu (test z Task 3 tego nie złapie — trzeba dopisać do `applyPin`).
- **Skrypt w PHP, testy w PHPUnit biblioteki.** Why: repo nie ma Pythona; testy driftu biegną w tym samym CI, które już jest, na tej samej wersji PHP. Odrzucone: kopia `contract_drift.py` z kitu — importuje `tdkit`, więc trzeba by go przepisać i tak, plus drugi runner testów w repo PHP. Odrzucone: bash w YAML-u — nietestowalny lokalnie. Rewizja: gdy wtyczka (etap 5, też PHP) dostanie ten sam skrypt — rozważyć jedną wspólną klasę zamiast kopii.
- **Zepsute kotwice README → sekcja w opisie PR-a, nie czerwony check.** Why: CI nie ma dostępu do drzewa tagu bez sieci w testach, a zmiana nagłówka przewodnika to rzadkość; człowiek czyta opis przed `/ship`. Odrzucone: krok CI sprawdzający kotwice przy każdym PR-ze — sieć w każdym runie dla rzadkiego przypadku. Rewizja: pierwszy wylądowany PR z martwym linkiem.
- **Lądowanie PR-a driftu nie stawia tagu biblioteki.** Why: tag `vX.Y.Z` to wydanie dla wszystkich (`^1.0`), a zasada lądowania mówi „tag tylko na słowo ownera”. Odrzucone: tag automatyczny po lądowaniu — wydanie bez człowieka. Rewizja: brak.
