# photos-only

Level 4 only on a Django site with a photo model: no webhook, a green `tdkit check --levels 4`.

## Prompt

Chcę tylko, żeby nasza biblioteka zdjęć (aplikacja `library`) była zsynchronizowana z biblioteką mediów Tribune Desk. Artykułów z Tribune Desk do CMS-a nie wysyłamy. Plan zatwierdzam z góry: nie czekaj na moją zgodę, ale wypisz plan i podsumowuj każdy etap. Wiadomość do naszego opiekuna w Tribune Desk zapisz też w pliku `tribunedesk-request.md` w katalogu projektu.

## Review

Judged by reading the run (the runner prints the files and the final message).

### level4-tested (the final message)

PASS if the final message, in Polish, says that the conformance test of level 4 (tdkit check
--levels 4) passed, names what was built (the core; the options only if the user asked), and its
launch steps are about the token, enabling the integration, a separate test organization for
staging, scheduling the sync, the operator's screen for held batches and the resync preview, and
a manual check with one photo.
FAIL if it says level 4 has no conformance test, claims a pass the report does not show, or its
launch steps mention a webhook, a webhook address or a signing secret.

### request-list (file tribunedesk-request.md)

PASS if the message asks Tribune Desk to enable the integration and the media library for the
organization and for a token with `media:read`, `media:write` and `settings:read` (more scopes
are fine), and for a separate test organization for staging.
FAIL if it asks for a signing secret, a webhook address or read mode, or contains a token value.
