# Odmowa importu wraca do CMS-a jako `rejected` z powodem — projekt

Data: 2026-11-21. Status: **zatwierdzony przez ownera 21.11 (wariant 1).** Zadanie z ledgera:
`2026-11-21-tribunedesk-wordpress-zdjecia-known-bez-asset-id`. Repozytoria: headlinesforge
(backend `/v3/cms/media` i źródło przewodnika `docs/api/cms/`), `Tribunedesk/tribunedesk-cms-api`
(drzewo publiczne, tag), ten kit (`tdkit mock`, `tdkit check`), `Tribunedesk/tribunedesk-wordpress`
(test). Przepływ kontraktu: `docs/specs/2026-11-13-kontrakt-najpierw-automaty-design.md` sekcja 5.

## 1. Po co

Pomiar 21.11 wtyczki 2.4.0 na Styl.fm pokazał 72 wysłane zdjęcia z `_hf_media_pushed = known@…`,
które nigdy nie dostały `_hf_asset_id`. Odczyt produkcji (21.11, rola `engram2_ro`):

- wszystkie 72 mają w `media_import_items` (org Styl.fm, dopasowanie po `url`) `status = skipped`,
  `reason = collage` (67) albo `screenshot` (5); w `media_assets` nie ma żadnego wiersza z ich ID ani
  skrótem pliku;
- ścieżka ciągła Styl.fm od 16.11: `imported` 81, `skipped` 74 (collage 69, screenshot 5);
- kontrola metody: 77 sparowanych zdjęć ma w bibliotece ten sam sha256 co plik w WordPressie, plik
  powstał 1–2 min po wysłaniu.

Import celowo nie bierze kolaży, zrzutów i grafik (`is_junk`, headlinesforge
`media_library/service.py` ok. 2180, spec E2 D2). Odpowiedź `POST /v3/cms/media` mówi o tym
jednak `known` bez `asset_id` (`media_library/service.py` `push_wp_items`: `known` = klucz pozycji
importu istnieje), co kontrakt dopuszcza („stays `null` if the import refused the file”), ale
integrator nie odróżni „import jeszcze trwa” od „import odmówił”. Skutek: wtyczka ponawia wysyłkę
przez 3 dni (`MediaPush::PAIR_CHECK`), a stan w CMS-ie i pomiar mówią „bez pary”.

**Sukces:** plik, którego import odmówił, dostaje przy następnej wysyłce `rejected` z powodem;
wtyczka zapisuje `rejected:<powód>@…` i przestaje go wysyłać; zdjęcia „bez pary” w pomiarze to
tylko pliki w trakcie importu.

**Nie-cele:** przyjmowanie kolaży do biblioteki (decyzja produktowa, spec E2 D2 zostaje);
odpowiedzi importu historycznego (`POST /v3/cms/backfill/requests/{id}/pages`, wynik `known`
zostaje jak jest); duplikaty treści (`skipped` z `duplicate`/`known_asset` — plik jest w bibliotece
pod innym ID, osobny temat); zmiana kodu wtyczki.

**Anty-cel:** `rejected` dla pliku, który jeszcze się importuje albo został zaimportowany — wtedy
wtyczka przestałaby pytać o `asset_id` i para nigdy by nie powstała.

## 2. Podejścia (rozstrzygnięte 21.11)

1. **`rejected` z powodem z importu** — wybrane przez ownera. Kształt odpowiedzi bez zmian
   (`reason` to dowolny tekst), wtyczka obsługuje to już dziś (`CmsSync.php` `finish_files`
   zapisuje `rejected:<reason>`; `MediaPush::candidates` ponawia tylko `rejected:host` i
   `rejected:missing_metadata`).
2. Zostawić `known` i dodać pole ze stanem importu — odrzucone: czysto addytywne, ale wymaga zmian
   w kodzie wtyczki i pomiaru.
3. Jeden ogólny powód `import_refused` — odrzucone: integrator nie wie, dlaczego plik odpadł, a
   powód jest w bazie.

## 3. Projekt

**D1. Serwer (headlinesforge `push_wp_items`).** Dla klucza, którego pozycja importu już istnieje,
wynik zależy od stanu tej pozycji:

| Pozycja importu | Wynik |
|---|---|
| `skipped`, `reason` ∈ {`collage`, `screenshot`, `graphic`} | `rejected` z tym samym `reason` |
| `failed` (dowolny powód: `host`, `model`, `store`, błędy pobrania) | `rejected`, `reason = import_failed` |
| każdy inny stan (`pending`, w trakcie, `imported`, `skipped` z `duplicate`/`known_asset`/anulowane) | `known`, jak dziś |

Klucz powtórzony w tym samym żądaniu zostaje `known`. Klucz z importu wstecznego (`cms:<id>`,
`BACKFILL_KEY_BLOCKING`) — ta sama tabela według stanu jego wiersza. `asset_id` przy takim
`rejected` jest `null` (plik nie istnieje). Test jednostkowy w headlinesforge na każdy wiersz tabeli.

**D2. Kontrakt `3.6.0-draft`** (minor, wpis **Breaking** w CHANGELOG, bo dla tego przypadku `known`
zamienia się w `rejected`). Przewodnik 4 › „Sending new files” EN i PL oraz opis `POST /media` w
OpenAPI: nowe powody `collage`, `screenshot`, `graphic`, `import_failed`; zdanie, że ta odmowa jest
zapamiętana — ponowne wysłanie da ten sam wynik, w odróżnieniu od odmów z ustawień, które nie są
zapamiętane. Blok `**Integrators:**`: `L4` — nie wysyłaj ponownie pliku z tymi powodami. Treść
zaczyna się w headlinesforge (`docs/api/cms/`), nie w `cms-api` (drzewo publiczne jest generowane).

**D3. Kit.** Atrapa (`tdkit mock`) umie odpowiedzieć tymi powodami dla pliku, który jej import
odrzucił; `tdkit check` ma scenariusz albo jawne wyłączenie dla nowego punktu „Done when” (jeśli
przewodnik go dostanie) — według reguł D3 specu „kontrakt najpierw”. Kolejność wydań kitu jak w
etapie 6 (poszerzony `SUPPORTED_MINORS` przed tagiem, scenariusz po tagu).

**D4. Wtyczka.** Bez zmian w kodzie; test PHPUnit, że `rejected:collage` nie wraca do
`MediaPush::candidates`. Przypinki kontraktu podnosi drift wtyczki.

**D5. 72 istniejące zdjęcia Styl.fm.** Ich okno ponowień minęło. Po `/deploy` headlinesforge:
usunąć im `_hf_media_pushed`, żeby wtyczka wysłała je jeszcze raz i zapisała `rejected:<powód>@…`.
Zapis w produkcji — tylko na słowo ownera, z listą ID z odczytu przed zapisem.

## 4. Dla budowniczego

- Dokładne brzmienie zdań przewodnika i punktu „Done when” (czy w ogóle nowy punkt) ustala plan;
  teksty cytowane przez kit są potem dosłowne.
- Lądowanie każdego repo przez `/ship` na słowo ownera; tag kontraktu stawia `tag.yml`, nie sesja;
  `/deploy` headlinesforge osobno.
- **Rewizja:** gdy import zacznie odrzucać pliki nowym powodem (`image_kind` spoza tabeli D1) —
  nowy powód w kontrakcie tym samym przepływem.
