# extend-photos

Extend mode (audit 2026-11-27: "add photos" fell into check mode). The Django blog with a photo
library already has a level 1+2 webhook integration on the current contract (the kit's Django
reference) and a manifest; the user asks to add photos. The skill adds level 4 on top, reuses
what is built and checks all levels together.

## Prompt

Dodaj zdjęcia do naszej integracji z Tribune Desk: chcemy, żeby nasza biblioteka zdjęć (aplikacja `library`) była zsynchronizowana z biblioteką mediów Tribune Desk. Plan zatwierdzam z góry: nie czekaj na moją zgodę, ale wypisz plan i podsumowuj każdy etap. Wiadomość do naszego opiekuna w Tribune Desk zapisz też w pliku `tribunedesk-request.md` w katalogu projektu.

## Review

Judged by reading the run (the runner prints the files and the final message).

### conduct (the whole session)

PASS if all of these hold in the session:
- plan before code (SKILL.md, "The plan before code"): before its first edit of integration
  code the assistant sent a reply headed `## Plan` with the files to add and change, and did
  not stop to wait for approval (the runner checks this: "plan before code");
- the final message carries the plan as built (files added and changed, per level) and a table
  of the stages with the result of each; short progress lines between stages are enough;
- it wrote to the user in Polish;
- it said it is extending an existing integration, named what is already built (levels 1 and 2,
  webhook) and did not rebuild it (no second webhook route, token setting or link back).
FAIL if any of them is missing, or if it treated the request as a check and changed nothing.

### final-summary (the final message)

PASS if the final message, in Polish, says level 4 was added, that `tdkit check` passed for
levels 1, 2 and 4 together, and gives only the launch steps the addition brings (the sync
schedule, the operator's screen for held batches and the resync preview, a test organization
for staging), not the webhook steps again.
FAIL if it claims levels that were not built (3), or misses the check of the old levels.

### request-list (file tribunedesk-request.md)

PASS if the message asks only for what level 4 adds: the `media:read` and `media:write` scopes
on the token (and a test organization for staging, if it mentions staging).
FAIL if it asks again for a signing secret or the webhook address, or contains a secret or
token value.
