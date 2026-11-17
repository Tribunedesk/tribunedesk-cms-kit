# Kontrakt najpierw — etap 6: przewodnik 3.5.0-draft z zachowaniami wtyczki przez cały łańcuch — plan wykonania

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** trzy zachowania wtyczki WordPress klasy (b), których przewodnik 3.4.2-draft nie opisuje, trafiają do przewodnika jako `3.5.0-draft` i przechodzą cały przepływ z sekcji 5 specu bez ręcznego tagu: headlinesforge → PR `sync/latest` w `cms-api` → tag stawiany przez `tag.yml` → drift kitu (pokrycie, scenariusz) → wydanie kitu i skilla → drift `cms-php` → drift wtyczki (trzy przypinki, kopia `guide/`, mapa, `tdkit check` z nowym scenariuszem). Każde miejsce, w którym łańcuch utknie, jest znaleziskiem o automacie, nie przeszkodą do obejścia.

**Architecture:** jedna zmiana treści (tekst przewodnika EN+PL, punkty „Done when”, CHANGELOG z blokiem `**Integrators:**`) i dalej wyłącznie kroki, które automaty z etapów 1–5 mają wykonać same, z ręcznym dopisaniem tylko tego, czego automat z założenia nie robi (wpisy pokrycia, scenariusz, implementacja w integracjach wzorcowych). Plan ma siedem faz po repozytoriach; każda kończy się zatrzymaniem z raportem, bo następna zaczyna się od zdarzenia w innym repo (tag, codzienny drift).

**Tech Stack:** jak w etapach 1–5 — Markdown przewodnika (headlinesforge `docs/api/cms/`), Python 3.12 + uv `0.12.20` (kit, `contract_gate.py`), PHP 8.3 + PHPUnit (`cms-php`, wtyczka), GitHub Actions na `GITHUB_TOKEN`.

**Spec:** `docs/specs/2026-11-13-kontrakt-najpierw-automaty-design.md` — D1 (klasa b), D2a–D2c, D2e, D3, D4, sekcja 5 (przepływ), sekcja 8 punkt 6. Poprzednie etapy: `docs/plans/2026-11-16-kontrakt-najpierw-etap-5a-…`, `…-5b-…`.

## Stan przed etapem (sprawdzony poleceniami 17.11)

| Repo | `main`/`master` | Najnowszy tag | Otwarte PR-y |
|---|---|---|---|
| kit | `5ac05a0` | `v1.3.1`; `ci/contract-tag` = `v3.4.2-draft`; `SUPPORTED_MINORS = frozenset({(3, 4)})` (`src/tdkit/docs.py:27`) | brak |
| `cms-api` | `c45e81e` (`pr.yml`, `tag.yml`, `.github/scripts/contract_gate.py`) | `v3.4.2-draft` (lekki, ręczny — `tag.yml` jeszcze nigdy nie postawił tagu) | brak |
| `cms-php` | `0d20fcd` = `v1.1.1` (`VERSION` 3.4.2) | `v1.1.1` | brak |
| wtyczka | `1cfb5d1` = `v2.4.0`; `tribunedesk.json`: contract `3.4.2-draft`, protocol `1.1.1`, kit `1.3.1` | `v2.4.0` | brak |
| headlinesforge | źródło dokumentacji: `docs/api/cms/` (+ `pl/`), `docs/api/cms-v3.openapi.json`; `CONTRACT_VERSION = "3.4.2-draft"` w `backend/api/cms_v3/routes.py:114`; strażnik `scripts/cms_contract_guard.py` w `back-ci.yml`; `cms-api-docs.yml` z wymaganym tokenem (D2d), ostatni run 15.11 zielony | — | — |

**Ważne dla kolejności (sprawdzone w kodzie):**

1. **Zmiana treści nie zaczyna się w `cms-api`.** `cms-api` to drzewo publiczne budowane przez `scripts/cms_api_public_tree.py` z headlinesforge; zmiana wpisana wprost w `cms-api` zostałaby nadpisana przy następnej synchronizacji. Wersja żyje w headlinesforge w pięciu miejscach: `docs/api/cms-v3.openapi.json` (`info.version`), `CONTRACT_VERSION` w backendzie, testy `tests/backend/test_cms_v3_contract.py:711,775,1086`, `VERSIONING.md`/`README.md` EN i PL, `frontend/public/developers/cms/guide.html` + `openapi.json` (generowane: `scripts/export_cms_guide.py`).
2. **Scenariusz z nowym punktem nie może wejść do kitu przed tagiem.** `tests/test_check.py::test_done_when_quotes_are_literal` szuka cytatu `done_when` w `tests/fixtures/cms-api` = kopia `ci/contract-tag`, a `tests/test_coverage.py` czerwieni wpis nieaktualny. Przed tagiem kit może więc wydać tylko poszerzony `SUPPORTED_MINORS`; scenariusz, wpisy pokrycia i nowa fixture przychodzą PR-em driftu `contract/latest` po tagu (dokładnie mechanizm D3).
3. **`pr.yml` w `cms-api` padnie na PR-ze `sync/latest`**, dopóki najnowszy tag kitu nie ma `(3, 5)` (`contract_gate.py::decide`, wyrażenie `_MINORS_LINE` wymaga jednej linii `SUPPORTED_MINORS = frozenset({(3, 4), (3, 5)})`). To zaplanowany sygnał D2c, nie błąd. `main` `cms-api` nie ma ochrony — czerwony `pr.yml` niczego nie blokuje; pilnuje go człowiek scalający.
4. **Drift wtyczki zmienia trzy przypinki naraz**, a `tests/test-contract.php` wymaga `contract == ContractVersion::TESTED` z `src/Protocol` — PR wtyczki zazieleni się dopiero, gdy jest tag `cms-php` z `TESTED = 3.5.0-draft`. A `"kit"` musi wskazywać wydanie z nowym scenariuszem, inaczej `tdkit check` wtyczki jest zielony bez sprawdzenia nowego zachowania (anty-cel).
5. **Atrapa podaje `contract_version` z dokumentacji** (`src/tdkit/mock/server.py:326`), nie z backendu — łańcuch nie potrzebuje deployu headlinesforge. Produkcyjny `GET /v3/cms/status` będzie mówił `3.4.2-draft` aż do `/deploy` headlinesforge (osobno, na słowo ownera).

## Inwentaryzacja klasy (b) (kod wtyczki `origin/main` `1cfb5d1` vs przewodnik `v3.4.2-draft`)

Mapa `docs/contract-map.json` wiąże każdą z 33 klas z sekcją przewodnika albo `wp_only` — luk na poziomie klas nie ma. Luki są **wewnątrz** sekcji, na które mapa już wskazuje:

| # | Zachowanie wtyczki | Gdzie w kodzie | Sekcja przewodnika | Co przewodnik mówi dziś | Test |
|---|---|---|---|---|---|
| E | Filtr embedów: `<script>` usuwany z treścią; `<iframe>` tylko z `youtube.com/embed/`, `www.youtube.com/embed/`, `player.vimeo.com/video/`, `platform.twitter.com/`, `www.instagram.com/embed`, `www.tiktok.com/embed/`, `www.facebook.com/plugins/`, atrybuty `src width height frameborder allowfullscreen allow title`; zapis z jawnie dozwolonym iframe, bo dostawa idzie bez zalogowanego użytkownika | `Sanitizer.php:17-67`, `PostWriter.php:55-69` | 1 › The HTML body | tylko „An editor may still paste an embed by hand” | scenariusz `l1-embeds` (czarna skrzynka: `inspect` → `html`) |
| R | Raport adresu, który padł na sieci, `429` albo `5xx`, idzie ponownie (wtyczka: raz po 5 min, timeout 5 s); posty sprzed tokenu raportuje jednorazowe uzupełnienie w paczkach po 100 | `PublishNotifier.php:28-111`, `Backfill.php:10-183` | 2 › Reporting the published address | tylko `not_found`/`invalid_url` „logged, not retried unchanged” | `exempt`: atrapa nie przetrzyma integracji kilka minut, czas ponowienia należy do integracji |
| F | Pliki, które były w bibliotece przed włączeniem poziomu 4, nie idą jako nowe (`POST /media` tylko powyżej progu ID z pierwszego uruchomienia); do Tribune Desk trafiają tylko importem historycznym | `MediaPush.php:32-41` | 4 › Sending new files | zdanie o `push-existing` w sekcji kursora, czytane jako kierunek TD→CMS | `exempt`: `tdkit` nie może dodać plików do biblioteki „przed startem” integracji |

**Odrzucone jako (c) albo już opisane** — w tym „limity kolejek”, o których mówi spec: rozmiary paczek i budżety przebiegów (`CmsSync` 3×100/5 min, `CmsBackfill` 500/3, kolejka usunięć 5000, metadane 500, log 20 wierszy, „czytaj więcej” 5/20) to tempo wewnętrzne pod limitem, który przewodnik już opisuje („Stay far below the rate limit”, „a handful spread over a day”, „a few days is a sound default”); integrator nie widzi ich z zewnątrz i nie ma czego wymagać. `429`/`Retry-After` — w OpenAPI. Język nieznany (Polylang), ekran ustawień, nazwy filtrów — idiom WordPressa.

**Na granicy, poza 3.5.0 (rekomendacja; decyzja ownera — pytanie 1):** ponowne wysyłanie plików odrzuconych za host po 7 dniach (`MediaPush::HOST_RETRY`) — właściwa poprawka to zdanie o serwerze (czy dodanie hosta wysyła `kind="settings"`), wymaga sprawdzenia backendu; polityka „opublikowanego wpisu nie nadpisuję, pola SEO tylko gdy puste” (`DraftRules` sama nazywa ją polityką biblioteki, nie kontraktu); obraz wyróżniający ustawiany raz; autor dopasowany e-mailem musi móc pisać; ponowna wysyłka po koszu tworzy nowy szkic.

**Rozjazdy wtyczka ↔ przewodnik znalezione przy okazji (nie luki przewodnika, nie ten etap):** dostawa bez `topic` → `400` (`RestEndpoint.php:71-73`), choć `topic` jest opcjonalny; zmiana adresu opublikowanego wpisu nie jest raportowana (`PublishNotifier.php:53`), choć przewodnik 2 każe. Zapisane do oceny w `/finalize`.

## Decyzje (do akceptacji ownera)

**S1. Zakres 3.5.0-draft = E, R, F.** E jest jedyną luką, którą `tdkit` sprawdzi czarną skrzynką i którą redakcja zobaczy na stronie (znikający YouTube); R i F to błędy, które integrator popełni na pewno bez zdania w przewodniku (zgubiony link zwrotny, cała biblioteka wysłana jako nowa i zjedzony dzienny limit).
- **Odrzucone: dołożyć pozycje graniczne.** Każda to albo pytanie o serwer (host → `settings`), albo polityka, której inny CMS nie musi mieć; wciągnięte do „Done when” wymuszałyby kolejne `exempt` (D3: przegląd przy >20%).
- **Odrzucone: tylko E.** Taniej o dwa wpisy `exempt`, ale R i F zostałyby dryfem wtyczka → skill, który evale parytetu 1.3 już pokazały (przegląd zachowania oblany, STATE 17.11).
- **Rewizja:** gdy owner rozstrzygnie pozycje graniczne — kolejny minor tym samym przepływem.

**S2. Kit wydaje dwa razy: `1.3.2` przed tagiem, `1.4.0` po tagu.** `1.3.2` = tylko `SUPPORTED_MINORS = frozenset({(3, 4), (3, 5)})` (patch: kit przyjmuje więcej, nic nie zmienia w zachowaniu). `1.4.0` = fixture 3.5.0, scenariusz `l1-embeds`, wpisy pokrycia, integracje wzorcowe, `SUPPORTED_MINORS = frozenset({(3, 5)})` (stary minor wypada — D2c), rytuał D4 (evale parytetu, wiersze w README).
- **Why:** scenariusz nie może wejść przed tagiem (stan, punkt 2), a evale D4 przed scenariuszem mierzyłyby kit bez nowego zachowania.
- **Odrzucone: `1.4.0` przed tagiem.** `tests/test_project.py::test_readme_has_parity_rows_for_this_minor` wymusza evale (~10 USD) na wydaniu, które nie testuje nowego zachowania, i drugie ~10 USD po tagu.
- **Odrzucone: jedno wydanie po tagu.** Niemożliwe — strażnik D2c nie wpuści tagu bez kitu znającego 3.5.
- **Rewizja:** gdy kolejny minor kontraktu przyjdzie bez nowych punktów „Done when”, wystarczy jedno wydanie przed tagiem.

**S3. Biblioteka `cms-php` nie dostaje filtra embedów.** Biblioteka nie ma dziś niczego o HTML (`src/` = podpis, kursory, reguły szkicu, hosty obrazów); Drupal ma własne formaty tekstu, Laravel własne sanitizery. `cms-php` w tym etapie to tylko drift i tag `v1.1.2`.
- **Odrzucone: `EmbedRule` w bibliotece.** Nowy publiczny kod bez drugiego użytkownika; wtyczka i tak filtruje przez `wp_kses`.
- **Rewizja:** gdy eval `parity-laravel` dwa razy oblewa `l1-embeds`.

**S4. Tekst przewodnika (EN, dosłownie; PL tłumaczy budowniczy w tym samym PR-ze).** Ten tekst jest kontraktem między repo — punkty „Done when” i pozycje `Integrators` cytuje dosłownie kit (`coverage.toml`, `scenarios.py`); zmiana słowa po fazie A to nowy patch.

- `guide/1-article-delivery.md`, sekcja „The HTML body”, nowy punkt listy po „No media in the body” (poprawka przy wykonaniu: blok etykiety AI to też `script`, a przewodnik pozwala go zostawić):
  > - **Embeds:** keep an `iframe` only when its `src` starts with the address of a video or social player you trust (the WordPress plugin keeps players from YouTube, Vimeo, X, Instagram, TikTok and Facebook), and keep only its `src`, `width`, `height`, `frameborder`, `allowfullscreen`, `allow` and `title`. Remove every other `iframe`, and every other `script` together with its content (the AI label block below is the one script you may keep). A delivery arrives with no editor logged in: if your CMS filters content by the rights of the current user, check that this filter keeps the embeds you trust.
- Punkt „Done when” przewodnika 1 (po punkcie o `image_hosts`):
  > - A `script` in `html` other than the AI label block is removed with its content; an `iframe` of a YouTube player is kept and an `iframe` from a host you do not trust is removed.

  (Poprawka przy wykonaniu: adres `www.youtube.com` w punkcie oblewa skan prywatnych danych drzewa publicznego `tests/scripts/test_cms_api_public_tree.py`, więc punkt mówi „a YouTube player”; scenariusz i tak używa `https://www.youtube.com/embed/…`.)
- `guide/2-link-back.md`, sekcja „Reporting the published address”, akapit na końcu:
  > **When a report fails.** A report that ends with a network error, `429` or a `5xx` is sent again later (after `Retry-After` when there is one); the WordPress plugin tries once more after 5 minutes. Posts that were public before your integration had its token are reported once it has one, up to 100 per request.
- Punkt „Done when” przewodnika 2 (po punkcie o `not_found`):
  > - A report that fails with a network error, `429` or `5xx` is sent again later, not dropped.
- `guide/4-media-library.md`, sekcja „Sending new files”, akapit po pierwszym:
  > Send only files added after you turned level 4 on. Files that were already in your library reach Tribune Desk through a historical import (see Historical import), not as new files: a whole library sent at once would use up the daily limit on describing new files.
- Punkt „Done when” przewodnika 4 (po punkcie o nowych plikach):
  > - Files that were in your library before level 4 was turned on are not sent as new files.
- `CHANGELOG.md`:
  ```
  ## 3.5.0-draft – 2026-11-17

  - Guide 1: which embeds to keep in `html`, and that a delivery arrives with no editor logged in.
  - Guide 2: a failed report of the published address is sent again; posts public before the token are reported once.
  - Guide 4: files already in the library are not sent as new files.

  **Integrators:**

  - `L1`: keep an `iframe` only from players you trust and remove every `script` other than the AI label block, with its content; check that your content filter keeps those embeds when no editor is logged in.
  - `L2`: send a report of the published address again when it fails with a network error, `429` or `5xx`.
  - `L4`: do not send files that were in your library before level 4 as new files.
  ```

## Global Constraints

- Każda zmiana w worktree swojego repo; PR-y; lądowanie `main`/`master` każdego repo tylko `/ship` na słowo ownera. Scalenie PR-a `sync/latest` w `cms-api` — ręcznie przez ownera (decyzja 3 specu otwartego API), nigdy przez sesję.
- Żadnego ręcznego tagu kontraktu: `v3.5.0-draft` stawia `tag.yml`. Ręczny tag = test łańcucha oblany; zgłosić, nie obchodzić.
- Wydania: kit `v1.3.2` i `v1.4.0` (tag + `plugin.json` + `SKILL.md` + `src/tdkit/__init__.py` + `README.md` + `tests/test_cli.py`, wzór commita `e927f0e`); `cms-php` `v1.1.2` na commicie lądującym drift. Wydanie wtyczki (wersja, tag, `Publish manifest`) i `/deploy` headlinesforge — poza etapem, osobno na słowo ownera.
- Teksty z S4 dosłownie wszędzie, gdzie są cytowane (kit `coverage.toml` i `scenarios.py`); znaki: zwykłe `-` w punktach, backticki jak w S4.
- Pełny `pytest` kitu i headlinesforge nie biegnie lokalnie — tylko zawężone cele (`tests/test_coverage.py`, `tests/test_check.py::…`, `tests/backend/test_cms_v3_contract.py`); całość na CI.
- PR driftu wtyczki otwarty przez `github-actions`: run `pull_request` w `action_required` — zatwierdzić `gh api -X POST repos/Tribunedesk/tribunedesk-wordpress/actions/runs/<id>/approve` i zapisać to jako znalezisko (Task 7).

## Review Focus

1. **Filtr, który działa w edytorze, a nie w dostawie** (zalogowany admin ma `unfiltered_html`, webhook nie) — scenariusz musi iść przez prawdziwą dostawę, nie przez `publish`. Task 4: `l1-embeds` dostarcza przez `ctx.deliver`, a `inspect` czyta zapisany wpis.
2. **Skrypt usunięty jako tag, ale jego tekst został** (dokładnie błąd, który wtyczka miała z JSON-LD) — Task 4: asercja na znacznik `tdkit-script-marker` w `text_of(html)`, nie tylko na brak `<script`.
3. **Host „zaufany” po prefiksie bez ukośnika** (`https://www.youtube.com.evil.example/embed/` przechodzi naiwne `startswith("https://www.youtube.com")`) — Task 4: trzeci iframe z takim adresem musi zniknąć; integracje wzorcowe porównują z prefiksem kończącym się `/`.
4. **`pr.yml` zielony na PR-ze `sync/latest` przed wydaniem `1.3.2`** (strażnik nie czyta tagu albo czyta `main`) — Task 2 krok weryfikacji: run musi być czerwony z komunikatem o `SUPPORTED_MINORS`; zielony = znalezisko.
5. **Drift wtyczki podnosi `"kit"` do `1.3.2` zamiast `1.4.0`** (drift przyjdzie w dniu między wydaniami) — Task 7: przed lądowaniem `tribunedesk.json` ma `"kit": "1.4.0"`, a log joba `tdkit` zawiera `l1-embeds … pass`.

---

## Faza A — headlinesforge: treść 3.5.0-draft

### Task 1: Przewodnik, CHANGELOG i wersja w headlinesforge

**Files** (worktree headlinesforge, gałąź `docs/cms-3-5-zachowania-wtyczki` od `origin/master`):
- Modify: `docs/api/cms/guide/1-article-delivery.md`, `2-link-back.md`, `4-media-library.md` (teksty S4)
- Modify: `docs/api/cms/pl/guide/1-article-delivery.md`, `2-link-back.md`, `4-media-library.md` (tłumaczenie)
- Modify: `docs/api/cms/CHANGELOG.md` (blok S4 na górze)
- Modify: `docs/api/cms-v3.openapi.json` (`info.version` → `3.5.0-draft`), `backend/api/cms_v3/routes.py:114`, `docs/api/cms/VERSIONING.md`, `docs/api/cms/README.md`, `docs/api/cms/pl/VERSIONING.md`, `docs/api/cms/pl/README.md`
- Regenerate: `frontend/public/developers/cms/guide.html`, `frontend/public/developers/cms/openapi.json` (`python -m scripts.export_cms_guide`)
- Test: `tests/backend/test_cms_v3_contract.py:711,775,1086` (wersja `3.5.0-draft`)

**Interfaces:**
- Produces: teksty S4 (dosłownie) na `master` headlinesforge → PR `sync/latest` w `cms-api`.

- [ ] **Step 1:** zmień trzy asercje wersji w `tests/backend/test_cms_v3_contract.py` na `3.5.0-draft`; uruchom `uv run pytest tests/backend/test_cms_v3_contract.py -q` — Expected: FAIL na wersji.
- [ ] **Step 2:** wpisz teksty S4 (EN), tłumaczenie PL, CHANGELOG, wersję w pięciu miejscach; regeneruj stronę.
- [ ] **Step 3:** `uv run pytest tests/backend/test_cms_v3_contract.py -q` i `uv run python -m scripts.cms_contract_guard --base origin/master --head HEAD` — Expected: PASS; strażnik: „Zmiany API CMS z wpisem w docs/api/cms/CHANGELOG.md” albo brak zmian API.
- [ ] **Step 4:** sprawdź lokalnie, co dostanie `cms-api`: `python3 -m scripts.cms_api_public_tree <klon cms-api>` i w klonie (z tagami) `python3 .github/scripts/contract_gate.py --repo .` — bazą jest najnowszy tag `v3.4.2-draft` — Expected: jedyny problem to „release tdkit knowing 3.5” (dowód, że wersja, CHANGELOG i minor za nowe punkty są w porządku).
- [ ] **Step 5:** commit, push gałęzi, PR do `master`; CI zielone.

**STOP A:** raport (diff przewodnika, wynik kroku 4, CI). Owner: `/ship` headlinesforge. Po lądowaniu: `gh run list --workflow cms-api-docs.yml -L1` zielony i w `cms-api` otwarty PR `sync/latest`.

## Faza B — `cms-api`: strażnik zatrzymuje tag

### Task 2: Czerwony `pr.yml` jako sygnał D2c

**Files:** brak zmian (obserwacja).

- [ ] **Step 1:** `gh pr list -R Tribunedesk/tribunedesk-cms-api` — Expected: PR z `sync/latest`.
- [ ] **Step 2:** `gh run list -R Tribunedesk/tribunedesk-cms-api --workflow pr.yml -L1` + log — Expected: FAIL z komunikatem o `SUPPORTED_MINORS` i `tdkit v1.3.1 supports 3.4`. Każdy inny problem (wersja, CHANGELOG, minor) = błąd fazy A albo automatu — STOP z raportem.

## Faza C — kit `1.3.2`: kit zna 3.5 przed tagiem

### Task 3: `SUPPORTED_MINORS` z (3, 5) i wydanie `1.3.2`

**Files** (worktree kitu, gałąź `feat/supported-3-5`):
- Modify: `src/tdkit/docs.py:27`
- Test: `tests/test_docs.py`
- Release files jak `e927f0e`: `src/tdkit/__init__.py`, `plugins/tribunedesk-integration/.claude-plugin/plugin.json`, `.../SKILL.md` (pin `@v1.3.2`), `README.md`, `tests/test_cli.py`

**Interfaces:**
- Produces: tag `v1.3.2`, którego `src/tdkit/docs.py` ma linię `SUPPORTED_MINORS = frozenset({(3, 4), (3, 5)})` (dokładnie ten kształt czyta `_MINORS_LINE` w `cms-api`).

- [ ] **Step 1: test** `test_accepts_3_5_and_still_3_4` w `tests/test_docs.py`: `is_supported("v3.5.0-draft")` i `is_supported("v3.4.2-draft")` prawdziwe, `is_supported("v3.6.0-draft")` fałszywe (`src/tdkit/docs.py:31`). Run `uv run pytest tests/test_docs.py -q` — Expected: FAIL.
- [ ] **Step 2:** zmień linię 27; Run — Expected: PASS.
- [ ] **Step 3:** `tdkit docs` na gałęzi `sync/latest`: `git clone --depth 1 --branch sync/latest https://github.com/Tribunedesk/tribunedesk-cms-api $TMP/cms-api` i `uv run tdkit mock --docs $TMP/cms-api` (start i `GET /v3/cms/status` z `contract_version` `3.5.0-draft`) — Expected: atrapa startuje, nie „update the plugin”.
- [ ] **Step 4:** pliki wydania `1.3.2`, commit `release: tdkit 1.3.2 (kit zna kontrakt 3.5)`, PR, CI zielone.

**STOP C:** owner `/ship` kitu + tag `v1.3.2`. Potem `gh run rerun` ostatniego `pr.yml` na PR-ze `sync/latest` — Expected: PASS. Owner scala PR `sync/latest`. Expected: run `tag.yml` zielony i `git ls-remote --tags …cms-api v3.5.0-draft` pokazuje tag; `git cat-file -t v3.5.0-draft` = `tag` (adnotowany). Ręczne postawienie tagu = test łańcucha oblany, raport zamiast obejścia.

## Faza D — kit `1.4.0`: pokrycie, scenariusz, integracje wzorcowe

### Task 4: PR driftu kitu i scenariusz `l1-embeds`

**Files** (gałąź `contract/latest`, otwarta przez `contract-drift.yml`; jeśli runu nie było — `gh workflow run contract-drift.yml`):
- Already changed by drift: `ci/contract-tag` (`v3.5.0-draft`), `tests/fixtures/cms-api/**`
- Modify: `src/tdkit/check/scenarios.py` (stała `D1_EMBEDS` = punkt S4 dosłownie, funkcja `embeds(ctx: Context) -> str`, `Scenario("l1-embeds", 1, "webhook", D1_EMBEDS, f"{G1}#the-html-body", embeds)`)
- Modify: `src/tdkit/check/coverage.toml` (wpisy niżej)
- Modify: `README.md` (tabela scenariuszy: `l1-embeds`)
- Test: `tests/test_check.py`, `tests/test_coverage.py`, `tests/reference_integration.py` (jeśli udaje integrację wzorcową)

**Interfaces:**
- Consumes: `ctx.article(html=...)`, `ctx.deliver`, `ctx.must_inspect`, `text_of`, `expect` (`scenarios.py:55-108`).
- Produces: id scenariusza `l1-embeds` — cytują go `coverage.toml` (Task 4) i wtyczka (Task 7, log `tdkit`).

- [ ] **Step 1:** obejrzyj czerwony CI PR-a driftu — Expected: `test_coverage.py` pada na trzy punkty „Done when” i trzy pozycje `Integrators` 3.5.0-draft (dokładnie te; inna lista = błąd fazy A). Zapisz w raporcie.
- [ ] **Step 2: test** w `tests/test_check.py`: `test_embeds_scenario_fails_a_cms_that_keeps_the_script` i `…_drops_youtube` na atrapie integracji (wzór istniejących testów scenariuszy); `test_embeds_scenario_passes_a_filtering_cms`. Run — Expected: FAIL (brak scenariusza).
- [ ] **Step 3:** `embeds`: dostawa z `html` zawierającym `<p>before</p>`, iframe `https://www.youtube.com/embed/tdkit`, iframe `https://evil.example/embed/x`, iframe `https://www.youtube.com.evil.example/embed/x`, `<script>tdkit-script-marker</script>`. Asercje na `inspect`: `www.youtube.com/embed/tdkit` w `html`; `evil.example` nie; `tdkit-script-marker` nie w `html` ani w `text_of(html)`; `before` w `text_of(html)`. Dostawa nie ma bloku etykiety AI (`ai_provenance: null`), żeby punkt o wyjątku nie mieszał się z tym scenariuszem. Run — Expected: PASS.
- [ ] **Step 4:** `coverage.toml`:
  ```toml
  [[done_when]]
  guide = "guide/2-link-back.md"
  point = "A report that fails with a network error, `429` or `5xx` is sent again later, not dropped."
  reason = "tdkit cannot hold an integration for minutes; when to try again is the integration's choice"

  [[done_when]]
  guide = "guide/4-media-library.md"
  point = "Files that were in your library before level 4 was turned on are not sent as new files."
  reason = "tdkit cannot add files to a library before the integration starts"

  [[integrators]]  # 3 wpisy, version = "3.5.0-draft", action = tekst S4 bez "`Lx`: "
  # L1 -> handled_by = ["scenario:l1-embeds"]
  # L2, L4 -> handled_by = ["none"], reason = "the guide says it and the skill reads the guide live; tdkit cannot test it (see the exempt point)"
  ```
  Punkt E nie potrzebuje wpisu `[[done_when]]` (pokryty cytatem scenariusza). Run `uv run pytest tests/test_coverage.py tests/test_check.py -q` — Expected: PASS.
- [ ] **Step 5:** commit na `contract/latest` (push gałęzi), CI — Expected: `ci` zielony; joby `reference-django`/`reference-drupal` **czerwone na `l1-embeds`** albo zielone — wynik zapisać; czerwone naprawia Task 5.

### Task 5: Integracje wzorcowe filtrują embedy

**Files:**
- Modify: `reference/django/…` (miejsce zapisu `html` w odbiorniku — budowniczy znajduje; dziś brak jakiegokolwiek filtra iframe/script)
- Modify: `reference/drupal/…` (format tekstu albo filtr w module; bez zmian w `cms-php` — S3)
- Test: testy projektu Django (`manage.py test`) — `test_embeds_trusted_kept_script_removed`

- [ ] **Step 1:** test Django — Expected: FAIL. **Step 2:** filtr z listą prefiksów z S4 (każdy kończy się `/`, poza `www.instagram.com/embed` jak we wtyczce). **Step 3:** test PASS, job `reference-django` zielony.
- [ ] **Step 4:** Drupal: job `reference-drupal` (poziomy 1–2) zielony na `l1-embeds`; jeśli format tekstu Drupala już filtruje przy dostawie — tylko zapis w raporcie.
- [ ] **Step 5:** commit, push `contract/latest`, CI całe zielone.

### Task 6: `1.4.0` — stary minor wypada, rytuał D4, wydanie

**Files:** `src/tdkit/docs.py:27` (`frozenset({(3, 5)})`), `tests/test_docs.py` (3.4 już nie), pliki wydania jak w Task 3 (`1.4.0`, pin `@v1.4.0`), `README.md` (wiersze `parity-django|laravel|node` z `1.4.0`).

- [ ] **Step 1:** test `test_3_4_is_no_longer_supported`; zmiana; PASS.
- [ ] **Step 2:** pliki wydania `1.4.0`; `uv run pytest tests/test_project.py -q` — Expected: FAIL na `test_readme_has_parity_rows_for_this_minor` (brak wierszy 1.4).
- [ ] **Step 3: rytuał D4** (koszt ~10 USD, owner zgodził się w specu): `uv run python evals/run.py parity-django`, `parity-laravel`, `parity-node` z kitem z tej gałęzi. Kryterium: `tdkit check` zielony 1–4 **i** przegląd zachowania obejmuje E, R, F (w 1.3 przegląd oblany, bo przewodnik ich nie opisywał). Wiersze w README z wynikiem i kosztem — także oblany wynik, bez upiększania.
- [ ] **Step 4:** `tests/test_project.py` PASS, CI zielone.

**STOP D:** raport (CI, evale, koszt). Owner `/ship` kitu (`contract/latest`) + tag `v1.4.0`. To jest wydanie skilla: plugin z `main` czyta przewodnik 3.5 na żywo, `TDKIT integrators` pokazuje trzy pozycje.

## Faza E — `cms-php`: drift i tag `v1.1.2`

### Task 7a: PR driftu `cms-php`

- [ ] **Step 1:** `gh pr list -R Tribunedesk/tribunedesk-cms-php` — PR `contract/latest` „v3.4.2-draft → v3.5.0-draft” (jeśli brak: `gh workflow run contract-drift.yml -R …`). Expected w diffie: `VERSION`, wektory podpisu, `ContractVersion::TESTED`, linki README; opis PR-a wypisuje trzy pozycje `Integrators` i nie zgłasza brakujących kotwic (nagłówki w S4 się nie zmieniają).
- [ ] **Step 2:** CI PR-a zielone (jeśli run czeka w `action_required` — zatwierdzić i zapisać jako znalezisko jak we wtyczce).

**STOP E:** owner `/ship` `cms-php` + tag `v1.1.2` na commicie lądującym.

## Faza F — wtyczka: trzy przypinki i `tdkit check` z `l1-embeds`

### Task 7: PR driftu wtyczki

**Files:** `tribunedesk.json` (`contract` `3.5.0-draft`, `protocol` `1.1.2`, `kit` `1.4.0`), `src/Protocol/**`, `tests/contract/**` (z `guide/`) — wszystko z driftu; ręcznie najwyżej `docs/contract-map.json`.

- [ ] **Step 1:** `gh workflow run contract-drift.yml -R Tribunedesk/tribunedesk-wordpress` (albo poranny run) — Expected: PR `contract/latest` z trzema przypinkami jak wyżej. `"kit"` inne niż `1.4.0` = STOP (Review Focus 5).
- [ ] **Step 2:** run `pull_request` w `action_required` → `gh api -X POST repos/Tribunedesk/tribunedesk-wordpress/actions/runs/<id>/approve`; zapisać liczbę takich zatwierdzeń w raporcie (znany kłopot — znalezisko łańcucha, nie rozwiązywać w tym etapie).
- [ ] **Step 3:** CI — Expected: PHPUnit zielony (`GuideAnchors`: wszystkie kotwice mapy istnieją w nowej kopii `guide/`; mapa bez zmian, bo E, R, F leżą w sekcjach, na które już wskazują `Sanitizer`, `PublishNotifier`/`Backfill`, `MediaPush`), job `tdkit` zielony z `l1-embeds` na liście `pass`. Czerwony `l1-embeds` = rozjazd wtyczka ↔ tekst S4: STOP z raportem (poprawka tekstu to patch 3.5.1 tym samym przepływem, nie zmiana scenariusza pod wtyczkę).

**STOP F:** owner `/ship` wtyczki. Wydanie wtyczki 2.4.1 (ZIP zawiera `src/Protocol` z nowym `TESTED`) — osobna decyzja ownera, poza etapem.

## Faza G — domknięcie

### Task 8: Dowód łańcucha i stan

- [ ] **Step 1:** w każdym z kitu, `cms-php`, wtyczki: `gh run list --workflow contract-drift.yml -L1` po lądowaniu — Expected: zielony (przypinki aktualne). W `cms-api`: tag `v3.5.0-draft` adnotowany, postawiony przez `github-actions`.
- [ ] **Step 2:** raport dla ownera: lista miejsc, gdzie łańcuch wymagał człowieka poza zaplanowanymi (`/ship`, scalenie `sync/latest`, tag `cms-php`) — każde to propozycja zadania do `/finalize`.
- [ ] **Step 3:** wiki kitu: Rollout bez zmian; STATE przez `/checkpoint` (nie ręcznie).
