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
| `blog/management/commands/` | `td_inspect`, `td_publish` (for `tdkit check`), `td_send_links` (cron) |
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
tdkit check --levels 1,2 --mode webhook --contract v3.4.1-draft --webhook http://127.0.0.1:8000/td/webhook/ \
  --inspect-cmd ".venv/bin/python manage.py td_inspect {article_id}" \
  --publish-cmd ".venv/bin/python manage.py td_publish {article_id}"
```

The secret and the token above are the mock's public test values (kit README, "The mock").

## Changed by the reviewer

- `SECRET_KEY` reads `DJANGO_SECRET_KEY` instead of the generated development key, so the
  repository carries no key.
- Added `requirements.txt` (the run used a prepared virtual environment).
- Left out the run's `tribunedesk-request.md` (a message for one organization's contact).
