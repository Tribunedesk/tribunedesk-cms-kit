# Kontrakt najpierw — etap 1b: pliki atrapy po https — plan wykonania

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** atrapa `tdkit` podaje obrazy dostaw i `file_url` biblioteki mediów po `https`, z certyfikatem testowym w kicie, tak że integracja na `tribunedesk/cms-protocol` (tylko `https`) może pobrać obraz z atrapy; `l1-image-host` sprawdza też, że obraz z dozwolonego hosta **jest** pobrany. Wydanie `tdkit` 1.3.0.

**Architecture:** `MockServer` uruchamia obok serwera http drugi `ThreadingHTTPServer` na wolnym porcie, owinięty `ssl.SSLContext` z certyfikatem z `src/tdkit/mock/tls/`. Ten sam handler obsługuje oba; adresy plików (`Context.article`, `image_host`, `files_base`) biorą schemat i port serwera https. API zostaje po `http` (`TD_API_BASE`). Ścieżkę certyfikatu CA `tdkit` podaje komendom integracji w `TD_CA_BUNDLE` i wypisuje ją w `tdkit mock` i `tdkit check`.

**Tech Stack:** Python 3.12, biblioteka standardowa (`ssl`), pytest, ruff, pyright; `openssl` (z Git for Windows) tylko raz, do wygenerowania certyfikatów, skryptem zapisanym w repo.

**Spec:** `docs/specs/2026-11-13-kontrakt-najpierw-automaty-design.md`, D5 (zatwierdzone 13.11) i sekcja 8, etap 1b.

## Global Constraints

- Żadnej nowej zależności; TLS przez `ssl` z biblioteki standardowej.
- Certyfikaty są jawne i tylko na pętlę zwrotną: CA (`ca.pem`, `basicConstraints=critical,CA:TRUE`, `keyUsage=critical,keyCertSign,cRLSign`, SKI) i certyfikat serwera (`server.pem` + `server-key.pem`) podpisany tym CA, z `subjectAltName=IP:127.0.0.1,DNS:localhost`, `basicConstraints=critical,CA:FALSE`, `keyUsage=critical,digitalSignature,keyEncipherment`, `extendedKeyUsage=serverAuth`, SKI i AKI (Python 3.13 weryfikuje w trybie `VERIFY_X509_STRICT`). Ważność 3650 dni. Klucz CA **nie** trafia do repo.
- Zmienna środowiskowa: `TD_CA_BUNDLE` = absolutna ścieżka `ca.pem`.
- API atrapy zostaje po `http`; `TD_API_BASE` bez zmian.
- `l1-image-host`: najpierw obraz z dozwolonego hosta po `https` — atrapa musi zobaczyć pobranie w ciągu 15 s (pobieranie w tle jest dozwolone, guide 1); potem obraz spoza listy — nie może być pobrany (jak dziś, 2 s).
- Każdy `done_when` zostaje dosłownym cytatem przewodnika tagu `ci/contract-tag`.
- Wersje po etapie: `tdkit` 1.3.0, `plugin.json` 1.3.0, `SKILL.md` przypina `@v1.3.0`; runda parytetu D4 (~15 USD) przed tagiem, za zgodą ownera na koszt.
- Pełny `pytest` nie biegnie lokalnie (hook): lokalnie `uv run pytest tests/<plik>.py` lub `-k`; całość na CI.
- Lądowanie tylko `/ship` na słowo ownera; tag `v1.3.0` przed `main`.

## Review Focus

1. **Integracja pobiera obraz bez zaufania do CA** (np. `urllib` bez `TD_CA_BUNDLE`): pobranie pada na TLS, atrapa nie widzi żądania → `l1-image-host` FAIL z komunikatem, który mówi o `TD_CA_BUNDLE` (nie „nie pobrano”). Test w Task 3 (`test_image_host_fail_names_ca_bundle`).
2. **Webhook integracji uruchomiony poza `tdkit`** (serwer deweloperski) nie dostaje `TD_CA_BUNDLE` z env komend: `tdkit check` wypisuje ścieżkę na starcie, README mówi, że trzeba ją ustawić w środowisku serwera. Test w Task 4 (`test_check_prints_ca_bundle`).
3. **Certyfikat bliski wygaśnięcia**: test czerwieni na 365 dni przed końcem ważności. Task 1 (`test_tls_cert_valid_for_another_year`).
4. **Port https zajęty / równoległe `tdkit check`** (dwa runy evali naraz): serwer https bierze port 0 (wolny), więc nie koliduje; URL niesie port. Test w Task 2 (`test_two_mocks_get_distinct_tls_ports`).
5. **Klient w trybie `VERIFY_X509_STRICT`** (Python 3.13+): łańcuch CA → serwer weryfikuje się. Test w Task 1 (`test_tls_chain_verifies_strict`).

---

## Mapa plików

| Plik | Odpowiedzialność |
|---|---|
| `ci/make_test_tls.sh` | jednorazowe wygenerowanie CA i certyfikatu serwera (`openssl`), dokumentacja |
| `src/tdkit/mock/tls/ca.pem`, `server.pem`, `server-key.pem` | certyfikaty testowe (dane pakietu) |
| `src/tdkit/mock/tls/__init__.py` | `CA_BUNDLE: Path`, `server_context() -> ssl.SSLContext` |
| `src/tdkit/mock/server.py` | drugi serwer po https, `tls_port`, `files_base` po https |
| `src/tdkit/check/context.py` | adresy obrazów po https, `TD_CA_BUNDLE` w env komend |
| `src/tdkit/check/scenarios.py` | `image_host`: pobranie dozwolonego + brak pobrania zakazanego |
| `src/tdkit/cli.py` | `tdkit mock` i `tdkit check` wypisują `TD_CA_BUNDLE` |
| `tests/reference_integration.py`, `tests/reference_media.py` | pobierają z kontekstem `TD_CA_BUNDLE` |
| `README.md`, `references/cms/*.md`, `references/tdkit.md` | jak zaufać CA w teście: Python, PHP (curl/Guzzle), Node |

---

### Task 1: certyfikaty testowe i kontekst TLS

**Files:**
- Create: `ci/make_test_tls.sh`, `src/tdkit/mock/tls/{ca.pem,server.pem,server-key.pem,__init__.py}`
- Test: `tests/test_tls.py`

**Interfaces:**
- Produces: `tdkit.mock.tls.CA_BUNDLE: Path`; `tdkit.mock.tls.server_context() -> ssl.SSLContext` (`PROTOCOL_TLS_SERVER`, `load_cert_chain(server.pem, server-key.pem)`).

- [ ] **Step 1: Testy:**

```python
def test_tls_chain_verifies_strict():  # serwer na 127.0.0.1 z server_context(); klient create_default_context(cafile=CA_BUNDLE) z VERIFY_X509_STRICT łączy się przez IP i przez "localhost"
def test_tls_cert_valid_for_another_year():  # ssl._ssl._test_decode_cert(server.pem)["notAfter"] > teraz + 365 dni; to samo dla ca.pem
def test_ca_key_is_not_in_the_repo():  # w src/tdkit/mock/tls/ nie ma pliku z "ca" i "key" w nazwie
def test_tls_files_ship_in_the_wheel():  # pyproject: packages = ["src/tdkit"] obejmuje tls/*.pem (hatchling bierze wszystkie pliki pakietu) — test: Path(tls.__file__).parent zawiera trzy pliki .pem
```

- [ ] **Step 2:** `uv run pytest tests/test_tls.py -q` → FAIL (brak modułu).
- [ ] **Step 3:** `ci/make_test_tls.sh` z wartościami z Global Constraints (klucz CA w katalogu tymczasowym, usuwany na końcu); uruchomić raz z Git Bash; `tls/__init__.py`.
- [ ] **Step 4:** `uv run pytest tests/test_tls.py -q` → PASS; ruff, pyright czysto.
- [ ] **Step 5:** commit `feat: test TLS certificates for the mock (loopback only)`.

### Task 2: atrapa serwuje też po https

**Files:**
- Modify: `src/tdkit/mock/server.py` (`start`, `stop`, `bound_address`, nowe `tls_address`, miejsce ustawiania `files_base` ok. linii 306)
- Modify: `src/tdkit/mock/media.py:180` (domyślny `files_base` po https — wartość ustawia serwer)
- Test: `tests/test_mock_routes.py`, `tests/test_media_routes.py`

**Interfaces:**
- Consumes: `tls.server_context()`.
- Produces: `MockServer.tls_address() -> tuple[str, int]`; `MockServer.files_base(host: str) -> str` = `f"https://{host}:{tls_port}"`.

- [ ] **Step 1: Testy:**

```python
def test_files_are_served_over_https():     # GET https://127.0.0.1:<tls_port>/files/x.jpg z kontekstem CA → 200, state.pulls["x.jpg"] == 1
def test_api_stays_on_http():                # GET http://127.0.0.1:<port>/v3/cms/status → jak dziś
def test_two_mocks_get_distinct_tls_ports(): # dwa MockServer(port=0) → różne tls_port
def test_new_asset_file_url_is_https():      # file_url zmiany new_asset zaczyna się od "https://" (test_media_routes)
```

- [ ] **Step 2:** testy → FAIL.
- [ ] **Step 3:** drugi `ThreadingHTTPServer((HOST, 0), Handler)`, `socket = ctx.wrap_socket(socket, server_side=True)`, własny wątek; `stop` zamyka oba.
- [ ] **Step 4:** `uv run pytest tests/test_mock_routes.py tests/test_media_routes.py -q` → PASS.
- [ ] **Step 5:** commit `feat: the mock also serves over https on a free port`.

### Task 3: `check` — adresy po https, `TD_CA_BUNDLE`, `l1-image-host` w obie strony

**Files:**
- Modify: `src/tdkit/check/context.py:76-99,194-195`, `src/tdkit/check/scenarios.py:243-254`
- Modify: `tests/reference_integration.py:125`, `tests/reference_media.py` (pobrania z `ssl.create_default_context(cafile=os.environ["TD_CA_BUNDLE"])`)
- Test: `tests/test_check.py`

**Interfaces:**
- Consumes: `MockServer.tls_address()`, `tls.CA_BUNDLE`.
- Produces: `Context.files_base: str`; `Context._env()` dodaje `TD_CA_BUNDLE`.

- [ ] **Step 1: Testy** (na referencji z flagami jak istniejące testy break-flag):

```python
def test_image_host_passes_when_allowed_image_is_downloaded():   # referencja → l1-image-host PASS
def test_image_host_fails_when_nothing_is_downloaded():           # nowa flaga referencji --no-image-download → FAIL "did not download the image on <host>"
def test_image_host_fail_names_ca_bundle():                       # flaga --no-ca (urllib bez kontekstu) → FAIL, komunikat zawiera "TD_CA_BUNDLE"
def test_image_host_still_refuses_the_forbidden_host():           # --any-image-host → FAIL jak dziś
```

Komunikat dla Review Focus 1: gdy pobranie dozwolonego obrazu nie przyszło, `detail` mówi: „the integration did not download the image on <host> within 15 s; it is served over https: trust TD_CA_BUNDLE (<ścieżka>) in the test environment”.

- [ ] **Step 2:** `uv run pytest tests/test_check.py -q -k image_host` → FAIL.
- [ ] **Step 3:** implementacja wg Global Constraints.
- [ ] **Step 4:** `uv run pytest tests/test_check.py -q -k image_host` → PASS; pełne `test_check.py` i `test_check_media.py` w tle (≈10 min) → PASS.
- [ ] **Step 5:** commit `feat: images over https in check; l1-image-host requires the allowed image to be downloaded`.

### Task 4: CLI i dokumentacja

**Files:**
- Modify: `src/tdkit/cli.py` (`tdkit mock`: linia `  CA bundle:      TD_CA_BUNDLE=<ścieżka>`; `tdkit check`: ta sama linia na stderr na starcie)
- Modify: `README.md` (tdkit mock, tdkit check, „How close the mock is to production”), `plugins/.../references/tdkit.md`, `references/cms/{generic,django,drupal,laravel,node-express,wordpress}.md` — jedno zdanie o zaufaniu CA w teście: Python `ssl.create_default_context(cafile=...)`/`REQUESTS_CA_BUNDLE`, PHP `CURLOPT_CAINFO`/Guzzle `verify`, Node `NODE_EXTRA_CA_CERTS`; nigdy w produkcji.
- Test: `tests/test_cli.py`, `tests/test_skill_text.py`

- [ ] **Step 1: Testy:** `test_mock_prints_ca_bundle`, `test_check_prints_ca_bundle` (capsys zawiera `TD_CA_BUNDLE=` i istniejącą ścieżkę), `test_cms_references_name_the_ca_bundle` (każdy plik `references/cms/*.md` poza `ghost.md` zawiera `TD_CA_BUNDLE`).
- [ ] **Step 2:** → FAIL. **Step 3:** implementacja. **Step 4:** → PASS; ruff, pyright.
- [ ] **Step 5:** commit `docs: TD_CA_BUNDLE in tdkit output, README and the CMS references`.

### Task 5: wydanie 1.3.0

- [ ] **Step 1:** wersja 1.3.0 w `__init__.py`, `plugin.json`, `SKILL.md`, `README.md` (`uvx …@v1.3.0`), `tests/test_cli.py`; `## Limits of 1.3`.
- [ ] **Step 2:** push gałęzi, `gh workflow run ci.yml --ref <gałąź>`, CI zielone (w tym `reference-django`/`reference-drupal`: jeśli ich pobieranie obrazów pada na TLS, poprawić konfigurację referencji, nie scenariusz).
- [ ] **Step 3:** zgoda ownera na koszt rundy parytetu (~15 USD); runda `parity-django`, `parity-laravel`, `parity-node`; wiersze w README dla `tdkit 1.3` (test `test_readme_has_parity_rows_for_this_minor` czerwieni bez nich).
- [ ] **Step 4:** commit `release: tdkit 1.3.0 (mock files over https)`; lądowanie `/ship` i tag `v1.3.0` na słowo ownera.

---

## Po etapie 1b

Zatrzymanie i podsumowanie dla ownera. Dalej etap 2 (headlinesforge), 3 (`cms-api`), 4 (`cms-php`), 5 (wtyczka — teraz z pobieraniem obrazów po https), 6 (przewodnik 3.5) — osobne plany.
