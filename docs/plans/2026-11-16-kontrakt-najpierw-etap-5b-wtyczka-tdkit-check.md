# Kontrakt najpierw — etap 5b: wtyczka przechodzi `tdkit check` w swoim CI — plan wykonania

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** każdy push i PR wtyczki `Tribunedesk/tribunedesk-wordpress` uruchamia `tdkit check --levels 1,2,3,4 --mode webhook` przeciw prawdziwemu WordPressowi z wtyczką (ogniwo 4 łańcucha), z `tdkit` z wersji przypiętej w manifeście `"kit"`, którą codzienny drift z 5a podnosi razem z `"contract"` i `"protocol"`.

**Architecture:** wtyczka dostaje komendy deweloperskie WP-CLI `wp td …` (cienka klasa `Cli` nad testowalną `DevCommands`). Job `tdkit` w `plugin-ci.yml` stawia WordPressa **na runnerze** (WP-CLI, `php -S` z kilkoma workerami, baza w kontenerze usługi), konfiguruje wtyczkę na atrapę i uruchamia `tdkit` z tagu kitu. API atrapy dostaje https przez proxy TLS na certyfikacie testowym kitu; wtyczka nie zmienia reguły „token tylko po https”. Rzeczy wyłącznie testowe (zaufanie do CA, pętla zwrotna) żyją w mu-pluginie z `ci/`, poza ZIP-em.

**Tech Stack:** PHP 8.3, WordPress (najnowszy, jak `core: null` w `.wp-env.json`), WP-CLI phar (przypięta wersja + sha512), MariaDB jako `services:` joba, `socat`, uv `0.12.20` (`astral-sh/setup-uv@v7`, jak kit), `tdkit` z `git+https://github.com/Tribunedesk/tribunedesk-cms-kit@v<kit>`, Polylang z wordpress.org (przypięta wersja).

**Spec:** `docs/specs/2026-11-13-kontrakt-najpierw-automaty-design.md`: D2e, D2b (przypinka `TDKIT_TAG`), D5, sekcja 8 punkt 5. Poprzedni etap: `docs/plans/2026-11-16-kontrakt-najpierw-etap-5a-wtyczka-drift-mapa.md` (wylądował 16.11, wtyczka `main` = `a480790`).

## Stan przed etapem (sprawdzony 16.11)

- 5a na `main`: `ci/ContractDrift.php` (dwie przypinki), `contract-drift.yml`, mapa `docs/contract-map.json`, `ci/phpunit.xml`. Pierwszy ręczny run driftu: czerwony zgodnie z planem, otworzył PR #9 `contract: 3.4.1-draft → 3.4.2-draft, protocol: 1.1.0 → 1.1.1` i uruchomił na nim `Plugin CI`.
- **`--levels 1,2,3,4` wymaga dziewięciu komend, nie dwóch:** `--inspect-cmd`, `--publish-cmd`, `--sync-cmd`, `--media-inspect-cmd`, `--media-add-cmd`, `--media-edit-cmd`, `--media-delete-cmd`, opcjonalnie `--reset-cmd`; `--backfill` i `--social-flag` włączają `l4-backfill-answered` i `l2-social-flag` (README kitu, „The commands your integration provides”, tabela scenariuszy). D2e wymienia tylko `inspect|publish`.
- **Https API:** `CmsApiClient::is_secure_base` i `PublishedUrlsClient` wysyłają token tylko na `https://` z hostem. Atrapa podaje `TD_API_BASE=http://127.0.0.1:<port>`. Jej serwer TLS (`_TlsServer`, `src/tdkit/mock/server.py`) obsługuje ten sam `Handler`, więc API jest też po https — ale na **losowym** porcie, którego `tdkit check` nie ujawnia, a wtyczka musi znać adres API z góry (opcja `headlinesforge_api_base`, czytana też w żądaniu webhooka, np. `ImageHosts`).
- **wp-env to Docker:** atrapa nasłuchuje na `127.0.0.1` runnera (stała `HOST`) i sama dostarcza webhook — kontener jej nie widzi, a ona nie widzi kontenera.
- **Manifest:** `tdkit manifest validate` (`src/tdkit/project.py::validate_manifest`) wymaga pola `"kit"` (niepusty string); wtyczka go nie ma, więc jej `tribunedesk.json` jest dziś dla `tdkit` niepoprawny. `"kit"` to dokładnie przypinka `TDKIT_TAG` z D2b.
- Wtyczka: `WP_CLI::add_command` nie występuje. Dane do `inspect`: `PostWriter::META_ARTICLE_ID` (`_aw_article_id`), `SeoMeta::META_TITLE/META_DESC` (klucze Yoast, pisane bez Yoasta), `ProvenanceMeta::META_KEY`, `Backlinks` (tabela `hf_backlinks`), język tylko przez Polylang (`Language`, `pll_set_post_language`). Link zwrotny: `PublishNotifier::on_after_insert` + `flush_pending`. Poziom 4: `CmsSync::run_poll/run_send`, `MediaPush::run`, `CmsDeletions::send`, `CmsBackfill::run`, `CmsResync::run_page`, `MediaMetaSync` (pola edytowane przez człowieka).
- Atrapa: `image_hosts` = `["127.0.0.1"]`; pliki po https na drugim porcie, CA w `TD_CA_BUNDLE`; przyjmuje adresy plików CMS-u z `127.0.0.1`/`localhost` po http (więc `--media-hosts` niepotrzebne).

## Decyzje (do akceptacji ownera)

**B1. Https API przez proxy TLS w CI.** `socat OPENSSL-LISTEN:8443,fork,reuseaddr,cert=<server.pem>,key=<server-key.pem>,verify=0 TCP:127.0.0.1:8787`; wtyczka ma `headlinesforge_api_base = https://127.0.0.1:8443` i ufa `TD_CA_BUNDLE`.
- **Why:** reguła „token tylko po https” zostaje bez wyjątku, kit bez zmian i bez wydania, certyfikat ten sam co dla plików (D5).
- **Odrzucone: opcja `tdkit check --tls-port N` w kicie.** Czystsza, ale to wydanie kitu przed 5b i przypinka `"kit"` ≥ nowej wersji; dziś potrzebuje jej tylko wtyczka.
- **Odrzucone: wyjątek http dla pętli zwrotnej w `CmsApiClient`.** Zmienia regułę bezpieczeństwa dla testów — to samo, co D5 odrzucił dla `ImageHostRule`.
- **Rewizja:** gdy druga integracja (Laravel z D4, Drupal na poziomie 2+) potrzebuje API po https — opcja w kicie, proxy znika.

**B2. WordPress na runnerze, nie w wp-env.** WP-CLI phar, `wp core download`, MariaDB jako kontener usługi joba (port na `127.0.0.1`), `php -S 127.0.0.1:8888` z `PHP_CLI_SERVER_WORKERS=4`.
- **Why:** atrapa i WordPress muszą się widzieć w obie strony na `127.0.0.1`; to wzór joba `reference-drupal` w kicie. Workery: bez nich `l1-overlapping-attempts` przechodzi, bo serwer i tak szereguje żądania — zieleń bez dowodu.
- **Odrzucone: wp-env z `host.docker.internal`.** Atrapa wiąże się z `127.0.0.1`, więc i tak niewidoczna z kontenera; trzeba by zmieniać kit.
- **Rewizja:** gdy job przekroczy ~10 min albo będzie niestabilny (D2e).

**B3. Przypinka kitu to pole `"kit"` manifestu** (`"kit": "1.3.0"`), trzecia w drifcie 5a.
- **Why:** `tdkit manifest validate` i tak go wymaga; drift czyta już manifest, więc krok `open` i `--open-pr-manifest` zostają bez zmian. Jedna gałąź `contract/latest` na trzy przypinki — D2c gwarantuje, że najnowszy kit zna najnowszy kontrakt.
- **Odrzucone: plik `ci/tdkit-tag`.** Drugi plik do czytania z otwartej gałęzi i manifest dalej niepoprawny dla `tdkit`.

**B4. Pierwszy pełny run to punkt zatrzymania.** Scenariusz czerwony na wtyczce to znalezisko (rozjazd wtyczka ↔ przewodnik), nie powód do zawężenia `--levels` ani do atrapy w komendzie. Plan staje po Task 4 z raportem; owner decyduje: naprawa we wtyczce w tym etapie, osobne zadania ledgera, czy tymczasowe zawężenie **widoczne w workflowie** z zadaniem ledgera. Job dołącza do wymaganego checku `test` dopiero zielony.

**B5. Polylang w CI.** `l3-seo-author-language` sprawdza język zapisany na wpisie; wtyczka zapisuje go tylko przez Polylang. Job instaluje przypiętą wersję Polylang z wordpress.org (`wp plugin install polylang --version=<X> --activate`, język `pl` i `en` dodane przez WP-CLI).
- **Odrzucone: bez Polylang.** Scenariusz padnie albo — gorzej — `inspect` zgłosi język z payloadu zamiast z wpisu.

## Global Constraints

- Praca w worktree klonu wtyczki: `git worktree add .claude/worktrees/tdkit-check -b ci/tdkit-check origin/main`. PR do `main`; lądowanie `/ship` na słowo ownera; wydanie wtyczki (wersja, tag, `Publish manifest`) — osobno, na słowo ownera.
- `src/WordPress/Cli.php` i `DevCommands.php` są w ZIP-ie (komendy dla integratorów, `references/cms/wordpress.md` §7); wszystko inne z 5b — `ci/`, `.github/`, testy.
- Komendy niczego nie wymyślają: `inspect` czyta to, co wtyczka zapisała (meta, tabele, Polylang), nigdy payload.
- Dane `inspect` (README kitu, „What `--inspect-cmd` prints”): `cms_post_id` (string), `title`, `html`, `excerpt`, `status`, `featured_image_url`, `permalink` (`null`, gdy wpis niepubliczny), `seo_title`, `meta_description`, `language`, `author`, `read_more` (lista `article_id`), `ai_provenance_jws` (lub `null`). `media inspect`: `cms_media_id`, `asset_id` (lub `null`), `sha256`, `fields` (`alt`, `caption`, `title`, `description`), `deleted_in_td`.
- Wartości testowe są publiczne: sekret `whsec_dGRraXQtbW9jay1zaWduaW5nLXNlY3JldC0wMDAwMDA=`, token `tdcms_mock` (README kitu). Żadnych sekretów repo.
- Wersje przypięte w workflowie: WP-CLI (phar + sha512 z wydania), MariaDB (obraz z tagiem wersji), Polylang, uv `0.12.20`; WordPress najnowszy jak w wp-env.

## Review Focus

1. **Równoległe próby jednej dostawy** — serwer jednowątkowy szeregowałby je i `l1-overlapping-attempts` byłby zielony bez dowodu blokady. Task 4: `PHP_CLI_SERVER_WORKERS=4` i asercja w kroku startu, że dwa żądania są obsługiwane naraz (`curl` na `?rest_route=/` dwa razy w tle, oba odpowiadają).
2. **`publish` kończy przed wysłaniem linku** (bulk/cron) — `l2-reports-url` czyta raport zaraz po komendzie. Task 2: `test_publish_sends_link_back_before_returning`.
3. **`inspect` zgłasza język/SEO z payloadu, nie z wpisu** — zieleń bez dowodu. Task 2: `test_inspect_reads_stored_values_not_the_delivery` (zmiana meta po dostawie widoczna w `inspect`).
4. **Edycja z `media edit` nie liczy się jako ludzka** (`MediaMetaSync::is_human_write`) i nie jest wysyłana — `l4-cms-field-edit` czerwony z mylącym powodem. Task 3: `test_media_edit_marks_field_dirty`.
5. **Drift podnosi `"kit"` do wersji bez znanego minora kontraktu** — D2c to wyklucza po stronie `cms-api`; tu: `test_run_moves_three_pins` i opis PR-a z linkiem `compare` kitu.

---

## Mapa plików (repo `tribunedesk-wordpress`)

| Plik | Odpowiedzialność |
|---|---|
| `tribunedesk.json` | + `"kit": "1.3.0"` |
| `ci/ContractDrift.php`, `tests/test-contract-drift.php` | trzecia przypinka `"kit"` |
| `src/WordPress/DevCommands.php` | logika komend, testowalna bez WP-CLI |
| `src/WordPress/Cli.php` | `wp td …` nad `DevCommands`, rejestrowane tylko gdy `WP_CLI` |
| `headlinesforge-receiver.php` | rejestracja `Cli` |
| `docs/contract-map.json` | `Cli`, `DevCommands` → `wp_only` |
| `tests/test-dev-commands.php`, `tests/test-dev-commands-media.php` | PHPUnit (wp-env) |
| `ci/tdkit/mu-plugin.php` | tylko CI: `TD_CA_BUNDLE` → `sslcertificates`, `127.0.0.1` jako host zewnętrzny dla `wp_safe_remote_*` |
| `ci/tdkit/site.sh` | instalacja WordPressa na runnerze i konfiguracja wtyczki na atrapę |
| `.github/workflows/plugin-ci.yml` | job `tdkit`; po B4 — w `needs` joba `test` |
| `README.md`, `readme.txt` | komendy `wp td` |

### Task 1: przypinka `"kit"` w manifeście i drifcie

**Interfaces — Produces:** `ContractDrift::KIT_REPO = 'https://github.com/Tribunedesk/tribunedesk-cms-kit'`, `KIT_TAG = '/^v\d+\.\d+\.\d+$/'`, `applyKit(string $repo, string $latest): void` (sama wartość `"kit"`, bez klonu), `pins()` zwraca trzy klucze, `title()` i `prBody()` znają `kit` (link `KIT_REPO/compare/v<stary>...v<nowy>`). Kolejność w tytule: contract, protocol, kit.

- [ ] **Step 1: testy:** `test_latest_tag_ignores_foreign_names` rozszerzony o kit; `test_title_names_only_moving_pins` z `kit`; `test_pr_body_links_kit_compare`; `test_apply_kit_moves_only_the_kit_value`; `test_run_moves_three_pins` (ls-remote trzech repo; klon tylko kontraktu i biblioteki); `test_run_open_pr_at_latest_is_left_alone` z trzema przypinkami; istniejące testy `run()` dostają `"kit"` w `MANIFEST` i kit w `NEWEST`. W `tests/test-contract.php::test_version_names_a_tag`: `"kit"` pasuje do `/^\d+\.\d+\.\d+$/`.
- [ ] **Step 2:** `php vendor/bin/phpunit -c ci/phpunit.xml` → FAIL. **Step 3:** implementacja; `tribunedesk.json` + `"kit": "1.3.0"` (po `"protocol"`). **Step 4:** PASS; próba na żywo jak w 5a (tytuł z trzema przypinkami tylko, gdy kit w tyle — dziś `1.3.0` = najnowszy, więc bez `kit`), zmiany cofnięte.
- [ ] **Step 5:** komentarz nagłówka `contract-drift.yml`: trzy przypinki. **Commit** `ci(contract): przypinka kit w manifescie i drifcie`.

### Task 2: `DevCommands` — poziomy 1–3

**Interfaces — Produces** (`TribuneDesk\WordPress\DevCommands`, statyczne):
- `inspect(string $article_id): ?array` — wpis po `_aw_article_id` (dowolny status poza `trash`), klucze z Global Constraints; `read_more` z `Backlinks` (te `article_id`, które pokazuje **ten** wpis); `language` z `pll_get_post_language($id)` albo `null` bez Polylang; `author` = `display_name` autora.
- `publish(string $article_id): void` — jak redaktor: `wp_publish_post`, potem `PublishNotifier::flush_pending()`; link zwrotny wysłany przed powrotem. `RuntimeException`, gdy wpisu nie ma.

- [ ] **Step 1: testy** (`tests/test-dev-commands.php`, `WP_UnitTestCase`, dostawa przez `RestEndpoint` jak `test-contract.php`, `pre_http_request` zapisuje żądania): `test_inspect_unknown_article_is_null`; `test_inspect_after_delivery_has_level_1_keys` (`cms_post_id` string, `status` `draft`, `permalink` `null`); `test_inspect_reads_stored_values_not_the_delivery` (zmiana `_yoast_wpseo_title` po dostawie → nowa wartość); `test_inspect_read_more_lists_article_ids`; `test_publish_sends_link_back_before_returning` (po `publish` w zapisanych żądaniach jest `POST …/v3/cms/articles/published` z `permalink` wpisu); `test_publish_unknown_article_throws`.
- [ ] **Step 2:** FAIL w wp-env (`npx @wordpress/env run tests-cli --env-cwd=wp-content/plugins/<katalog> ./vendor/bin/phpunit --filter Test_Dev_Commands`). **Step 3:** implementacja. **Step 4:** PASS. **Step 5: commit** `feat(cli): komendy deweloperskie, poziomy 1-3`.

### Task 3: `DevCommands` — poziom 4

**Interfaces — Produces:**
- `sync(bool $backfill): void` — jeden pełny cykl: `CmsSync::run_poll()` do `has_more = false` (jeśli `run_poll` robi jedną stronę — pętla tu), `CmsSync::run_send()`, `MediaPush::run()`, `CmsDeletions::send()`, z `$backfill` `CmsBackfill::run()`, `CmsResync::run_page()` gdy rekoncyliacja trwa; bez czekania na cron, z pominięciem blokad czasowych tylko tam, gdzie klasa ma do tego publiczną drogę (inaczej — znalezisko do raportu B4, nie obejście).
- `mediaInspect(int $id): ?array`, `mediaAdd(string $file): int` (jak redaktor: `media_handle_sideload`), `mediaEdit(int $id, string $field, string $value): void` (`alt` → `_wp_attachment_image_alt`, `caption` → `post_excerpt`, `title` → `post_title`, `description` → `post_content`, przez `wp_update_post`/`update_post_meta` jako zalogowany redaktor), `mediaDelete(int $id): void` (`wp_delete_attachment`, true), `reset(): void` (kursor, wersje, kolejki, pary, blokady — opcje i meta z `CmsSync`, `CmsDeletions`, `MediaMetaSync`, `CmsResync`, `CmsBackfill`; lista ustalona z ich stałych `OPTION_*`).

- [ ] **Step 1: testy** (`tests/test-dev-commands-media.php`): `test_media_inspect_reports_fields_and_sha256`; `test_media_inspect_unknown_is_null`; `test_media_add_returns_attachment_id`; `test_media_edit_marks_field_dirty` (`MediaMetaSync::dirty_fields($id)` zawiera pole); `test_media_delete_queues_deletion` (`CmsDeletions::queue()` niepuste); `test_reset_clears_cursor`; `test_sync_polls_until_no_more` (fałszywe `/changes` z `has_more` true, potem false → dwa GET-y).
- [ ] **Step 2–4:** FAIL → implementacja → PASS. **Step 5: commit** `feat(cli): komendy deweloperskie, poziom 4`.

### Task 4: `wp td …`, środowisko CI i pierwszy run (punkt zatrzymania B4)

**Interfaces — Consumes:** `DevCommands` z Task 2–3. **Produces:** komendy `wp td inspect <article_id>`, `publish <article_id>`, `sync [--backfill]`, `media inspect <id>`, `media add <file>`, `media edit <id> <field> <value>`, `media delete <id>`, `reset`; wyjście JSON (`wp_json_encode`, `null` dosłownie), błąd → `WP_CLI::error` (kod ≠ 0).

- [ ] **Step 1:** `src/WordPress/Cli.php` + rejestracja w `headlinesforge-receiver.php` (`if (defined('WP_CLI') && WP_CLI)`), wpisy mapy `wp_only` (powód: developer commands for `tdkit check`, guide-independent). Test mapy zielony.
- [ ] **Step 2:** `ci/tdkit/mu-plugin.php` (filtry `http_request_args` i `http_request_host_is_external`, oba tylko gdy `getenv('TD_CA_BUNDLE')`) i `ci/tdkit/site.sh` (argumenty: katalog strony, URL; `wp core download`, `wp config create` na MariaDB, `DISABLE_WP_CRON`, `wp core install`, link wtyczki do `wp-content/plugins`, mu-plugin, Polylang + języki, redaktor `editor`, opcje: `RestEndpoint::OPTION_SIGNING_SECRET` = sekret atrapy, `CmsApiClient::OPTION_TOKEN` = `tdcms_mock`, `PublishedUrlsClient::OPTION_API_BASE` = `https://127.0.0.1:8443`, domyślny autor, klucz meta dla `SocialQueueFlag`).
- [ ] **Step 3:** job `tdkit` w `plugin-ci.yml` (`ubuntu-26.04`, PHP 8.3 z `mysqli`, `services: mariadb`, uv, `socat`): `CA` i ścieżki `server.pem`/`server-key.pem` z `uvx --from git+…@v<kit> python -c "from tdkit.mock import tls; …"`; start proxy i `php -S` z `TD_CA_BUNDLE` w środowisku; asercja z Review Focus 1; potem w katalogu strony:
  `uvx --from "git+https://github.com/Tribunedesk/tribunedesk-cms-kit@v$kit" tdkit check --levels 1,2,3,4 --mode webhook --contract "v$contract" --webhook "http://127.0.0.1:8888/?rest_route=/tribunedesk/v1/receive" --social-flag --backfill --inspect-cmd "wp td inspect {article_id}" --publish-cmd "wp --user=editor td publish {article_id}" --sync-cmd "wp td sync --backfill" --media-inspect-cmd "wp td media inspect {cms_media_id}" --media-add-cmd "wp --user=editor td media add {file}" --media-edit-cmd "wp --user=editor td media edit {cms_media_id} {field} {value}" --media-delete-cmd "wp --user=editor td media delete {cms_media_id}" --reset-cmd "wp td reset" --media-fields alt,caption --json "$RUNNER_TEMP/tdkit-report.json"`
  oraz `tdkit manifest validate` na `tribunedesk.json`; raport JSON jako artefakt. **Job nie wchodzi jeszcze do `needs` joba `test`.**
- [ ] **Step 4:** commit, push gałęzi, PR; przeczytać raport pierwszego runu.
- [ ] **Step 5: STOP (B4).** Raport do ownera: scenariusze zielone / czerwone z `detail` i cytatem „Done when”, dla czerwonych — przyczyna (wtyczka, komenda, środowisko) z dowodem. Czerwone z winy komendy lub środowiska naprawiamy w tym etapie; z winy wtyczki — decyzja ownera.

### Task 5: job w wymaganym checku i dokumentacja (po decyzji z Task 4)

- [ ] **Step 1:** `test.needs: [php, tdkit]` i warunek `needs.tdkit.result == 'success'` w jobie zbiorczym (ochrona `main` wymaga `test`).
- [ ] **Step 2:** README (sekcja „Development”: `wp td …` i jak odtworzyć job lokalnie) i `readme.txt` (changelog następnej wersji: komendy WP-CLI dla integratorów).
- [ ] **Step 3:** CI zielone (`test (PHP 8.3)`, `test (PHP 8.5)`, `tdkit`, `test`), czas joba `tdkit` w opisie PR-a (rewizja D2e: ~10 min). **Commit**, PR gotowy do `/ship` na słowo ownera.

## Poza tym etapem

- Kit: `references/cms/wordpress.md` §7 wymienia `wp td inspect|publish|poll`; po 5b — uzupełnić o komendy poziomu 4 (osobna zmiana kitu).
- `"conformance"` manifestu (`tdkit manifest` z raportu) — CI nie commituje; wpis zostaje sprawą wydania.
