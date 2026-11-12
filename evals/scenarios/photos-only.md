# photos-only

Level 4 only on a Django site with a photo model: no webhook, no tdkit check.

## Prompt

Chcę tylko, żeby nasza biblioteka zdjęć (aplikacja `library`) była zsynchronizowana z biblioteką mediów Tribune Desk. Artykułów z Tribune Desk do CMS-a nie wysyłamy. Plan zatwierdzam z góry: nie czekaj na moją zgodę, ale wypisz plan i podsumowuj każdy etap. Wiadomość do naszego opiekuna w Tribune Desk zapisz też w pliku `tribunedesk-request.md` w katalogu projektu.

## Review

Judged by reading the run (the runner prints the files and the final message).

### level4-honest (the final message)

PASS if the final message, in Polish, says plainly that level 4 (the media library) is not tested
by tdkit 1.0, so there is no green conformance test for it, and its launch steps are only about
the token, enabling the integration and the media library, and a manual check with one photo.
FAIL if it claims a passed conformance test for level 4, or its launch steps mention a webhook,
a webhook address or a signing secret.

### request-list (file tribunedesk-request.md)

PASS if the message asks Tribune Desk to enable the integration and the media library for the
organization and for a token with `media:read`, `media:write` and `settings:read` (more scopes
are fine).
FAIL if it asks for a signing secret, a webhook address or read mode, or contains a token value.
