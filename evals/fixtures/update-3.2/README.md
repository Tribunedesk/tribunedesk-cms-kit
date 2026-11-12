# Blog

A small Django 5.2 blog on SQLite. Posts are written in the Django admin.

- Python environment: `.venv` (Django, requests and Pillow are installed).
- Run: `.venv\Scripts\python manage.py runserver`
- Tests: `.venv\Scripts\python manage.py test`

## Tribune Desk

Articles sent with "Send to CMS" arrive at `/td/webhook/` as drafts; when such a post is
published, its address is reported back to Tribune Desk (levels 1 and 2 of the CMS API,
see `tribunedesk.json`). Configuration comes from environment variables listed in
`.env.example`: `SITE_URL`, `TD_WEBHOOK_SECRET`, `TD_API_BASE`.

- Retry queued link backs from cron: `.venv\Scripts\python manage.py td_send_links`
- Developer commands for `tdkit check`: `td_inspect <article_id>`, `td_publish <article_id>`
