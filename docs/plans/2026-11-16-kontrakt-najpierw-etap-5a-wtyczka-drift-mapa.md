# Kontrakt najpierw — etap 5a: drift przypinek i mapa funkcji w `tribunedesk-wordpress` — plan wykonania

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** wtyczka `Tribunedesk/tribunedesk-wordpress` codziennie sama sprawdza, czy `"contract"` i `"protocol"` z `tribunedesk.json` to najnowsze tagi `tribunedesk-cms-api` i `tribunedesk-cms-php`; gdy nie — buduje gałąź `contract/latest`, otwiera albo aktualizuje jeden PR, uruchamia na nim CI i zostaje czerwona, póki PR nie wyląduje. Do tego mapa funkcji `docs/contract-map.json` z testem PHPUnit: każda klasa `src/WordPress/*.php` wskazuje sekcję przewodnika (z kopii `tests/contract/guide/`) albo ma jawny wpis `wp_only`.

**Architecture:** port `ci/ContractDrift.php` z `cms-php` (`0d20fcd`, z poprawką kroku `open`) rozszerzony z jednej przypinki na dwie, liczone razem w jednym przebiegu: kontrakt (manifest, `tests/contract/{openapi.json,article-delivered.json,guide/}`, linki README) i biblioteka (manifest, `src/Protocol` = `src/` tagu). Wspólne liczenie kotwic Markdown w `ci/GuideAnchors.php`, używane przez drift i test mapy. Testy w istniejącym zestawie PHPUnit wtyczki (wp-env), drift na fałszywym gicie.

**Tech Stack:** PHP 8.3 (minimum z `composer.json`), PHPUnit 9.6 + yoast polyfills (już w `require-dev`), wp-env jak w `plugin-ci.yml`, git, GitHub Actions (`actions/checkout@v6`, `shivammathur/setup-php@v2`, runner `ubuntu-26.04`), `gh` z obrazu runnera.

**Spec:** `docs/specs/2026-11-13-kontrakt-najpierw-automaty-design.md` (repo kitu): D1 (mapa funkcji), D2b (przypinki wtyczki), sekcja 6, sekcja 7 (ledger `…-wordpress-kontrakt-3-4-2`, poprawki po etapach 1, 3, 4), sekcja 8 punkt 5. Wzór: `Tribunedesk/tribunedesk-cms-php` `main` `0d20fcd`: `.github/workflows/contract-drift.yml`, `ci/ContractDrift.php`, `ci/contract-drift.php`, `tests/ContractDriftTest.php`. Etap 5b (WP-CLI `wp td …` i job `tdkit check`, przypinka `TDKIT_TAG`) — osobny plan, po tym.

## Stan przed etapem (sprawdzony 16.11)

- Wtyczka `origin/main` = `538a3af` (2.3.0; tag `v2.3.0` jest, manifest klientów nie opublikowany). `tribunedesk.json`: `{"contract": "3.4.1-draft", "protocol": "1.1.0", "levels": [1, 2, 3, 4], "delivery": "webhook", "cms": "wordpress"}` — **`protocol` to już 1.1.0, nie 1.0.0**. `src/Protocol` == `src/` tagu `cms-php` `v1.1.0` (diff pusty); względem `v1.1.1` różni się tylko `ContractVersion::TESTED` (`3.4.1-draft` → `3.4.2-draft`).
- Najnowsze tagi: `cms-api` `v3.4.2-draft` (CHANGELOG 3.4.2 `Integrators`: „Nothing to do.”), `cms-php` `v1.1.1`, kit `v1.3.0`.
- **Przypinki są sprzężone testem:** `tests/test-contract.php::test_version_names_a_tag` wymaga `manifest.contract == openapi info.version == ContractVersion::TESTED`. PR podnoszący sam kontrakt (3.4.2, `TESTED` 3.4.1) i PR podnoszący samą bibliotekę (1.1.1, `TESTED` 3.4.2 przy kontrakcie 3.4.1) byłyby **oba czerwone**. Stąd jedna gałąź na obie przypinki (odstępstwo od „gałąź `protocol/latest`” z D2b — patrz decyzja niżej).
- `plugin-ci.yml`: `push: main` + `pull_request`, **bez `workflow_dispatch`**; krok „Kontrakt z otagowanej wersji” robi `curl | cmp` dla `openapi.json` i `examples/payloads/article-delivered.json`; krok „Kopia biblioteki z tagu” robi `diff -r` `src/` tagu z `src/Protocol`; PHPUnit w wp-env na PHP 8.3 i 8.5; zbiorczy check `test` (wymagany ochroną `main`: liniowa historia, także admin).
- `tests/contract/`: `.gitattributes` (`* -text`), `article-delivered.json`, `openapi.json` — **bez `guide/`**. `.gitattributes` w korzeniu: `/src/Protocol/** text eol=lf`.
- README wtyczki: linki `tribunedesk-cms-api/tree/v3.4.1-draft/guide` (l. 31) i `…/blob/v3.4.1-draft/openapi.json` (l. 32) — drift je przepina.
- Ustawienie repo „Allow GitHub Actions to create and approve pull requests”: **włączone** (`can_approve_pull_request_reviews: true`, 16.11) — `gh pr create` `GITHUB_TOKEN`-em zadziała.
- `WP_CLI::add_command`: brak (tylko sprawdzenie stałej `WP_CLI` w `MediaMetaSync`) — etap 5b.
- Rollout (vault `projects/tribunedesk-wordpress/wiki.md`): **push `main` niczego nie publikuje** (tylko CI); wydanie = tag `vX.Y.Z` (`release.yml`, ZIP z `headlinesforge-receiver.php uninstall.php readme.txt src assets languages LICENSE` — bez `ci/`, `docs/`, `tests/`), publikacja = `Publish manifest`; repo publiczne, PR-y scala owner. Zdanie specu „push `main` wtyczki = wydanie” (D2e) nie odpowiada wiki. Podbicie `src/Protocol` z PR-a driftu dociera do klientów dopiero z następnym wydaniem (wersja + changelog to osobna decyzja).
- Ledger `2026-11-13-tribunedesk-wordpress-kontrakt-3-4-2`: kryteria 1–4 to zawartość pierwszego PR-a driftu (manifest, kopie, linki README, PHPUnit na 8.3/8.5); spec §7: zadanie zamyka się po scaleniu tego PR-a (na słowo ownera).

## Decyzja: jedna gałąź `contract/latest` na `"contract"` i `"protocol"`

- **Why:** test spina kontrakt z `ContractVersion::TESTED` z kopii biblioteki; osobne PR-y byłyby czerwone z powodu kolejności, nie z powodu realnej niezgodności — fałszywa czerwień, a dwa PR-y trzeba by scalać w jednym ruchu. Jeden PR mówi prawdę: zielony, gdy najnowsze tagi do siebie pasują; czerwony, gdy najnowsza biblioteka nie jest jeszcze testowana na najnowszym kontrakcie — i opis PR-a mówi wtedy wprost „czeka na tag `cms-php` z `TESTED = X`”.
- **Odrzucone: dwie gałęzie z D2b + poluzowanie testu.** Test jest jedynym dowodem, że `src/Protocol` testowano na kontrakcie, który wtyczka deklaruje; luzowanie go dla wygody automatu to anty-cel specu.
- **Rewizja:** gdy biblioteka zacznie wychodzić częściej niż kontrakt, a jej PR-y będą czekać na niezwiązany tag kontraktu — rozdzielić gałęzie i przenieść sprzężenie do opisu PR-a.

## Global Constraints

- Praca w worktree klonu `C:/Users/czarn/Documents/A_PYTHON/tribunedesk-wordpress`: `git worktree add .claude/worktrees/contract-drift -b ci/contract-drift origin/main`. PR do `main` scala owner (`/ship` na jego słowo); tag wtyczki, `Publish manifest`, zamknięcie zadania ledgera — tylko na słowo ownera.
- Nic z etapu nie trafia do `src/` ani do ZIP-a wydania: skrypty w `ci/`, mapa w `docs/`, testy w `tests/`.
- PHP: `declare(strict_types=1);`, klasa `final`, metody statyczne, 4 spacje, bez nowych zależności Composera. Klasy z `ci/` testy ładują `require_once` (namespace `TribuneDesk\Ci`, bez autoloadu).
- Git tylko przez `proc_open` z tablicą argumentów (bez powłoki); niezerowy kod → `RuntimeException` ze stderr. Sieć wyłącznie w CLI: `git ls-remote --tags --refs` i `git -c core.autocrlf=false clone --quiet --depth 1 --branch <tag>` publicznych `https://github.com/Tribunedesk/tribunedesk-cms-api` i `https://github.com/Tribunedesk/tribunedesk-cms-php`.
- Wersje: tag kontraktu `^v\d+\.\d+\.\d+(-draft)?$`, tag biblioteki `^v\d+\.\d+\.\d+$`; porządek `[major, minor, patch, 0 dla -draft / 1 bez]`; obce nazwy (`ship-lock`) pomijane. W manifeście wersje **bez** `v`.
- `tribunedesk.json` zmieniany podmianą samej wartości (`"contract": "…"`, `"protocol": "…"`), reszta bajtów bez zmian; kopie z tagów kopiowane bajt w bajt (`copy`), katalogi (`tests/contract/guide`, `src/Protocol`) czyszczone przed kopią, żeby plik usunięty w tagu zniknął i tu.
- Workflow driftu: `GITHUB_TOKEN`, `contents: write`, `pull-requests: write`, `actions: write`; żadnego sekretu; nie commituje nic pod `.github/workflows/`. PR nigdy nie scala się sam.
- Lokalnie: testy driftu i mapy bez WordPressa — `php vendor/bin/phpunit --no-configuration tests/test-contract-drift.php` (po `composer install` w worktree); cały zestaw w wp-env (`npx @wordpress/env start` + komendy z `plugin-ci.yml`) albo w CI gałęzi.

## Review Focus

1. **Nagłówek w bloku kodu** (`# first poll: …` w `guide/4-media-library.md`) nie jest kotwicą — mapa wskazująca go musi być czerwona. Test w Task 1 (`test_anchors_skip_fenced_code`).
2. **Przewodnik zmienia nagłówek, który wskazuje mapa albo README** — PR driftu wypisuje te wpisy i linki w opisie (mapa i tak czerwieni się w CI, README nie). Test w Task 3 (`test_pr_body_lists_missing_anchors`).
3. **Najnowsza biblioteka nie jest testowana na najnowszym kontrakcie** (nowy tag `cms-api`, `cms-php` jeszcze bez wydania) — PR jest czerwony i opis to mówi. Test w Task 3 (`test_pr_body_warns_when_protocol_lags_contract`).
4. **Ktoś dopisał commit do otwartej `contract/latest`, a żaden tag się nie zmienił** — run nie przebudowuje gałęzi, dalej czerwony. Test w Task 4 (`test_run_open_pr_at_latest_is_left_alone`); a gdy zmienił się tylko jeden z tagów — przebudowa (`test_run_rebuilds_when_one_tag_moved`).
5. **Klon tagu na Windows z `core.autocrlf=true`** zmieniłby bajty kopii i `cmp`/`diff -r` w CI by padł. Test w Task 4 (`test_clone_args_disable_autocrlf`).

---

## Mapa plików (repo `tribunedesk-wordpress`)

| Plik | Odpowiedzialność |
|---|---|
| `ci/GuideAnchors.php` | kotwice nagłówków Markdown jak na GitHubie |
| `ci/ContractDrift.php` | wersje, CHANGELOG, opis PR-a, przepięcie obu przypinek, przebieg z wstrzykiwanym gitem |
| `ci/contract-drift.php` | CLI: `php ci/contract-drift.php --body-out FILE [--open-pr-manifest FILE]` |
| `tests/contract/guide/*.md` | kopia `guide/` tagu z `"contract"` (bajt w bajt) |
| `docs/contract-map.json` | mapa funkcji (D1) |
| `tests/test-guide-anchors.php`, `tests/test-contract-map.php`, `tests/test-contract-drift.php` | PHPUnit (kotwice i drift bez WordPressa) |
| `.github/workflows/contract-drift.yml` | 05:30 UTC + `workflow_dispatch`: przebieg D2b |
| `.github/workflows/plugin-ci.yml` | + `workflow_dispatch`, kontrakt z klonu tagu z `guide/` |
| `README.md` | akapit o drifcie i mapie |

### Task 1: kopia `guide/` i kotwice

**Files:** Create `ci/GuideAnchors.php`, `tests/test-guide-anchors.php`, `tests/contract/guide/` (5 plików z `v3.4.1-draft` — przypinka się tu nie zmienia). Modify `.github/workflows/plugin-ci.yml`.

**Interfaces — Produces** (`TribuneDesk\Ci\GuideAnchors`, `final`):
- `slug(string $heading): string` — GitHub: małe litery, usuń wszystko poza literami, cyframi, `_`, `-`, spacją; spacje → `-` (en dash znika, zostawiając `--`).
- `anchors(string $markdown): list<string>` — nagłówki `#`…`######` poza blokami ```` ``` ````, powtórzenia z sufiksem `-1`, `-2`.

- [ ] **Step 1: testy** w `tests/test-guide-anchors.php` (klasa `Test_Guide_Anchors extends \PHPUnit\Framework\TestCase`, `require_once dirname(__DIR__) . '/ci/GuideAnchors.php'` — bez WordPressa):
  - `test_slug_matches_github`: `'The “read more” box'` → `the-read-more-box`; `'Level 1 – Article delivery'` → `level-1--article-delivery`; `'Conflicts and base_version'` → `conflicts-and-base_version`; `'SEO, author and language'` → `seo-author-and-language`.
  - `test_anchors_skip_fenced_code`: Markdown z `## Sync` i blokiem ```` ``` ```` zawierającym `# first poll` → `['sync']`.
  - `test_anchors_number_duplicates`: dwa `## Done when` → `['done-when', 'done-when-1']`.
- [ ] **Step 2:** `php vendor/bin/phpunit --no-configuration tests/test-guide-anchors.php` → FAIL (brak klasy).
- [ ] **Step 3:** zaimplementuj `GuideAnchors`; skopiuj `guide/*.md` z `git -c core.autocrlf=false clone --depth 1 --branch v3.4.1-draft …cms-api` do `tests/contract/guide/`.
- [ ] **Step 4:** testy PASS; `diff -r <klon>/guide tests/contract/guide` pusty.
- [ ] **Step 5:** `plugin-ci.yml`: dodaj `workflow_dispatch:` do `on:`; krok „Kontrakt z otagowanej wersji” zamień na jeden klon (`git -c core.autocrlf=false clone -q --depth 1 --branch "v$contract" https://github.com/Tribunedesk/tribunedesk-cms-api /tmp/api`) + `cmp /tmp/api/openapi.json tests/contract/openapi.json` + `cmp /tmp/api/examples/payloads/article-delivered.json tests/contract/article-delivered.json` + `diff -r /tmp/api/guide tests/contract/guide`. Komentarz kroku: kopia `guide/` służy mapie funkcji.
- [ ] **Step 6: commit** `test(contract): kopia guide/ z tagu kontraktu, kotwice jak na GitHubie`.

### Task 2: mapa funkcji `docs/contract-map.json` i jej test

**Files:** Create `docs/contract-map.json`, `tests/test-contract-map.php` (`Test_Contract_Map extends WP_UnitTestCase`, `require_once` `ci/GuideAnchors.php`).

**Interfaces — Consumes:** `GuideAnchors::anchors`. **Produces:** format mapy, który czyta etap 6:
`{"classes": [{"class": "AuthorResolver", "guide": "3-full-content.md#seo-author-and-language"}, {"class": "Updater", "wp_only": "self-update of the plugin from the Tribune Desk manifest"}]}` — `class` = nazwa pliku `src/WordPress/<class>.php` bez `.php`; `guide` = plik w `tests/contract/guide/` + `#` + kotwica; dokładnie jedno z `guide` / `wp_only`; `wp_only` niepusty, po angielsku (jak reszta repo).

- [ ] **Step 1: testy** (`Test_Contract_Map`):
  - `test_every_class_has_an_entry` — `glob(src/WordPress/*.php)` minus klasy z mapy = `[]` (komunikat wymienia brakujące i mówi: „dopisz `guide` albo `wp_only` w docs/contract-map.json”).
  - `test_every_entry_names_a_class` — klasy z mapy minus pliki = `[]`.
  - `test_entry_has_guide_xor_wp_only` i `test_no_duplicate_classes`.
  - `test_guide_points_at_a_heading_of_the_pinned_guide` — dla każdego `guide`: plik istnieje w `tests/contract/guide/`, kotwica ∈ `GuideAnchors::anchors(plik)`; komunikat podaje klasę, wpis i wersję z manifestu.
- [ ] **Step 2:** FAIL (brak mapy).
- [ ] **Step 3: wypełnij mapę** dla 31 klas. Propozycja (implementer weryfikuje każdą z docblockiem klasy i treścią sekcji; klasa mieszająca (b) i (c) dostaje wpis tej części, która jest kontraktem, a różnicę zapisuje w opisie PR-a — to materiał dla etapu 6):

  | Klasa | Wpis |
  |---|---|
  | RestEndpoint | `1-article-delivery.md#article-delivery-webhook` |
  | PostWriter | `1-article-delivery.md#fields-of-the-request` |
  | WriteResult | `1-article-delivery.md#fields-of-your-answer` (sprawdzić: może `wp_only` jako obiekt wewnętrzny) |
  | Sanitizer | `1-article-delivery.md#the-html-body` |
  | MediaHandler, ImageHosts | `1-article-delivery.md#where-images-come-from` |
  | PublishNotifier, PublishedUrlsClient, Backfill | `2-link-back.md#reporting-the-published-address` |
  | SocialQueueFlag | `2-link-back.md#keeping-a-post-off-facebook` |
  | LinkResolver | `3-full-content.md#internal-links` |
  | Backlinks, ReadMore | `3-full-content.md#the-read-more-box` |
  | AuthorResolver, SeoMeta, Language | `3-full-content.md#seo-author-and-language` |
  | ProvenanceMeta | `3-full-content.md#the-ai-label` |
  | CmsSync | `4-media-library.md#the-sync-cycle` |
  | CmsResync | `4-media-library.md#cursors-and-expiry` |
  | MediaMetaSync | `4-media-library.md#conflicts-and-base_version` |
  | MediaPush | `4-media-library.md#sending-new-files` |
  | CmsDeletions | `4-media-library.md#deletions` |
  | CmsBackfill | `4-media-library.md#historical-import` |
  | CmsSettingsScreen | sprawdzić: `#held-batches` / `#settings` albo `wp_only` (ekran admina) |
  | CmsApiClient | `wp_only`: HTTP transport over the WordPress HTTP API; the routes it calls are mapped by their callers |
  | Activator, Settings, DeliveriesLog, Hooks, Updater, UpdateManifest | `wp_only` (aktywacja i migracje; ekran ustawień; log dostaw w adminie; nazwy filtrów WP; samoaktualizacja ×2) |
- [ ] **Step 4:** testy PASS w wp-env (`--filter Test_Contract_Map`).
- [ ] **Step 5: commit** `feat(contract): mapa funkcji wtyczki na przewodnik (D1) z testem`.

### Task 3: reguły driftu bez gita i bez zapisu

**Files:** Create `ci/ContractDrift.php`, `tests/test-contract-drift.php` (`Test_Contract_Drift extends \PHPUnit\Framework\TestCase`, `require_once` obu klas z `ci/`).

**Interfaces — Produces** (`TribuneDesk\Ci\ContractDrift`, `final`; port z `cms-php` tam, gdzie nazwa się zgadza):
- `CONTRACT_REPO`, `PROTOCOL_REPO` — adresy dwóch repo.
- `versionKey(string $version): array`, `latestTag(array $lsRemoteLines, string $pattern): string`, `compare(string $pinned, string $latest): string` (`current|behind|ahead`), `changelogItems(string $changelog): array` — jak w `cms-php` (+ wzorzec tagu jako argument `latestTag`).
- `testedContract(string $contractVersionPhp): string` — wartość `TESTED` z `src/ContractVersion.php` tagu; `RuntimeException`, gdy nie ma jednej stałej.
- `prBody(array $moves, string $changelog, ?string $testedByProtocol, array $missingAnchors): string` — `$moves` = `['contract' => [stary, nowy]?, 'protocol' => [stary, nowy]?]` (wersje bez `v`).
- `title(array $moves): string` — np. `contract: 3.4.1-draft → 3.4.2-draft, protocol: 1.1.0 → 1.1.1`; tylko przypinki, które się ruszają.

- [ ] **Step 1: testy:** `test_version_key_orders_draft_before_release`, `test_latest_tag_ignores_foreign_names` (`ship-lock`, `v1.2.0^{}` pominięte; wzorzec biblioteki odrzuca `-draft`), `test_compare`, `test_changelog_items_skip_nothing_to_do`, `test_title_names_only_moving_pins`, `test_pr_body_lists_integrators_between` (pozycje z wersji `> stary` i `<= nowy`, „Nothing to do.” gdy brak), `test_pr_body_links_protocol_compare` (`…/tribunedesk-cms-php/compare/v1.1.0...v1.1.1`), `test_pr_body_warns_when_protocol_lags_contract` (`testedByProtocol` = `3.4.2-draft`, nowy kontrakt `3.5.0-draft` → akapit „czeka na tag cms-php testowany na 3.5.0-draft; do tego czasu PR jest czerwony na `test_version_names_a_tag`”), `test_pr_body_lists_missing_anchors` (sekcja z linkami README i wpisami mapy), `test_tested_contract_reads_constant`.
- [ ] **Step 2:** FAIL. **Step 3:** implementacja. **Step 4:** PASS (`php vendor/bin/phpunit --no-configuration tests/test-contract-drift.php`).
- [ ] **Step 5: commit** `ci(contract): reguły driftu dwóch przypinek`.

### Task 4: przepięcie i przebieg z wstrzykiwanym gitem

**Files:** Modify `ci/ContractDrift.php`, `tests/test-contract-drift.php`; Create `ci/contract-drift.php` (3 linie jak w `cms-php`).

**Interfaces — Produces:**
- `git(array $args): string`, `cloneArgs(string $repoUrl, string $tag, string $dest): array` (`['-c','core.autocrlf=false','clone','--quiet','--depth','1','--branch',$tag,$repoUrl,$dest]`).
- `applyContract(string $repo, string $tagRoot, string $latest): void` — manifest `"contract"`, `tests/contract/openapi.json`, `tests/contract/article-delivered.json` (z `examples/payloads/`), `tests/contract/guide/` (wyczyść `*.md`, skopiuj), linki README `#(tribunedesk-cms-api/(?:blob|tree)/)v\d+\.\d+\.\d+(?:-draft)?/#`. Brak pliku w tagu → `RuntimeException` **przed** zapisem czegokolwiek.
- `applyProtocol(string $repo, string $tagRoot, string $latest): void` — manifest `"protocol"`, `src/Protocol` = `src/` tagu (wyczyść, skopiuj).
- `missingAnchors(string $repo): array` — po przepięciu: linki README z kotwicą do `guide/*.md` i wpisy mapy, których kotwic nie ma w nowej kopii.
- `run(array $argv, string $repo, callable $git): int` — `--body-out FILE` (wymagany), `--open-pr-manifest FILE` (opcjonalny: `tribunedesk.json` z otwartej `contract/latest`). Wynik do `$GITHUB_OUTPUT`: `behind`, `rebuild`, `title`. Obie przypinki aktualne → `behind=false`, 0. Któraś przed tagiem → 1, nic nie zmienione. Manifest otwartego PR-a ma oba najnowsze → `behind=true rebuild=false`, 0. Inaczej przepina, co jest w tyle, pisze opis → `behind=true rebuild=true`, 0.

- [ ] **Step 1: testy** (katalog tymczasowy z minimalną wtyczką: manifest, `tests/contract/…`, `src/Protocol/ContractVersion.php`, README, mapa; fałszywy git zwraca linie `ls-remote` i „klonuje” z przygotowanych katalogów): `test_clone_args_disable_autocrlf`, `test_apply_contract_moves_manifest_copies_guide_and_links` (plik usunięty w tagu znika z `tests/contract/guide`; reszta bajtów manifestu bez zmian), `test_apply_contract_fails_before_writing_without_sample`, `test_apply_protocol_replaces_src_protocol`, `test_run_current_changes_nothing`, `test_run_ahead_fails`, `test_run_open_pr_at_latest_is_left_alone`, `test_run_rebuilds_when_one_tag_moved` (otwarty PR ma najnowszy kontrakt, ale starą bibliotekę), `test_run_behind_moves_both` (dzisiejszy stan: 3.4.1→3.4.2 i 1.1.0→1.1.1, tytuł z obiema), `test_run_fails_without_changelog_in_tag`, `test_workflow_passes_the_manifest_only_with_an_open_pull_request` i `test_workflow_commits_no_workflow_file` (czytają `contract-drift.yml` z Task 5 jak w `cms-php` — dopisz je w Task 5, jeśli tu pliku jeszcze nie ma).
- [ ] **Step 2:** FAIL. **Step 3:** implementacja. **Step 4:** PASS.
- [ ] **Step 5:** próba na żywo w worktree, bez commitu: `php ci/contract-drift.php --body-out /tmp/body.md` → `behind=true rebuild=true`, `git status` pokazuje manifest, `tests/contract/**`, `src/Protocol/ContractVersion.php`, README; `body.md` ma tytuł z obiema przypinkami i „Nothing to do.”. Potem `git checkout -- . && git clean -fd tests/contract`.
- [ ] **Step 6: commit** `ci(contract): przepięcie kontraktu i biblioteki z przebiegiem CLI`.

### Task 5: workflow, README, CI na gałęzi

**Files:** Create `.github/workflows/contract-drift.yml`; Modify `README.md`, `tests/test-contract-drift.php` (dwa testy workflowu, jeśli nie weszły w Task 4).

- [ ] **Step 1:** `contract-drift.yml` = kopia z `cms-php` `0d20fcd` z różnicami: krok `open` czyta `git show FETCH_HEAD:tribunedesk.json > "$RUNNER_TEMP/open.json"` tylko przy otwartym PR-ze `contract/latest` i przekazuje `--open-pr-manifest`; tytuł commita i PR-a z `steps.drift.outputs.title`; `git add -A tribunedesk.json tests/contract src/Protocol README.md`; `gh workflow run plugin-ci.yml --ref contract/latest`; krok czerwieni: `::error::tribunedesk.json is behind the newest tags ($TITLE): land the contract/latest pull request`. Komentarz nagłówka: spec D2b, jedna gałąź na dwie przypinki (dlaczego: `test_version_names_a_tag`), PR nie scala się sam, lądowanie nie wydaje wtyczki.
- [ ] **Step 2:** README: w akapicie o `tribunedesk.json` (l. 34) — kopia `guide/` w `tests/contract/`, mapa `docs/contract-map.json` (nowa klasa w `src/WordPress/` = czerwone CI bez wpisu) i codzienny drift otwierający PR `contract/latest`.
- [ ] **Step 3:** `php -l` na `ci/*.php`; testy driftu lokalnie PASS; cały zestaw w wp-env (Docker jest na laptopie) albo w CI.
- [ ] **Step 4: commit** `ci(contract): codzienny drift contract/latest (kontrakt najpierw, etap 5a)`; push `ci/contract-drift`, PR do `main`, CI `test` zielony na 8.3 i 8.5.
- [ ] **Step 5 (po lądowaniu, na słowo ownera):** `gh workflow run contract-drift.yml -R Tribunedesk/tribunedesk-wordpress` → oczekiwany run **czerwony** z PR-em `contract: 3.4.1-draft → 3.4.2-draft, protocol: 1.1.0 → 1.1.1` i zielonym `Plugin CI` z dispatchu na `contract/latest` (check `test` na SHA gałęzi — sprawdzić, że ochrona `main` go widzi). Lądowanie tego PR-a i zamknięcie `2026-11-13-tribunedesk-wordpress-kontrakt-3-4-2` — słowo ownera.

## Co zostaje dla 5b (osobny plan, ustalenia z 16.11)

- `--levels 1,2,3,4` wymaga też komend poziomu 4: `--sync-cmd`, `--media-inspect-cmd`, `--media-add-cmd`, `--media-edit-cmd`, `--media-delete-cmd` (opcjonalnie `--reset-cmd`) — czyli `wp td sync|media …|reset` obok `inspect|publish` z D2e.
- `CmsApiClient` i `PublishedUrlsClient` wysyłają token tylko po `https` (`is_secure_base`), a API atrapy jest po `http` (D5) — poziomy 2–4 wtyczki nie porozmawiają z atrapą bez zmiany.
- wp-env to Docker: `127.0.0.1` atrapy na runnerze nie jest widoczny z kontenera, a atrapa dostarcza webhook do WordPressa.
- Przypinka `TDKIT_TAG` (plik `ci/tdkit-tag`, poza workflowami) jako trzecia w tym samym drifcie — `applyTdkit` dopisany w 5b.
