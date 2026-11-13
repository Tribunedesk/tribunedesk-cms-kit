# parity-django

Clean-room parity (spec 2026-11-13 kontrakt najpierw, D4): everything the official WordPress
plugin does, built from scratch in a Django blog with a photo library, from the skill and the
public documentation alone. Levels 1-4, webhook; `tdkit check` green for all four.

## Prompt

Zbuduj nam integrację z Tribune Desk w takim zakresie, jak oficjalna wtyczka WordPress: artykuły trafiają do CMS-a jako szkice, po publikacji Tribune Desk dostaje link zwrotny, pełna treść (linki wewnętrzne, „czytaj więcej”, SEO, autor, oznaczenie AI) i synchronizacja naszej biblioteki zdjęć (aplikacja `library`) z biblioteką mediów Tribune Desk. Blog działa publicznie przez https pod https://blog.example.com, więc webhook jest dla nas OK. Plan zatwierdzam z góry: nie czekaj na moją zgodę, ale wypisz plan i podsumowuj każdy etap. Wiadomość do naszego opiekuna w Tribune Desk zapisz też w pliku `tribunedesk-request.md` w katalogu projektu.

## Review

Judged by reading the run (the runner prints the files and the final message).

### conduct (the whole session)

PASS if all of these hold in the session:
- before writing integration code the assistant printed a plan (files to add or change) and did
  not stop to wait for approval;
- it ended stages with short summaries (what was done, the result, what is next);
- it wrote to the user in Polish;
- when it stated a rule of the Tribune Desk contract it named the documentation file it took it
  from (for example `guide/3-full-content.md`).
FAIL if any of them is missing, or if it read the WordPress plugin's code instead of the guide.

### final-summary (the final message)

PASS if the final message, in Polish, sums up levels 1-4 in webhook mode, says `tdkit check`
passed for each level, and gives launch steps (secret and token in the production environment,
the webhook address for Tribune Desk, the schedule of the media sync).
FAIL if a level is claimed without its `tdkit check` result.

### request-list (file tribunedesk-request.md)

PASS if the message asks for a signing secret, the webhook address set for the organization and
a token with `articles:write`, `media:read` and `media:write` (it may ask for more read scopes).
FAIL if one of them is missing or it contains a secret or token value.
