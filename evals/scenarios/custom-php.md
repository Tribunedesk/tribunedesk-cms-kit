# custom-php

The promise to a publisher's developer (audit 2026-11-27): a hand-written PHP site, no framework,
no Composer, no queue, no cron, no HTML filter; the developer only says "build a Tribune Desk
plugin". Levels 1-4, webhook, from the skill's general case (`references/cms/generic.md`) and the
public documentation alone. `tdkit check` green for all four.

## Prompt

Zbuduj wtyczkę do Tribune Desk dla naszej strony, w takim zakresie jak oficjalna wtyczka WordPress: artykuły trafiają do nas jako szkice, po publikacji Tribune Desk dostaje link zwrotny, pełna treść (linki wewnętrzne, „czytaj więcej”, SEO, autor, oznaczenie AI) i synchronizacja naszej biblioteki zdjęć z biblioteką mediów Tribune Desk. Strona działa publicznie przez https pod https://gazeta.example.com, więc webhook jest dla nas OK. Plan zatwierdzam z góry: nie czekaj na moją zgodę, ale wypisz plan i podsumowuj każdy etap. Wiadomość do naszego opiekuna w Tribune Desk zapisz też w pliku `tribunedesk-request.md` w katalogu projektu.

## Review

Judged by reading the run (the runner prints the files and the final message).

### conduct (the whole session)

PASS if all of these hold in the session:
- plan before code (SKILL.md, "The plan before code"): before its first edit of integration
  code the assistant wrote the plan (files to add and change) as a progress line, and did
  not stop to wait for approval;
- the final message carries the plan as built (files added and changed, per level) and a table
  of the stages with the result of each; short progress lines between stages are enough;
- it wrote to the user in Polish;
- it told the user this is the general case for an unlisted CMS;
- when it stated a rule of the Tribune Desk contract it named the documentation file it took it
  from (for example `guide/1-article-delivery.md`).
FAIL if any of them is missing, or if it read the WordPress plugin's code instead of the guide.

### plain-php (the code)

PASS if all of these hold:
- the protocol comes from `tribunedesk/cms-protocol` loaded without Composer (a copied `src/`
  and an autoloader), or Composer was added only after the assistant said so and why;
- the webhook reads `php://input` and verifies before `json_decode`;
- the upsert is in a transaction with a lock (`BEGIN IMMEDIATE` on SQLite, or equivalent);
- the body goes through a sanitizer with an allow-list (not a regular expression or
  `strip_tags`), and the project has a test that `onerror` and `javascript:` do not survive;
- link back retries, scheduled posts, the daily taxonomy run (if the site has categories or
  tags) and the media sync run from one CLI entry point called by cron, never on page views;
- `l1-overlapping-attempts` was not passed on a single `php -S` without saying so.
FAIL if any of them is missing.

### final-summary (the final message)

PASS if the final message, in Polish, sums up levels 1-4 in webhook mode, says `tdkit check`
passed for each level, and gives launch steps that include the cron line (or Task Scheduler) for
the jobs, the secret and the token in the production environment and the webhook address.
FAIL if a level is claimed without its `tdkit check` result or the launch steps omit the schedule.

### request-list (file tribunedesk-request.md)

PASS if the message asks for a signing secret, the webhook address set for the organization and
a token with `articles:write`, `media:read` and `media:write` (it may ask for more read scopes).
FAIL if one of them is missing or it contains a secret or token value.
