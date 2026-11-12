# no-public-endpoint

Django blog behind a firewall: the skill must choose read mode.

## Prompt

Chcę, żeby artykuły z Tribune Desk trafiały do naszego CMS-a. Plan zatwierdzam z góry: nie czekaj na moją zgodę, ale wypisz plan i podsumowuj każdy etap. Wiadomość do naszego opiekuna w Tribune Desk zapisz też w pliku `tribunedesk-request.md` w katalogu projektu.

## Review

Judged by reading the run (the runner prints the files and the final message).

### read-mode-explained (the final message)

PASS if the final message, in Polish, says the site cannot receive requests from the internet so
the integration polls Tribune Desk (read mode), says the conformance test passed in read mode,
and its launch steps include scheduling the poll and do not ask for a webhook address.
FAIL if it builds or recommends a webhook, or omits how the poll is run in production.

### request-list (file tribunedesk-request.md)

PASS if the message asks Tribune Desk to switch on read mode for the organization, to enable the
integration, and for a token with `articles:read` and `articles:write`.
FAIL if it asks for a signing secret or a webhook address, or contains a token value.
