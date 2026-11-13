# Kontrakt najpierw: jak zmiany wtyczki i API same docierają do kontraktu, `cms-php`, `tdkit` i skilla — projekt

Data: 2026-11-13. Status: **zatwierdzony przez ownera 13.11 (wariant 1: w całości).** Repozytoria: `Tribunedesk/tribunedesk-cms-kit`
(ten), `Tribunedesk/tribunedesk-cms-api`, `Tribunedesk/tribunedesk-cms-php`,
`Tribunedesk/tribunedesk-wordpress`, headlinesforge (`docs/api/cms/`,
`.github/workflows/cms-api-docs.yml`). Kontekst: spec E9 (headlinesforge
`docs/specs/2026-11-08-e9-skill-integracji-tribune-desk-design.md`), Rollout kitu w vault
`projects/tribunedesk-cms-kit/wiki.md`.

## 1. Po co

Owner będzie dużo rozwijał wtyczkę WordPress. Cel: **najnowszą wersję wtyczki zawsze da się
odtworzyć w innym CMS-ie samym skillem `tribunedesk-integration`.** Dziś to zależy od pamięci
sesji: nic między repozytoriami nie jest zautomatyzowane, a każda przypinka wersji dowodzi tylko
zgodności z tagiem, który sama nazywa.

**Sukces:** zmiana wtyczki albo API, która dotyczy integratorów, nie może dojść do `main`/`master`
ani do tagu kontraktu tak, żeby kit, `cms-php`, wtyczka i skill zostały po cichu zielone na starej
wersji. Każde opóźnienie widać jako czerwony check albo otwarty PR, nie jako brak sygnału.

**Anty-cel:** automat, który maluje zielono coś, czego nikt nie sprawdził — np. test pokrycia
spełniany przez dopasowanie tekstu „na oko” albo PR podbijający przypinkę, który scala się sam.
Fałszywa zieleń jest gorsza od dzisiejszej ciszy, bo uspokaja.

**Nie-cele:** wykonanie trzech zadań z ledgera z 13.11 (sekcja 7 mówi, co je zastąpi); zmiana
zasady, że PR synchronizacji dokumentacji scala człowiek (decyzja ownera 3 ze specu otwartego API
z 03.11); deploy czegokolwiek; poziom 5.

## 2. Stan 13.11 (sprawdzony w repozytoriach, nie z pamięci)

| Miejsce | Przypinka / mechanizm | Stan |
|---|---|---|
| headlinesforge `cms-api-docs.yml` | push `master` w `docs/api/**` → PR `sync/latest` w `tribunedesk-cms-api` | bez `CMS_API_DOCS_TOKEN` kończy się **na zielono** z `::notice` |
| headlinesforge `tests/backend/test_cms_v3_contract.py` | `docs/api/cms-v3.openapi.json` == `build_openapi()` | łapie zmianę kształtu API bez dokumentacji; nie łapie zmiany zachowania |
| `tribunedesk-cms-api` | tagi lekkie `v3.2.0-draft` … `v3.4.2-draft`, stawiane ręcznie | brak katalogu `.github/workflows` |
| kit `.github/workflows/ci.yml` | `CONTRACT_TAG: v3.4.1-draft` (job `examples`), `--contract v3.4.1-draft` wpisane dwa razy (reference-django, reference-drupal) | fixture `tests/fixtures/cms-api` jest już 3.4.2, CI dalej 3.4.1 |
| kit `src/tdkit/docs.py` | `SUPPORTED_MINOR = (3, 4)` — **jeden** minor | strażnika „kit przed dokumentacją” nikt nie wymusza; Rollout w wiki to tylko zasada |
| kit `tests/test_check.py:240`, `tests/test_check_media.py:165` | każdy `done_when` scenariusza jest dosłownym cytatem przewodnika | kierunek odwrotny (punkt przewodnika → scenariusz) nie jest sprawdzany |
| `cms-php` `tests/fixtures/contract/VERSION` | `v3.4.1-draft`, CI porównuje wektory podpisu z tym tagiem | zielone na 3.4.1 |
| wtyczka `tribunedesk.json` | `"contract": "3.4.1-draft"`, `"protocol": "1.0.0"`; CI porównuje `openapi.json` i przykładowy payload z tagiem oraz `src/Protocol` z tagiem `cms-php` | zielone na 3.4.1; wtyczka **nie** przechodzi `tdkit check` nigdzie |
| skill | czyta przewodnik na żywo (`TDKIT docs` = najnowszy tag), zmiany dla integratorów przez `TDKIT integrators` | dobra podstawa: treść przewodnika dociera do skilla bez wydania kitu |

Przewodnik już opisuje część zachowań „wordpressowych”: autor (`guide/3-full-content.md`,
„SEO, author and language”), pola SEO, „read more” (`backlink_sources`), `social_queue_exclude`.
Nie opisuje m.in. filtra embedów ani limitów kolejek wtyczki.

## 3. Pomysł: łańcuch dowodu

Zdanie „wtyczkę da się odtworzyć skillem” rozkłada się na ogniwa; każde dostaje automat, który
czerwieni CI, gdy ogniwo pęka:

1. **Wtyczka ⊆ przewodnik** — każda funkcja wtyczki ma miejsce w przewodniku albo jawny wpis
   „tylko WordPress” (D1, mapa funkcji).
2. **Przewodnik ⊆ `tdkit`** — każdy punkt „Done when” ma scenariusz albo jawne wyłączenie (D3).
3. **CHANGELOG `Integrators` ⊆ skill/`tdkit`** — każda pozycja ma potwierdzoną obsługę (D3).
4. **Wtyczka przechodzi `tdkit check`** — ten sam test co każdy inny CMS (D2e).
5. **`tdkit` zna kontrakt, zanim kontrakt dostanie tag** (D2c).
6. **Każdy konsument śledzi najnowszy tag**, a nie tylko „swój” (D2b).
7. **Dowód końcowy:** agent z samym skillem i publicznymi źródłami buduje w innych CMS-ach to,
   co ma wtyczka (D4).

Ogniwa 1–3 to dane w repozytoriach sprawdzane testem; 4–6 to CI; 7 to rytuał przy wydaniu.

## 4. Decyzje

### D1. Kontrakt najpierw; zachowania wtyczki trafiają do przewodnika

Każda zmiana wtyczki należy do jednej z trzech klas:

- **(a) Kontrakt** — zmienia to, co Tribune Desk wysyła albo czego oczekuje (pole, trasa, kod,
  kolejność, czasy). Najpierw PR dokumentacji w headlinesforge (`openapi`, przewodnik, `CHANGELOG`
  z blokiem `**Integrators:**`), potem tag kontraktu, potem PR wtyczki podnoszący `contract`.
- **(b) Zachowanie, które inny CMS też powinien mieć** (rozwiązywanie autora, pola SEO, filtr
  embedów, „czytaj więcej”, limity kolejek…) — **do przewodnika**, w rozdziale poziomu, którego
  dotyczy: zdanie w treści i punkt „Done when”. Gdy CMS może nie mieć danego pojęcia, punkt ma
  formę już używaną w przewodniku: „If your CMS has …”. Taka zmiana idzie tą samą drogą co (a):
  wersja, CHANGELOG, pozycja `Integrators`.
- **(c) Idiom WordPressa** (który hook, klucze meta Yoast, WP-Cron, ekran ustawień) — nigdzie w
  kontrakcie; do `references/cms/wordpress.md` w kicie tylko wtedy, gdy przyda się komuś, kto
  buduje własną integrację WordPressa zamiast wtyczki.

**Wymuszenie po stronie wtyczki — mapa funkcji** (`docs/contract-map.json` w repo wtyczki): każda
klasa `src/WordPress/*.php` ma wpis `{"class", "guide": "<plik>#<nagłówek sekcji>"}` albo
`{"class", "wp_only": "<powód>"}`. Test PHPUnit w wtyczce: każda klasa ma wpis, każdy wpis wskazuje
istniejącą klasę, każdy `guide` wskazuje nagłówek istniejący w dokumentacji tagu z
`tribunedesk.json` (`tests/contract/` trzyma już kopię tego tagu — dochodzi kopia `guide/`). Nowa
klasa bez wpisu = czerwone CI wtyczki.

**Wymuszenie po stronie headlinesforge:** job CI na PR i push `master`: jeśli zakres zmian dotyka
`backend/api/cms_v3/**` albo `backend/services/cms_delivery_contract.py` (lista ścieżek do
uściślenia przez budowniczego), a nie dotyka `docs/api/cms/CHANGELOG.md`, job pada — chyba że
któryś commit zakresu ma trailer `Contract: none` (refaktor bez skutku dla integratorów).

- **Why:** przewodnik jest jedynym źródłem, które skill czyta na żywo, które ma wersję, wchodzi do
  `TDKIT integrators` (tryb aktualizacji) i które czyta też integrator bez Claude'a. Zachowanie
  zapisane w przewodniku dociera do skilla bez wydania kitu, a punkt „Done when” wciąga je w test
  pokrycia (D3). Mapa funkcji zamienia „pamiętaj o przewodniku” w czerwony test.
- **Odrzucone: `references/` skilla dla klasy (b).** Przegrywa, bo wiąże zachowanie z cyklem
  wydań kitu zamiast wersji kontraktu, tryb aktualizacji go nie widzi (nie ma pozycji
  `Integrators`), integrator bez Claude'a go nie zobaczy, a `tdkit` nie ma punktu do testowania —
  dryf wtyczka↔skill wróciłby bocznymi drzwiami.
- **Odrzucone: checkbox w szablonie PR wtyczki zamiast mapy.** Nic nie wymusza; to dokładnie
  „pamięć sesji”, którą owner chce usunąć.
- **Odrzucone: mapa na poziomie funkcji/hooków.** Za drobna: każda zmiana nazwy to szum w mapie;
  klasa to jednostka, w której wtyczka już jest zorganizowana.
- **Rewizja:** gdy klasa zaczyna mieszać zachowania (b) i (c) tak, że jeden wpis kłamie — przejść
  na wpisy per publiczna metoda tej klasy; gdy trailer `Contract: none` pojawia się w więcej niż
  co trzecim commicie API CMS — lista ścieżek jest za szeroka.

### D2. Automaty CI

**D2a. Kontroli i tagu pilnuje `tribunedesk-cms-api`.** Dwa workflowy w repo publicznym:

- `pr.yml` (na PR do `main`, w praktyce PR `sync/latest`): jeśli zmienił się `openapi.json`,
  `guide/**`, `examples/**` albo `CHANGELOG.md`, to `info.version` > najnowszy tag, `CHANGELOG.md`
  ma nagłówek `## <version>` z blokiem `**Integrators:**` (choćby „Nothing to do.”), a jeśli
  zbiór punktów „Done when” różni się od najnowszego tagu, podbity jest co najmniej minor
  (nowy punkt to nowe wymaganie, nie opis — patch z 3.4.2 dodał punkty i dziś nic by tego nie
  zatrzymało). Plus strażnik z D2c.
- `tag.yml` (na push `main`): wersja z `openapi.json`; jeśli tagu `v<version>` nie ma — strażnik
  D2c, potem **adnotowany** tag `v<version>` na tym SHA (`GITHUB_TOKEN`, `contents: write`).
  Gdy tag już jest, a treść się zmieniła — błąd (zmiana bez wersji nie może leżeć na `main`).

Scalanie PR-a synchronizacji zostaje ręczne; tag przestaje być ręczny.

- **Why:** tag to moment publikacji (skill bierze najnowszy tag), więc kontrole muszą stać tam,
  gdzie tag powstaje. Repo jest małe, publiczne, ma jeden typ PR-a.
- **Odrzucone: kontrole tylko w headlinesforge.** Wcześniejszy sygnał, ale headlinesforge musiałby
  sięgać po tagi innego repo w każdym CI backendu, a tag i tak powstaje w `cms-api`; zostawiam
  jedno miejsce prawdy.
- **Rewizja:** jeśli `pr.yml` w `cms-api` odrzuci synchronizację więcej niż dwa razy w miesiącu
  (poprawki wracają do headlinesforge) — przenieść kontrole wersji/CHANGELOG do CI headlinesforge.

**D2b. Konsumenci śledzą najnowszy tag: harmonogram, nie `repository_dispatch`.** W kicie,
`cms-php` i wtyczce workflow `contract-drift.yml`: `schedule` codziennie (np. 05:30 UTC) +
`workflow_dispatch`. Porównuje przypinkę z najnowszym tagiem (`git ls-remote --tags`, repo
publiczne, bez tokenu). Gdy przypinka jest w tyle:

1. buduje gałąź `contract/latest` od `main`: podnosi przypinkę i odświeża kopie z tagu
   (kit: `CONTRACT_TAG` + `tests/fixtures/cms-api`; `cms-php`: `VERSION` + wektory podpisu;
   wtyczka: `"contract"` + `tests/contract/*`), force-push;
2. otwiera albo aktualizuje jeden PR „contract: vSTARY → vNOWY” z linkiem do CHANGELOG i
   wypisanymi pozycjami `Integrators`;
3. uruchamia CI na tej gałęzi przez `gh workflow run <ci> --ref contract/latest` — PR utworzony
   `GITHUB_TOKEN`-em sam nie odpala CI, `workflow_dispatch` tak (CI kitu, `cms-php` i wtyczki
   dostają wyzwalacz `workflow_dispatch`);
4. **sam kończy się błędem**, póki przypinka jest w tyle — codzienny czerwony run to
   powiadomienie.

Wtyczka ma dwie dodatkowe przypinki tym samym mechanizmem: `"protocol"` vs najnowszy tag
`cms-php` (gałąź `protocol/latest`, kopiuje `src` biblioteki do `src/Protocol`) i `TDKIT_TAG`
vs najnowszy tag kitu (D2e). Kit przy okazji ujednolica przypinkę: `--contract` w jobach
reference czyta `$CONTRACT_TAG` zamiast wpisanego literału.

PR-y nie scalają się same: `main` ląduje tylko przez `/ship` na wyraźne słowo (zasada ownera),
a push `main` kitu to wydanie pluginu.

- **Why:** zero nowych sekretów (wszystko na `GITHUB_TOKEN` własnego repo), nowy konsument
  dokłada się bez rejestrowania w nadawcy, opóźnienie ≤ 24 h wystarcza, bo nic tu nie ma
  cyklu szybszego niż dzień. CI na PR-ze od razu pokazuje, co nowy tag psuje.
- **Odrzucone: `repository_dispatch` z `cms-api`.** Wymaga PAT-a z zapisem do trzech repo
  trzymanego w `cms-api`; gdy wygaśnie, sygnał znika po cichu — to dokładnie awaria, którą
  naprawiamy (tak działa dziś `CMS_API_DOCS_TOKEN`).
- **Odrzucone: job „przypinka == najnowszy tag” w zwykłym CI każdego PR-a.** Nowy tag
  czerwieniłby wszystkie niezwiązane PR-y aż do podbicia; harmonogram + jeden PR daje ten sam
  sygnał bez blokowania pracy.
- **Odrzucone: automatyczne scalanie zielonego PR-a podbicia.** Łamie zasadę lądowania przez
  `/ship`; w kicie byłoby wydaniem pluginu bez człowieka.
- **Rewizja:** gdy zmiana kontraktu musi dotrzeć do integratorów tego samego dnia — dołożyć
  `repository_dispatch` z `tag.yml` jako przyspieszenie (harmonogram zostaje zabezpieczeniem).

**D2c. Strażnik „kit przed dokumentacją”.** W kicie `SUPPORTED_MINOR` staje się zbiorem
`SUPPORTED_MINORS = {(3, 4), (3, 5)}`: wydanie kitu dla nowego minora musi **dalej** przyjmować
poprzedni, bo między wydaniem kitu a tagiem dokumentacji `TDKIT docs` wciąż widzi stary tag —
z jednym minorem skill przestałby działać każdemu w tym oknie. `pr.yml` i `tag.yml` w `cms-api`,
gdy `major.minor` nowej wersji jest inny niż najnowszego tagu, czytają `src/tdkit/docs.py` z
najnowszego tagu kitu (`git clone --depth 1 --branch <tag>`, wyrażenie regularne na
`SUPPORTED_MINORS`) i padają z komunikatem „najpierw wydaj tdkit znający X.Y”, jeśli go tam nie
ma. Stary minor wypada ze zbioru w kolejnym wydaniu kitu po tagu nowego.

- **Why:** reguła z Rollout w wiki zamienia się w błąd w miejscu publikacji; kit testuje nową
  dokumentację przed tagiem na `--docs` z gałęzi `main` repo `cms-api`.
- **Odrzucone: strażnik w CI kitu.** Kit nie wie, kiedy ktoś postawi tag w innym repo; pilnować
  trzeba po stronie, która publikuje.
- **Odrzucone: czytanie wersji przez `uvx … tdkit --supports`.** Dokłada nową komendę i
  instalację narzędzia w CI `cms-api` dla jednej linii, którą da się przeczytać z pliku.
- **Rewizja:** gdy kontrakt przestanie być `-draft` i dojdzie major — strażnik ma porównywać
  także major (wyrażenie już niesie obie liczby; zmienia się tylko komunikat i test).

**D2d. Brak tokenu w headlinesforge to błąd.** `cms-api-docs.yml`: brak `CMS_API_DOCS_TOKEN` →
`::error::` i `exit 1` zamiast `::notice` i zielonego przejścia. Komentarz o „leżeniu na master
przed powstaniem repo” do usunięcia — repo istnieje.

- **Why:** zielony run bez synchronizacji to najgroźniejsza dziś cisza: dokumentacja zmienia się w
  headlinesforge, a nic nie dociera do tagu.
- **Odrzucone: zostawić ostrzeżenie (`::warning`).** Nie wysyła powiadomienia o nieudanym runie;
  nikt go nie zobaczy.
- **Rewizja:** brak — chyba że synchronizacja zostanie zastąpiona innym mechanizmem.

**D2e. Wtyczka przechodzi `tdkit check` w swoim CI** (propozycja moja, nie było jej w zadaniu —
bez niej ogniwo 4 łańcucha nie istnieje). Job w `plugin-ci.yml`: wp-env z wtyczką, `tdkit` z tagu
`TDKIT_TAG` (`uvx --from git+…@<tag> tdkit`), `tdkit check --levels 1,2,3,4 --mode webhook
--contract v<contract z tribunedesk.json>` z `--inspect-cmd "wp td inspect {article_id}"` i
`--publish-cmd "wp td publish {article_id}"`. Wtyczka nie rejestruje dziś żadnej komendy WP-CLI
(`WP_CLI::add_command` nie występuje w `origin/main` 13.11), więc budowniczy je dodaje —
`references/cms/wordpress.md` sekcja 7 opisuje te same komendy dla własnej integracji.

- **Why:** wtyczka staje się implementacją referencyjną sprawdzaną tym samym testem co Django i
  Drupal w kicie; z D1 i D3 daje to: funkcja wtyczki → punkt przewodnika → scenariusz → zielony
  test w wtyczce i w każdym innym CMS-ie.
- **Odrzucone: wtyczka jako kolejny job reference w kicie.** CI kitu musiałoby budować WordPressa
  przy każdej zmianie `src/tdkit/`, a wtyczka nie dowiedziałaby się o własnej regresji przed
  wydaniem (push `main` wtyczki = wydanie).
- **Rewizja:** gdy job przekroczy ~10 min albo będzie niestabilny — puszczać go tylko na PR-ach
  dotykających `src/` i na `contract/latest`.

### D3. Test pokrycia w kicie

Nowy plik danych `src/tdkit/check/coverage.toml` i test `tests/test_coverage.py`, oba na
`tests/fixtures/cms-api` (fixture to kopia tagu `CONTRACT_TAG`; test pilnuje, że wersje są równe,
a PR z D2b odświeża oba naraz):

- **„Done when” → scenariusz.** Parser zbiera wypunktowania sekcji `## Done when` każdego
  `guide/*.md` (razem z listą „In read mode, also:”). Każdy punkt musi być dosłownie równy
  `done_when` jakiegoś scenariusza **albo** mieć wpis `[[exempt]]` z `point` (dosłowny tekst) i
  `reason` (np. „ekran redaktora, niewidoczny przez API”). Wpis `exempt`, który nie pasuje do
  żadnego punktu, też czerwieni (nieaktualne wyłączenie).
- **`Integrators` → obsługa.** Każda pozycja bloków `**Integrators:**` (parser z
  `src/tdkit/integrators.py`), klucz `version` + dosłowny tekst, ma wpis `[[integrators]]` z
  `handled_by` — listą `scenario:<id>` (scenariusz istnieje), `skill:<ścieżka>` (plik w
  `plugins/tribunedesk-integration/skills/tribunedesk-integration/` istnieje) albo `none` z
  `reason`. „Nothing to do.” nie wymaga wpisu. Nieznany tag poziomu (przyszły `L5`) czerwieni.

Nowy punkt w nowym tagu → PR `contract/latest` w kicie jest czerwony, dopóki ktoś nie dopisze
scenariusza albo wpisu.

- **Why:** test w kierunku „scenariusz → przewodnik” już jest (cytaty dosłowne); brakuje
  odwrotnego, i to on mówi, czy zielony raport `tdkit` znaczy „Done when”. Dane w kicie, bo
  identyfikatory scenariuszy i pliki skilla to sprawa kitu, nie publicznej dokumentacji.
  Skill czyta `Integrators` na żywo, więc „odzwierciedlenie w skillu” znaczy: ktoś potwierdził,
  który scenariusz albo plik skilla to obsługuje, albo że nie ma czego.
- **Odrzucone: dopasowanie przybliżone (podobieństwo tekstu) zamiast wpisów.** Zielone bez
  człowieka — anty-cel.
- **Odrzucone: wymóg scenariusza dla każdej pozycji `Integrators`.** Część pozycji nie da się
  sprawdzić ogólnie („send it when your CMS has such a setting”); wymuszałoby to scenariusze-atrapy.
- **Odrzucone: oznaczenia w samym przewodniku (np. id scenariusza przy punkcie).** Zaśmieca tekst
  dla integratorów nazwami z narzędzia, którego mogą nie używać.
- **Rewizja:** gdy `exempt` przekroczy ~20% punktów „Done when” — przegląd, czy `tdkit` nie
  omija za dużo.

### D4. Rytuał wydania: eval clean-room na trzech CMS-ach

Po każdym wydaniu minora kitu (1.2, 1.3, …; każdy nowy minor kontraktu i każda nowa funkcja z
klasy (b) przechodzi przez minor kitu przez D2c/D3) trzy nowe scenariusze evalu `parity-<cms>`:
zbuduj od zera w danym CMS-ie wszystko, co ma wtyczka (poziomy 1–4, webhook, punkty „If your CMS
has …” tam, gdzie CMS ma pojęcie). CMS-y: **Django** (Python), **Laravel** (PHP przez `cms-php`),
**Node/Express** (JavaScript).

**Clean-room** znaczy: agent ma tylko plugin z gałęzi wydania (`--plugin-dir`, ta sama treść, którą
`main` opublikuje), `tdkit` z kandydata wydania, dokumentację tylko z GitHuba (`TDKIT docs`),
żadnego dostępu do lokalnych repo wtyczki, kitu ani headlinesforge (projekt w katalogu
tymczasowym, `--setting-sources local` jak dziś w `evals/run.py`). Ocena: `tdkit check` zielony
dla wszystkich poziomów + przegląd jak w obecnych scenariuszach.

Wynik w tabeli „Evals” w README (data, wersja kitu, tag kontraktu, wynik `tdkit`, przegląd,
koszt). Test `tests/test_project.py`: tabela ma wiersze `parity-*` z wersją kitu o tym samym
`major.minor` co `tdkit.__version__` — PR wydania minora nie jest zielony bez evalu.

- **Why:** to jedyny dowód celu ownera wprost, a nie przez ogniwa. Trzy różne języki pokazują, że
  skill nie przemyca idiomu jednego CMS-a. Szacunek z obecnych runów: 1,6–3,6 USD na scenariusz,
  ok. 10 USD na wydanie minora.
- **Odrzucone: eval w CI.** Klucz API w CI publicznego repo, koszt przy każdym pushu, niestabilny
  wynik czerwieniący niezwiązane zmiany.
- **Odrzucone: eval przy każdym patchu.** Patche zmieniają opisy; koszt bez nowej informacji.
- **Odrzucone: Drupal i Ghost jako CMS-y parytetu.** Drupal ma już job reference w CI kitu i
  buduje się ~7 min; Ghost nie ma kodu po stronie integratora.
- **Rewizja:** gdy ten sam scenariusz parytetu padnie dwa wydania z rzędu z tego samego powodu,
  albo koszt rundy przekroczy 20 USD.

## 5. Przepływ jednej zmiany (przykład: wtyczka zaczyna filtrować embedy)

1. Klasa (b). PR w headlinesforge: zdanie w `guide/3-full-content.md` + punkt „Done when”,
   wersja 3.5.0-draft, CHANGELOG z pozycją `` `L3`: … ``. CI headlinesforge zielone.
2. Kit: scenariusz albo wpis `exempt`, wpis `[[integrators]]`, `SUPPORTED_MINORS` z (3, 5),
   testy na `--docs` z `main` `cms-api` po scaleniu synchronizacji; wydanie kitu 1.x (tag, `/ship`).
   Rytuał D4.
3. `cms-api`: PR `sync/latest` → `pr.yml` sprawdza wersję, CHANGELOG, minor za nowy punkt, kit
   zna 3.5 → człowiek scala → `tag.yml` stawia `v3.5.0-draft`.
4. Następnego dnia `contract-drift.yml` w `cms-php` i wtyczce otwiera PR-y podbicia; CI wtyczki
   uruchamia `tdkit check` z nowym scenariuszem.
5. PR wtyczki z samą funkcją: klasa w `docs/contract-map.json` wskazuje
   `guide/3-full-content.md#…`; bez wpisu CI czerwone.

Klasa (a) idzie tak samo. Klasa (c): tylko wpis `wp_only` w mapie wtyczki.

## 6. Sekrety i uprawnienia

Żadnego nowego sekretu. `cms-api`: `GITHUB_TOKEN` z `contents: write` (tag). Konsumenci:
`GITHUB_TOKEN` z `contents: write`, `pull-requests: write`, `actions: write` (dispatch CI).
Headlinesforge: istniejący `CMS_API_DOCS_TOKEN` (teraz wymagany).

## 7. Co z zadaniami ledgera z 13.11

- `2026-11-13-tribunedesk-wordpress-kontrakt-3-4-2` — zastępuje `contract-drift.yml` wtyczki
  (pierwszy run otworzy PR 3.4.1 → 3.4.2); zadanie można zamknąć po scaleniu tego PR-a.
- `2026-11-13-tribunedesk-wordpress-cms-php-kontrakt-3-4-2` — zastępuje drift `cms-php`
  (`VERSION`) i drift `"protocol"` wtyczki (po tagu `cms-php` 1.1.0).
- `2026-11-13-tribunedesk-cms-php-pogodzenie-z-przewodnikiem` — **nie** zastępuje: to jednorazowa
  poprawka treści (PR `Tribunedesk/tribunedesk-cms-php#2` czeka na tag). Przyszłe rozjazdy
  biblioteki z przewodnikiem złapie częściowo job `reference-drupal` kitu (biblioteka, poziomy
  1–2) i D2e (wtyczka używa kopii biblioteki, poziomy 1–4).
- Kit sam ma ten sam dryf (CI na 3.4.1, fixture 3.4.2): pierwszy run driftu kitu go naprawi.

## 8. Dla budowniczego

**Kolejność wdrożenia** (osobny PR na repo; każdy etap kończy się zatrzymaniem i weryfikacją):

1. **Kit:** `SUPPORTED_MINORS` (zbiór), `CONTRACT_TAG` jedną zmienną, `coverage.toml` +
   `tests/test_coverage.py` (z wpisami dla dzisiejszego 3.4.2), `workflow_dispatch` w `ci.yml`,
   `contract-drift.yml`, test tabeli evalów, scenariusze `parity-*` w `evals/`. Wydanie kitu
   minorem (1.2.0), pierwsza runda D4.
2. **headlinesforge:** D2d (token) i strażnik ścieżek API → CHANGELOG (D1).
3. **`cms-api`:** `pr.yml`, `tag.yml` ze strażnikiem D2c (czyta format z etapu 1, więc po nim).
4. **`cms-php`:** `workflow_dispatch` w CI, `contract-drift.yml`.
5. **Wtyczka:** `contract-drift.yml` (kontrakt, `protocol`, `TDKIT_TAG`), `docs/contract-map.json`
   + test, kopia `guide/` w `tests/contract/`, job `tdkit check` z nowymi komendami WP-CLI `wp td inspect|publish`.
6. **Przewodnik:** zachowania klasy (b), których brakuje (filtr embedów, limity kolejek —
   inwentaryzacja z mapy wtyczki), jako 3.5.0-draft przez pełny przepływ z sekcji 5 — pierwsza
   prawdziwa próba całego łańcucha.

**Zostawione budowniczemu:** dokładna lista ścieżek strażnika headlinesforge; format parsera
„Done when” (dziś wypunktowania `- ` po nagłówku i po linii „In read mode, also:”); godzina
harmonogramu; nazwy plików workflowów; czy mapa wtyczki to JSON czy tabela Markdown parsowana
testem (zalecam JSON — test PHP czyta go bez parsera Markdown).

**Moje decyzje do sprawdzenia przy czytaniu:** D2e (wtyczka w `tdkit check`) i strażnik ścieżek w
headlinesforge — oba spoza listy zadania; nowy punkt „Done when” wymusza minor (D2a); zbiór
`SUPPORTED_MINORS` zamiast jednego minora (D2c); wybór Django/Laravel/Node do D4.
