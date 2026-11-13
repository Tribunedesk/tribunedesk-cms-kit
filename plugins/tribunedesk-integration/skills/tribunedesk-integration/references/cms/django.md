# Django (custom CMS on Django)

Contract rules come from the downloaded guide; this file is only how to do them in Django.

## 1. Raw body and the webhook route

- One view, e.g. `td/webhook/` (or `td/webhook/<org_code>/` for several organizations), decorated
  with `@csrf_exempt` and `@require_POST`. The signature replaces CSRF.
- Verify on `request.body` (bytes) **before** `json.loads`. Do not route it through Django REST
  Framework parsers; if the project uses DRF, keep this one view plain Django.
- Headers: `request.headers["webhook-id"]` (case-insensitive).
- Signature: the `standardwebhooks` Python package, or the check in the contract's
  `examples/python/level1_receiver.py`.
- Watch `APPEND_SLASH`: register the exact path with its trailing slash so no redirect happens.

## 2. Secret and token

- Read from environment variables in `settings.py`: `TD_WEBHOOK_SECRET`, `TD_CMS_TOKEN`,
  `TD_API_BASE` (default the production address). `django-environ` or `os.environ`.
- `.env.example` with the names only. Never in fixtures, migrations or the admin.

## 3. Unique key and lock

- A model such as `TribuneDeskArticle(article_id=UUIDField(unique=True), post=OneToOneField(...),
  last_sent_at=DateTimeField(), last_delivery_id=..., internal_links=JSONField(), ...)`.
- Upsert inside `transaction.atomic()` with `select_for_update()` on the row; create with
  `get_or_create` under the unique constraint and retry once on `IntegrityError` (two attempts
  can race to create).
- Compare `sent_at` with `last_sent_at` inside the lock.

## 4. Publish hook and link back

- Level 2: a `post_save` signal (or the publish action/service) when the post becomes public.
- Send the link back from a background task (Celery, Django-Q, `django-tasks`, or a simple
  outbox table processed by a management command on cron) so a failure retries without blocking
  the editor. A repeat is harmless.

## 5. Edit URL

Build it without request context: `settings.SITE_URL + reverse("admin:blog_post_change",
args=[post.pk])` (or the CMS's own editor route). `request.user` does not exist in a delivery.

## 6. Images

- Download only from the allowed hosts (guide 1, "Where images come from"); fetch them in a
  background task after answering, then attach to the post.
- `requests`/`httpx` with a timeout and a size limit; store through the project's storage
  (`default_storage`).

## 7. Developer commands

Management commands in `<app>/management/commands/`:

- `python manage.py td_inspect <article_id>` prints the JSON the kit README defines;
- `python manage.py td_publish <article_id>` publishes the post (runs the same code as the
  editor's publish, so the link back fires);
- `python manage.py td_poll` runs one read mode poll.

Print with `self.stdout.write(json.dumps(..., ensure_ascii=False))`.

`publish` sends the link back before it exits, so `check` finds it: it reads the report right after
the command returns. A retry queue may still handle a failed send later.

## 8. Running the project's tests

`python manage.py test` or `pytest` (with `pytest-django`), whichever the project uses. Test the
signature check with the contract's signature vectors (`examples/vectors/webhook-signature.json`
in the downloaded docs) and the upsert with two calls for one `article_id`.

## 9. Pitfalls

- `request.POST` is empty for JSON; `request.body` can be read once before something else reads
  the stream.
- `USE_TZ = True`: parse `sent_at` with `datetime.fromisoformat` and compare aware datetimes.
- Middleware that rewrites responses (GZip, locale redirects) must not touch the webhook path.
- Long-running image downloads inside the view break the 30-second answer limit.

## 10. Level 4 (media library)

The model (state, queue, screens, staging) is in `references/cms/generic.md`, section 10. In
Django:

- A model `SyncState` (one row: cursor, attempts, resync flag) and fields or a one-to-one model
  on the photo model (`asset_id`, field versions as a `JSONField`, set-aside values, send result),
  plus `MediaEdit` (photo, field, `changed_at`, unique together).
- A `post_save` signal fills the edit queue; apply feed changes with a flag (a thread-local or an
  `update_fields` call that the signal skips) so they do not enter it.
- `select_for_update()` on the `SyncState` row inside `transaction.atomic()` is the lock; run the
  cycle from cron or Celery beat, never from a view.
- Admin views (`ModelAdmin` actions or a custom admin page) for held batches and the resync
  preview.
- Management commands for `TDKIT check`: `td_sync`, `td_media_inspect <cms_media_id>`,
  `td_media_add <file>`, `td_media_edit <cms_media_id> <field> <value>`,
  `td_media_delete <cms_media_id>`, `td_media_reset`.
