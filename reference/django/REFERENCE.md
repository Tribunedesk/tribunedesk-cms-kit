# Django reference integration (levels 1 + 2, webhook)

**Reference to read, not a supported module.** Built by the skill `tribunedesk-integration` in the
`django-l12` run (2026-11-12) on a small Django 5.2 blog; the project's own `README.md` is the
one the skill extended.

## What to read

| File | What it does |
|---|---|
| `blog/tribunedesk.py` | signature check (Standard Webhooks), the upsert keyed by `article_id` with a row lock, order of sends, link back with retries |
| `blog/views.py` | the webhook route: raw body, 401 on a bad signature, the answer |
| `blog/signals.py` | link back when a post made from an article is published |
| `blog/management/commands/` | `td_inspect`, `td_publish` (for `tdkit check`), `td_send_links` and `td_publish_due` (cron: scheduled posts whose time has come) |
| `blog/tests.py` | the project's own tests, including the contract's signature vectors |
| `blogsite/settings.py` (end) | values from the environment only; SQLite `IMMEDIATE` transactions |
| `tribunedesk.json` | the manifest written from the `tdkit check` report |

## Run it and check it

```
python -m venv .venv
.venv/bin/pip install -r requirements.txt        # Windows: .venv\Scripts\pip
.venv/bin/python manage.py migrate
TD_WEBHOOK_SECRET=whsec_dGRraXQtbW9jay1zaWduaW5nLXNlY3JldC0wMDAwMDA= \
TD_API_BASE=http://127.0.0.1:8787 TD_CMS_TOKEN=tdcms_mock \
  .venv/bin/python manage.py runserver 127.0.0.1:8000 --noreload &
tdkit check --levels 1,2 --mode webhook --contract v3.9.0-draft --webhook http://127.0.0.1:8000/td/webhook/ \
  --inspect-cmd ".venv/bin/python manage.py td_inspect {article_id}" \
  --publish-cmd ".venv/bin/python manage.py td_publish {article_id}"
```

`tdkit` is the kit's command line tool:
`uvx --from git+https://github.com/Tribunedesk/tribunedesk-cms-kit@v1.8.1 tdkit` (kit README,
"Run it"). The secret and the token above are the mock's public test values (kit README,
`tdkit mock`).

Last checked 2026-11-27: tdkit 1.8.0, contract 3.9.0-draft, 15 passed, 0 failed (`tribunedesk.json`
records it). CI runs the same check on every pull request that touches the kit (job
`reference-django`), on the contract of `ci/contract-tag`.

## Changed by the reviewer

- `SECRET_KEY` reads `DJANGO_SECRET_KEY` instead of the generated development key, so the
  repository carries no key.
- Added `requirements.txt` (the run used a prepared virtual environment).
- Left out the run's `tribunedesk-request.md` (a message for one organization's contact).
- 2026-11-17: the embed filter of guide 1 (contract 3.5); 2026-11-25: the publication mode and
  `td_publish_due` (contract 3.7).
- 2026-11-27: the site address is read from the environment variable `TD_SITE_URL`, the kit's
  name in every CMS reference (the run had used a name without the prefix); the body filter is an
  allow list on a parser (`nh3`), as `guide/complete-integration.md` asks since 3.9 (the regular
  expressions before let `onerror` and `javascript:` through); the manifest was rewritten from a check on contract 3.9.0-draft.
