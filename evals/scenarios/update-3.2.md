# update-3.2

Update an L1+L2 Django integration built for contract 3.2.0-draft to 3.4.1-draft.

## Prompt

Zaktualizuj naszą integrację z Tribune Desk do najnowszej wersji kontraktu. Zmiany zatwierdzam z góry, ale najpierw wypisz listę zmian z rekomendacją i zapisz ją też w pliku `tribunedesk-update.md`.

## Review

Judged by reading the run (the runner prints the files and the final message).

### change-list (file tribunedesk-update.md)

PASS if the list covers the level 1 and level 2 changes of contracts 3.3.0-draft and 3.4.0-draft:
verifying the signature (no `X-Webhook-Secret` any more), moving the link back from
`/v2/cms/published-urls` to `/v3/cms/articles/published`, sending `social_queue_exclude` where
the CMS has such a setting, answering `401` to an unsigned delivery, skipping a delivery older
than the last applied `sent_at`, and treating `forbidden` like `not_found`; and it gives a
recommendation (what to do and in which order).
FAIL if it lists level 3, level 4 or read mode items as work for this integration, or has no
recommendation.
