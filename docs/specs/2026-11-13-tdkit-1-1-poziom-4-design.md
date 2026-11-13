# tdkit 1.1 i skill: poziom 4 (biblioteka mediów) — projekt

Data: 2026-11-13. Status: **do zatwierdzenia przez ownera**. Zadanie ledgera:
`2026-11-13-tribunedesk-cms-kit-poziom-4-wskazowki-i-atrapa`. Kontrakt: tag `v3.4.2-draft` repo
`Tribunedesk/tribunedesk-cms-api` (`guide/4-media-library.md`, `openapi.json`). Kontekst: spec E9
(headlinesforge `docs/specs/2026-11-08-e9-skill-integracji-tribune-desk-design.md`, D6 i decyzja
ownera z 08.11, linia 572).

## 1. Po co

Ocena clean-room 13.11: skill `tribunedesk-integration` v1.0.1 prowadzi dobrze poziomy 1+2, ale
integracja „tylko zdjęcia” (poziom 4) powstaje ze zgadywaniem i bez dowodu. Powody:

- `tdkit` 1.0 odpowiada `501` na wszystkie trasy mediów, a `check --levels 4` to błąd użycia;
- `references/cms/*.md` nie mają ani słowa o poziomie 4 po stronie CMS-a (gdzie kursor, wersje
  pól, wartości odłożone, licznik prób, kolejka własnych zmian, harmonogram, ekrany decyzji);
- `scope.md` traktuje poziom 4 jako całość, choć backfill, push-existing i zapis ustawień są
  opcjonalne;
- jedyny działający kod poziomu 4 w PHP (`src/WordPress/CmsSync.php` wtyczki WP 2.2.3) nie jest
  nigdzie wskazany;
- eval `photos-only` sprawdza tylko szczerość („nie ma testu”), nie zgodność.

**Sukces:** integrator z samym skillem buduje rdzeń poziomu 4, uruchamia
`tdkit check --levels 4` i dostaje zielony raport, który znaczy to samo co „Done when”
przewodnika 4. Eval `photos-only` to sprawdza automatycznie.

**Anty-cel:** atrapa, która przepuszcza integrację łamiącą przewodnik (np. zapisującą kursor przed
zastosowaniem zmian albo ponawiającą zapis po `conflict`) — zielony raport byłby fałszywym
dowodem, gorszym niż brak testu.

## 2. Zakres

W 1.1:

1. Atrapa poziomu 4: wszystkie trasy przewodnika 4 z zachowaniem opisanym w nim (D1, D3).
2. Scenariusze `check --levels 4`: rdzeń zawsze, backfill na flagę (D2, D4).
3. Trzy odroczone punkty D6: ponowienia dostaw, przełącznik integracji, tokeny z pliku (D5).
4. Wskazówki poziomu 4 w skillu: `generic.md` (pełny model), `laravel.md` i `django.md` (idiom),
   `wordpress.md` (wtyczka już to robi), `scope.md` (rdzeń / opcja), `tdkit.md`, `SKILL.md` (D6).
5. Integracja wzorcowa poziomu 4 w testach kitu, na której CI uruchamia `check --levels 4` (D7).
6. Eval `photos-only` sprawdza zielony raport poziomu 4 (D8).
7. Wydanie: `tdkit` i plugin 1.1.0, skill przypina `@v1.1.0` (D9).

Poza zakresem (świadomie): `429` i `project_deactivated` w atrapie (bez zmian względem 1.0);
scenariusze dla push-existing i zapisu ustawień (trasy działają w atrapie, scenariuszy brak — D4);
sprawdzanie wyglądu ekranów decyzji (tdkit nie widzi UI — D2, scenariusz `l4-held-not-resent`);
poziom 5; referencja Django/Drupal z poziomem 4 (D7, rewizja).

## 3. Decyzje

### D1. Atrapa implementuje wszystkie trasy przewodnika 4, nie tylko te pod scenariusze

Trasy (OpenAPI tagu): `GET /changes` (rodzaje `fields`, `new_asset`, `settings`, `deleted`,
`restored`, z wersjami i `cursor` na zmianę), `POST /media`, `POST /media/fields`,
`POST /media/deletions`, `POST /media/{asset_id}/link`, `POST /media/push-existing`,
`POST /resync` (podgląd stronami i potwierdzenie), `GET /held`,
`POST /held/{held_id}/decision`, `GET`/`PUT /settings`, `GET /backfill/requests`,
`POST /backfill/requests/{request_id}/pages`; `/status` dostaje prawdziwe `held_batches` i
`pending_changes` poziomu 4.

Zachowanie spisane ręcznie z przewodnika, jak w 1.0 dla poziomów 1–3 (kształty z OpenAPI,
walidacja ciał schematami tagu, kolejność `422 → 401 → 403 → 422 → 409`). Najważniejsze reguły,
które atrapa musi mieć, bo na nich stoją scenariusze:

- **Kursor:** brak kursora = „od teraz”; kursor zmiany i `next_cursor` potwierdzają wszystko do
  nich; starszy kursor powtarza późniejsze zmiany; `410 cursor_expired` po wygaśnięciu i po
  ponownym włączeniu integracji; `409 state_conflict` przed włączeniem.
- **Pierwszy odczyt po włączeniu** przełącza organizację: edycje sprzed przełączenia wchodzą do
  kanału (pierwszy odczyt bez kursora zwraca pustą listę i kursor sprzed nich).
- **Wersje pól** rosną tylko dla zmian, które idą do kanału lub przychodzą z CMS-a; resync
  `td_to_cms` powtarza wartość z tą samą wersją i `changed_by=editor`.
- **`POST /media/fields`:** sześć kroków decyzji w kolejności przewodnika (`field_disabled`,
  `unchanged`, `keep_nonempty`, `base_version`, `changed_at`, reguła konfliktu
  `last_change|cms|td`), statusy pozycji `ok|known|unknown|conflict|rejected|held`, `422` dla
  NUL i czasu bez strefy.
- **Próg masowych zmian:** okno 60 minut od pierwszej liczonej zmiany, zmiany ponad próg →
  `held` z `held_batch_id`, kolejne żądania okna dokładają do tej samej paczki. Próg ustawialny
  w atrapie (scenariusze używają `1`).
- **Parowanie plików z `POST /media`:** pozycja przyjęta (`ok`) nie ma pliku; atrapa paruje ją
  dopiero na sygnał (scenariusz lub `POST /_tdkit/import`), do tego czasu `fields` i `deletions`
  odpowiadają `unknown`, a powtórzone `POST /media` zwraca `asset_id: null`, potem właściwe id.
- **`/link`:** `404`, `422` (host), `409` w przypadkach przewodnika; `known` dla powtórki.
- **Resync:** `collecting → ready`, potwierdzenie w 24 h, `held` ponad próg, kursor z chwili
  rozpoczęcia podglądu, zmiany `td_to_cms` wpadają do kanału po tym kursorze.
- **Backfill:** prośby z filtrami, strony do 1000, `is_last`, `max_files`, pauza
  (pusta strona `is_last=false` → `200 accepted: 0`).

Pliki: atrapa podaje `file_url` w `new_asset` z własnego `/files/<nazwa>`, tak samo jak obrazy
poziomu 1 (schemat — `http` czy `https` — dziedziczy po zadaniu
`…-atrapa-obrazy-https`, które biegnie równolegle). `/link` i `POST /media` przyjmują adresy na
hostach z `image_hosts` atrapy, także `http` na `127.0.0.1`/`localhost` — złagodzenie wpisane do
README „How close the mock is to production”, jak dostawa na `http://localhost` w 1.0. Atrapa
nie pobiera adresu z `/link` (w produkcji to dzieje się w tle i nic nie raportuje przez API).

Sterowanie atrapą (trasy własne `/_tdkit/*`, bez tokenu, jak `/_tdkit/send`): nowy plik w Tribune
Desk, edycja pola w Tribune Desk, kosz/przywrócenie, zmiana ustawień, nowa prośba backfill,
parowanie przyjętych plików, włączenie/wyłączenie integracji, wygaszenie kursorów. `tdkit mock`
wypisuje je przy starcie.

- **Dlaczego:** `tdkit mock` służy też do ręcznej pracy; integrator budujący opcjonalny backfill
  albo push-existing dostawałby `501` i wracał do zgadywania. Koszt pełnych tras ponad trasy
  rdzenia to ok. ⅓ pracy atrapy, a reguły i tak trzeba spisać dla scenariuszy.
- **Odrzucone: tylko trasy rdzenia, reszta `501`.** Taniej, ale opcjonalne części poziomu 4
  zostają bez żadnego miejsca do próby — dokładnie ten problem, który zgłosiła ocena.
- **Odrzucone: atrapa generowana z OpenAPI (Prism i podobne).** Odrzucone już w E9 D6: kształty
  się zgadzają, zachowania (kursor, wersje, próg, konflikty) nie istnieją.
- **Rewizja:** różnica atrapa–produkcja zgłoszona przez integratora albo nowa wersja przewodnika 4.

### D2. `check` steruje CMS-em poziomu 4 przez pięć komend deweloperskich

Poziom 4 nie ma webhooka: CMS sam ciągnie i wysyła. `check` musi więc (a) uruchomić cykl
synchronizacji, (b) zajrzeć do biblioteki CMS-a, (c) zrobić zmianę „redaktora” po stronie CMS-a.
Ten sam wzorzec co `--inspect-cmd`/`--publish-cmd`/`--poll-cmd` w 1.0 (szablon, bez powłoki,
60 s, kod wyjścia ≠ 0 = porażka scenariusza):

| Opcja | Co robi komenda |
|---|---|
| `--sync-cmd` | jeden pełny cykl: odczyt `/changes` do `has_more=false`, zastosowanie, zapis kursora, wysłanie własnej kolejki (nowe pliki, pola, usunięcia), odpowiedź na prośby backfill (gdy zbudowane). Kończy wysyłkę przed wyjściem. |
| `--media-inspect-cmd "{cms_media_id}"` | JSON pliku w bibliotece CMS-a albo `null`: `cms_media_id`, `asset_id` (lub `null`), `sha256` przechowanego pliku, `fields` (`alt`, `caption`, `title`, `description` — te, które CMS mapuje), `deleted_in_td` (znacznik z `kind=deleted`). |
| `--media-add-cmd "{file}"` | dodaje plik `{file}` (JPEG zapisany przez `check`) do biblioteki jak redaktor; wypisuje JSON `{"cms_media_id": "…"}`. |
| `--media-edit-cmd "{cms_media_id} {field} {value}"` | zmienia pole jak redaktor (`{value}` to jeden argument, także ze spacjami). |
| `--media-delete-cmd "{cms_media_id}"` | usuwa plik jak redaktor. |

Plus opcjonalna `--reset-cmd` (czyszczenie stanu przed scenariuszami, §5 pkt 1).
`check` ustawia w środowisku komend `TD_API_BASE`, `TD_CMS_TOKEN` (jak w 1.0). Tryb: nowe
`--mode none` dozwolone tylko dla samego poziomu 4; przy `--levels 1,4` scenariusze poziomu 4
biegną w każdym trybie.

- **Dlaczego:** to jedyna droga do „Done when” nr 2 (zmiany po stronie CMS-a docierają do
  Tribune Desk) bez wchodzenia w bazę CMS-a; integrator zna już ten wzorzec z poziomów 1–3.
- **Odrzucone: jedna komenda `--media-cmd "{action} …"`.** Mniej opcji, ale szablon musiałby
  mieć puste miejsca zależne od akcji (`render` wstawiałby puste argumenty), a komunikat o
  błędzie nie mówiłby, której akcji brakuje.
- **Odrzucone: tylko kierunek Tribune Desk → CMS (bez add/edit/delete).** Dwie komendy mniej,
  ale „Done when” nr 2, konflikty i próg (`held`) zostają bez testu — połowa ryzyk poziomu 4.
- **Odrzucone: tdkit czyta bibliotekę CMS-a przez API CMS-a.** Każdy CMS ma inne API; byłby to
  adapter na CMS, czyli pakiety per język, odrzucone w E9 D6.
- **Rewizja:** integratorzy zgłaszają, że pięć komend to za dużo (np. dla CMS-u bez CLI).

### D3. Pola i ustawienia w scenariuszach

Scenariusze używają pola `alt` (każdy CMS z biblioteką mediów je ma); `--media-fields alt,caption`
pozwala wskazać inne mapowane pola, gdyby CMS nie miał `alt` (wtedy pierwsze z listy). Atrapa
startuje z wariantem `full`, regułą `last_change`, `td_deletion_marks_in_cms=true`,
`keep_nonempty_td_to_cms=false`, progiem 500; scenariusz, który potrzebuje innego ustawienia,
zmienia je w stanie atrapy i wysyła `kind=settings` — co przy okazji sprawdza, że integracja
czyta ustawienia ponownie.

- **Dlaczego:** ustawienia przez kanał to droga produkcyjna; scenariusz nie zakłada pamięci
  podręcznej integracji dłuższej niż jeden `kind=settings`.
- **Odrzucone: osobny start atrapy na każdy scenariusz z innymi ustawieniami.** Czystsze, ale
  wolniejsze i nie sprawdza reakcji na `kind=settings`.

### D4. Scenariusze poziomu 4

Każdy cytuje dosłownie punkt „Done when” przewodnika 4 albo — gdy go tam nie ma — zdanie
przewodnika, które to wymaga (test tekstu jak w 1.0, na fixturze `guide/4-media-library.md`
dodanej do `tests/fixtures/cms-api`). Rdzeń (zawsze przy `--levels 4`):

| id | co robi | przechodzi, gdy | podstawa |
|---|---|---|---|
| `l4-first-poll` | `--sync-cmd` dwa razy | pierwszy odczyt bez kursora, każdy następny z kursorem z poprzedniej odpowiedzi | DW1; „keep your cursor and send it every time” |
| `l4-new-asset-linked` | nowy plik w Tribune Desk, sync | `/link` z `cms_media_id`, `inspect` pokazuje plik z tym samym `sha256` i polem z kanału; kursor przesunięty | DW1; „Taking files from Tribune Desk” |
| `l4-cursor-after-apply` | `new_asset`, którego `file_url` odpowiada `500`; sync; potem plik działa, sync | po porażce następny odczyt używa kursora sprzed zmiany; po naprawie plik jest i kursor idzie dalej | DW1 |
| `l4-field-versions` | zmiany pola v3, potem powtórka v2, potem powtórka v3 z nową wartością (resync `td_to_cms`) | v2 pominięta, powtórka v3 zastosowana | „Apply by version” |
| `l4-cms-new-file` | `--media-add-cmd`, sync, parowanie w atrapie, sync | `POST /media` z `width`, `height`, `mime_type`; po parowaniu `inspect` ma `asset_id`; brak duplikatu | DW2 |
| `l4-cms-field-edit` | edycja pola w CMS-ie, sync dwa razy | jeden zapis z `base_version` równym znanej wersji i `changed_at` ze strefą; druga synchronizacja nic nie wysyła albo dostaje `unchanged` | DW2; „Conflicts and base_version” |
| `l4-cms-deletion` | usunięcie w CMS-ie, sync | `POST /media/deletions` z `cms_media_id` i `deleted_at`, bez `422` za powtórzone id | DW2 |
| `l4-conflict-winning-value` | reguła `td`, edycja w Tribune Desk i w CMS-ie, sync dwa razy | `inspect` pokazuje `winning_value`; druga synchronizacja nie wysyła pola ponownie | DW3 |
| `l4-both-sides-edited` | edycja w CMS-ie, potem zmiana tego pola w kanale, sync | zmiana z kanału nie nadpisuje lokalnej przed wysyłką; zapis idzie ze starym `base_version` | „A field edited on both sides” |
| `l4-cursor-expired-resync` | `410` na następny kursor, sync | brak odczytu bez kursora; niewysłane edycje wysłane przed podglądem; podgląd `POST /resync` `td_to_cms` z `is_last`; integracja nie potwierdza go sama (§5 pkt 2) | DW4; „Show the preview to a person before confirming” |
| `l4-held-not-resent` | próg 1, dwie edycje w CMS-ie, sync dwa razy | pole `held` nie jest wysyłane ponownie; integracja sama nie woła `/held/{id}/decision` | DW5 (sam ekran: sprawdzenie ręczne, raport to mówi) |
| `l4-settings-and-unknown-kinds` | `kind=settings` i nieznany `kind`, sync | `GET /settings` po `kind=settings`; nieznany rodzaj pominięty, kursor idzie dalej | „The sync cycle” |
| `l4-td-trash-mark` | `kind=deleted`, sync, `kind=restored`, sync | `deleted_in_td` `true`, potem `false`; plik nie zniknął z biblioteki | „Trashed in Tribune Desk” |

Opcja (flaga `--backfill`, jak `--social-flag` w 1.0): `l4-backfill-answered` — otwarta prośba z
filtrem `min_width`, sync → strony z kandydatami i `is_last`; prośba bez kandydatów → jedna pusta
strona z `is_last`.

Push-existing i `PUT /settings` to akcje operatora z ekranu, nie z cyklu; scenariuszy nie mają
(trasy działają w atrapie, README i `scope.md` to mówią).

- **Dlaczego:** pięć punktów „Done when” plus zdania przewodnika, których złamanie gubi dane
  (kursor, wersje, oba boki, `410`). Każdy scenariusz ma w integracji wzorcowej flagę, która
  łamie jedną regułę, i test, że `check` to łapie (wzór 1.0).
- **Odrzucone: tylko pięć scenariuszy, po jednym na punkt „Done when”.** Mniej pracy, ale wersje
  pól, edycja z obu stron i nieznane rodzaje to dokładnie miejsca, w których ocena clean-room
  zgadywała.
- **Odrzucone: scenariusze dla push-existing i zapisu ustawień.** Wymagałyby dwóch kolejnych
  komend operatora; wartość niska, bo obie trasy są proste i idempotentne.
- **Rewizja:** integrator buduje push-existing lub zapis ustawień i prosi o test.

### D5. Trzy odroczone punkty E9 D6

1. **Ponowienia dostaw.** `tdkit mock --webhook` po błędzie sieci, timeoucie, `5xx`, `408`,
   `425`, `429` próbuje ponownie według harmonogramu przewodnika 1 (2, 10, 30, 120, 360,
   840 minut) skróconego do sekund (2, 10, 30, 120, 360, 840 s), ten sam `webhook-id`,
   `X-Delivery-Attempt` rośnie, każda próba podpisana na nowo z nowym znacznikiem czasu; nowsza
   wysyłka artykułu anuluje ponowienia starszej; inne `4xx` i `3xx` kończą wysyłkę.
   `--retry-scale` (domyślnie `1` = sekunda za minutę; `0` wyłącza ponowienia). `check` nadal
   wysyła próby jawnie (scenariusze muszą być deterministyczne).
2. **Przełącznik integracji.** `tdkit mock --disabled` startuje z wyłączoną integracją;
   `POST /_tdkit/integration {"enabled": true|false}` przełącza. Wyłączona: `409 state_conflict`
   na `/changes` i trasach poziomu 4 jak w przewodniku; ponowne włączenie unieważnia kursory
   sprzed przerwy (`410`), sesje resync i paczki `held` sprzed przerwy; edycje z czasu przerwy
   czekają na pierwszy odczyt (przełączenie).
3. **Tokeny z pliku.** `tdkit mock --tokens FILE`: JSON
   `{"tokens": [{"token": "…", "scopes": ["media:read", …]}]}`; wyklucza się z `--token-scopes`.
   `tdkit mock` wypisuje tokeny i ich zakresy. `check` nadal używa `tdcms_mock` ze wszystkimi
   zakresami (scenariusze nie testują braków zakresów).

- **Dlaczego:** owner przeniósł je do 1.1 (08.11); są małe, a przełącznik jest potrzebny
  poziomowi 4 (`409` przed włączeniem, `410` po ponownym włączeniu).
- **Odrzucone: zostawić je na 1.2.** Wszystkie trzy są obiecane w README 1.0 („Planned for
  tdkit 1.1”); przesunięcie znaczy poprawkę README i dalsze zgadywanie przy ponowieniach.
- **Rewizja:** brak — to domknięcie obietnicy.

### D6. Wskazówki poziomu 4 w skillu

- **`references/cms/generic.md`, nowa sekcja „10. Level 4 (media library)”** — pełny model,
  niezależny od CMS-a:
  - *stan:* na organizację — kursor, licznik prób na zmianę, flaga „potrzebny resync”, blokada
    cyklu; na plik — `asset_id`, wersja każdego pola, wartości odłożone z kanału (dla pól
    edytowanych lokalnie) z `held_batch_id`, kolejka brudnych pól z `changed_at` edycji, wynik
    ostatniej wysyłki pliku; kolejka usunięć;
  - *kolejka własnych zmian:* śledzić tylko edycje człowieka (zapisy z kanału bez śledzenia),
    `changed_at` = czas ostatniej edycji pola, paczki po 100, wartości ≤ 5000 znaków bez NUL;
  - *harmonogram:* odczyt co 5 minut, wysyłka minutę po edycji, jeden cykl naraz (blokada),
    pauza na `retry_after`;
  - *mapowanie pól:* tabela `alt`/`caption`/`title`/`description` → pola CMS-a, decyzja
    integratora z ownerem CMS-a;
  - *ekrany decyzji:* paczki `held` (lista, `send`/`discard`), podgląd resync (kierunek, liczba
    różnic, potwierdzenie przez człowieka) — sync nigdy nie decyduje sam;
  - *rdzeń i opcja* (jak w `scope.md`);
  - *staging:* jedna organizacja = jeden klient (kursor organizacji jest wspólny), więc staging i
    lokalne środowisko nigdy na organizacji produkcyjnej — poproś Tribune Desk o osobną;
  - *wzór:* `src/WordPress/CmsSync.php` wtyczki `Tribunedesk/tribunedesk-wordpress` na tagu
    `v2.2.3` z listą plików, które robią resztę (`MediaMetaSync.php`, `CmsResync.php`,
    `CmsDeletions.php`, `CmsBackfill.php`, `CmsSettingsScreen.php`) — czytać jako wzór logiki,
    nie kopiować (to kod WordPressa).
- **`laravel.md` i `django.md`, sekcja „10. Level 4”** — tylko idiom: migracje dla stanu, scheduler
  (`schedule:run` / cron + management command), blokada (`Cache::lock` / `select_for_update`),
  sygnały/obserwatory modelu dla kolejki, pięć komend deweloperskich; odsyła do `generic.md`.
- **`wordpress.md`** — poziom 4 już jest we wtyczce; skill nie buduje go od nowa.
- **`scope.md`** — wiersz „Only photos” bez „tdkit 1.0 does not test”; nowy podział poziomu 4 na
  rdzeń (cykl, `/link`, wysyłka nowych plików/pól/usunięć, konflikty, `410` → resync, ekran
  `held`) i opcję (backfill, push-existing, zapis ustawień).
- **`tdkit.md`, `SKILL.md`** — `check --levels 4` z komendami poziomu 4; usunięte zdania „tdkit
  1.0 does not test level 4”; kroki uruchomienia poziomu 4 bez „jedynego dowodu ręcznego”.
- **`tribune-desk-request.md`** — prośba o osobną organizację testową dla poziomu 4.

- **Dlaczego `generic.md` jako źródło, a nie każdy plik CMS osobno:** jedna prawda o modelu;
  pliki CMS-ów mówią tylko, czym to zrobić. Ocena zgadywała właśnie model, nie idiom.
- **Odrzucone: tylko `laravel.md` i `generic.md` (dosłownie z kryteriów zadania).** Eval
  `photos-only` buduje na Django, więc bez `django.md` sam eval jechałby na `generic.md`;
  dodanie `django.md` kosztuje kilkanaście linii.
- **Odrzucone: kopia `CmsSync.php` jako szablon w skillu.** Kod WordPressa (hooki, opcje, meta)
  nie przenosi się do innych CMS-ów; wskazanie z listą odpowiedzialności daje to samo bez kopii
  do utrzymania.

### D7. Integracja wzorcowa poziomu 4 w testach kitu

`tests/reference_integration.py` (dziś poziomy 1–3, sama biblioteka standardowa, flagi łamiące po
jednej regule) dostaje poziom 4: `sync`, `media-inspect`, `media-add`, `media-edit`,
`media-delete` na tym samym pliku JSON, oraz flagi łamiące regułę każdego scenariusza
(`--cursor-before-apply`, `--resend-conflict`, `--ignore-versions`, `--fresh-after-410`,
`--auto-decide-held`, …). Testy kitu sprawdzają, że czysta wersja przechodzi `--levels 4`, a każda
flaga oblewa dokładnie swój scenariusz. CI kitu (job `ci`) to obejmuje bez nowych jobów.

- **Dlaczego:** bez tego scenariusze poziomu 4 nie mają dowodu, że da się je przejść, ani że
  łapią błąd — wzór 1.0, który się sprawdził.
- **Odrzucone: poziom 4 w `reference/django`.** Bliżej evalu, ale to osobny projekt (model zdjęć,
  migracje, ekrany) i nowy job CI; warto później, nie jako warunek 1.1.
- **Odrzucone: wtyczka WP jako sprawdzian atrapy w CI.** Byłaby to najlepsza kontrola zgodności
  atrapy z działającym kodem, ale `CmsApiClient` przyjmuje tylko `https` jako adres API, a CI
  musiałby stawiać WordPressa; jako jednorazowy pomiar ręczny — patrz „Do wykonawcy”.
- **Rewizja:** pierwsza integracja poziomu 4 u klienta przechodzi `check`, a w produkcji nie
  działa — wtedy referencja w prawdziwym CMS-ie.

### D8. Eval `photos-only`

Automatyczne sprawdzenia: `tdkit check` uruchomione z `--levels 4`, raport zielony dla
`levels [4]`, trybu `none` i kontraktu tagu, manifest `levels [4]`, `delivery none`. Recenzja:
`level4-honest` → „level4-tested”: wiadomość końcowa mówi, że test zgodności poziomu 4 przeszedł
(rdzeń; backfill tylko jeśli zbudowany), kroki uruchomienia bez webhooka i sekretu, z prośbą o
osobną organizację testową. `request-list` bez zmian plus organizacja testowa. Eval uruchamia
się ręcznie (płatny) przed wydaniem.

### D9. Wersje i wydanie

`tdkit` 1.1.0, plugin 1.1.0, skill przypina `uvx --from …@v1.1.0`. Kontrakt bez zmian
(`3.4.2-draft`; CI `examples` zostaje na tagu, który ma przykłady). Lądowanie przez `/ship`
według Rollout w vaulcie `projects/tribunedesk-cms-kit/wiki.md`: tag `v1.1.0` przed pushem
`main`, tylko na słowo ownera. Zmiana zachowania 1.0: `--levels 4` przestaje być błędem użycia
(to jest cel), reszta wstecznie zgodna.

## 4. Kolejność i konflikty

Równolegle biegną dwa proste zadania kitu: `…-atrapa-obrazy-https` (dotyka `mock/server.py`,
`check/context.py`, serwowania plików) i `…-kontrakt-komend-i-przewodnik-ogolny` (dotyka
`references/cms/*.md`, `README.md`, `SKILL.md`, walidacji manifestu). Oba są małe i wylądują
pierwsze; ta praca rebase'uje się na nie przed PR-em i dziedziczy ich decyzję o schemacie plików
atrapy. Sekcje „10. Level 4” dopisuje na końcu plików CMS, żeby konflikty były mechaniczne.

## 5. Ustalenia po recenzji wykonawcy (decyzje sesji, techniczne)

Niezależny recenzent przeczytał spec jako wykonawca; trzy jego pytania rozstrzygam tak:

1. **Stan integracji między uruchomieniami `check`.** Każde `check` startuje nową atrapę, a
   integracja trzyma kursor i pary z poprzedniego razu. Opcjonalna szósta komenda
   `--reset-cmd` czyści stan poziomu 4 integracji (kursor, wersje, kolejki, pary; nie pliki) i
   biegnie raz przed scenariuszami poziomu 4. Bez niej kursory atrapy niosą znacznik
   uruchomienia, a kursor z innego uruchomienia dostaje `422 validation_error` z komunikatem
   „kursor z poprzedniego uruchomienia tdkit: wyczyść stan albo podaj --reset-cmd” — nie `410`,
   żeby nie wpychać integracji w resync. Integracja wzorcowa i eval podają `--reset-cmd`.
2. **Kto zaczyna resync po `410`.** Zgodnie z przewodnikiem („first send your unsent edits …,
   then run `td_to_cms`. Show the preview to a person before confirming”): `--sync-cmd` po `410`
   ustawia flagę „potrzebny resync”, wysyła niewysłane edycje, zaczyna podgląd `td_to_cms`
   (podgląd niczego nie zmienia) i przestaje czytać kanał; człowiek na ekranie widzi kierunek i
   liczbę różnic, potwierdza albo zaczyna od nowa z `cms_to_td`. Scenariusz
   `l4-cursor-expired-resync` przechodzi, gdy: brak odczytu bez kursora, wysłane edycje przed
   podglądem, podgląd z `is_last`, brak samodzielnego potwierdzenia. `--resync-confirm-cmd`
   wypada (potwierdzenie to ekran, jak decyzja `held`). Tak samo opisują to `generic.md` i
   pliki CMS-ów.
3. **Adresy plików od CMS-a w atrapie.** Dwie osobne listy: `image_hosts` (skąd CMS może
   pobierać — bez zmian, łącznie z celowo zakazanym hostem pętli zwrotnej w `l1-image-host`) i
   hosty, które atrapa przyjmuje w `file_url` z `POST /media` i `/link`: `127.0.0.1` i
   `localhost`, dowolny port, `http` lub `https`. Druga lista dotyczy innego kierunku, więc nie
   osłabia sprawdzenia poziomu 1. `--media-hosts` dopisuje hosty (np. nazwa z `/etc/hosts`).
   Atrapa nie pobiera tych adresów (jak w D1), więc wystarczy, że host jest na liście.

Przy okazji (decyzja wykonawcy, zapisana): pliki `new_asset` atrapy i JPEG, który `check` daje
`--media-add-cmd`, mają co najmniej 800 px szerokości — 1×1 z poziomu 1 dostałby `too_small`.

## 6. Do wykonawcy (decyzje techniczne, nie ownera)

- Podział `mock/` na moduły (np. `state.py` + `media.py` dla poziomu 4) i nazwy flag łamiących.
- Dokładne kształty JSON tras `/_tdkit/*` (opisane w README).
- Czas „wygaśnięcia” `file_url` w atrapie (w produkcji 24 h; w atrapie odnawiany przy każdym
  odczycie, jak w przewodniku).
- Jednorazowy pomiar ręczny przed wydaniem (zalecany, nie warunek): wtyczka WP 2.2.3 przeciw
  atrapie za lokalnym proxy `https`, cykl odczyt/link/edycja — różnice zapisać jako zgłoszenia.
