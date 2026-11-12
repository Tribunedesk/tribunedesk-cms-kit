# django-l12

Build levels 1+2 (webhook) into a Django blog; the user answers and approves up front.

## Prompt

Zbuduj mi integrację naszego bloga z Tribune Desk: artykuły mają trafiać do CMS-a, a po publikacji Tribune Desk ma dostać link zwrotny. Blog działa publicznie przez https pod https://blog.example.com, więc webhook jest dla nas OK. Zdjęć i pełnej treści nie potrzebujemy. Plan zatwierdzam z góry: nie czekaj na moją zgodę, ale wypisz plan i podsumowuj każdy etap. Wiadomość do naszego opiekuna w Tribune Desk zapisz też w pliku `tribunedesk-request.md` w katalogu projektu.

## Review

Judged by reading the run (the runner prints the files and the final message).

### conduct (the whole session)

PASS if all of these hold in the session:
- before writing integration code the assistant printed a plan (files to add or change), even
  though the user approved it in advance, and did not stop to wait for approval;
- it ended stages with short summaries (what was done, the result, what is next);
- it wrote to the user in Polish;
- when it stated a rule of the Tribune Desk contract it named the documentation file it took it
  from (for example `guide/1-article-delivery.md`).
FAIL if any of them is missing, or if the assistant asked the user to approve the plan and
stopped there.

### final-summary (the final message)

PASS if the final message, in Polish, sums up the build of levels 1 and 2 in webhook mode, says
the conformance test (tdkit check) passed, and gives launch steps that include putting the
signing secret and the token into the production environment and giving Tribune Desk the
webhook address.
FAIL if it claims levels that were not built (3 or 4), gives read mode or photo library steps,
or does not say whether the conformance test passed.

### request-list (file tribunedesk-request.md)

PASS if the message asks Tribune Desk for: a signing secret for webhooks, the webhook address
(https://blog.example.com/...) set for the organization, and a token with the `articles:write`
scope (it may also ask for `articles:read` or the list of image hosts, for downloading images).
FAIL if it is missing one of those three, if it asks for read mode, for media library scopes
(`media:read`, `media:write`) or for the "read more" box, or if it contains a secret or token
value.
