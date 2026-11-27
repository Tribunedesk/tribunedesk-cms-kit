# Node.js / Express (custom CMS)

Contract rules come from the downloaded guide.

## 1. Raw body and the webhook route

- Mount the route with a raw parser **before** any global `express.json()`:
  `app.post('/td/webhook', express.raw({ type: 'application/json', limit: '2mb' }), handler)`.
  `req.body` is then a `Buffer`; verify it, then `JSON.parse(req.body.toString('utf8'))`.
- Signature: the `standardwebhooks` npm package, or `crypto.createHmac('sha256', key)` with
  `crypto.timingSafeEqual`.
- No CSRF middleware on this route (`csurf` and similar).
- Fastify: `addContentTypeParser('application/json', { parseAs: 'buffer' }, ...)` for the route.
  Next.js route handlers: `await request.text()` before parsing.

## 2. Secret and token

`process.env.TD_WEBHOOK_SECRET`, `TD_CMS_TOKEN`, `TD_API_BASE` (`dotenv` locally); `.env` in
`.gitignore`, `.env.example` with the names only.

## 3. Unique key and lock

- A unique index on `article_id`, and the upsert in one transaction: PostgreSQL
  `INSERT … ON CONFLICT (article_id) DO UPDATE … WHERE excluded.sent_at > td_articles.sent_at`
  does the "older send" rule atomically; or `SELECT … FOR UPDATE` then write.
- Prisma: `$transaction` with an interactive transaction and a raw `FOR UPDATE`, or the
  conditional upsert in raw SQL.

## 4. Publish hook and link back

Where the CMS publishes (a service method, a model hook), enqueue a job (BullMQ, pg-boss, an
outbox table polled by a worker) that sends the link back with `fetch`. A repeat is harmless.

## 5. Edit URL

`${process.env.TD_SITE_URL}/admin/posts/${id}/edit` (the app's own editor route), built without
the current user; `TD_SITE_URL` is the public address of the site (`references/cms/generic.md`,
section 5) and gives the `permalink` too.

## 6. Images

Check the host, answer, then download in the job (`fetch` with `AbortSignal.timeout`), store and
attach.

Testing with `tdkit`: the mock serves images over https with a test certificate. Trust its CA, the file `TDKIT check` prints as `TD_CA_BUNDLE`, in the test environment only, through `NODE_EXTRA_CA_CERTS=$TD_CA_BUNDLE` in the environment of the process. Never in production: there the system's CAs stay.

## 7. Developer commands

Scripts in `package.json`, run with node directly so `tdkit` can call them without a shell:
`node scripts/td.js inspect <article_id>`, `node scripts/td.js publish <article_id>`,
`node scripts/td.js poll`. (`npm run td -- inspect …` works too; on Windows `tdkit` finds
`npm.cmd` on `PATH`.) At level 3, when the app has categories or tags,
`node scripts/td.js taxonomy-sync` sends them as one full run to `POST /v3/cms/taxonomy/terms`.

`publish` sends the link back before it exits, so `check` finds it: it reads the report right after
the command returns. A retry queue may still handle a failed send later.

## 8. Running the project's tests

`npm test` (Jest, Vitest or `node --test`), with `supertest` for the route: a signed request
(mock secret) and two attempts for one `article_id`.

## 9. Pitfalls

- A global `express.json()` registered first consumes the stream: the raw route gets an empty
  body or a parsed object, and the signature fails.
- `bodyParser.json({ verify })` keeping a raw copy also works, but only if every path keeps it.
- Comparing signatures with `===` leaks timing; use `timingSafeEqual` on equal-length buffers.
- Serverless platforms may decode or re-encode bodies; check the platform's raw body option.

## 10. Level 4 (media library)

The model (state, queue, screens, staging) is in `references/cms/generic.md`, section 10. In
Node:

- Tables `td_sync_state` (one row: cursor, attempts, resync flag, open preview id) and
  `td_media` keyed by the app's media id (`asset_id`, field versions as JSON, set-aside values,
  send result), plus `td_media_edits` (media id, field, `changed_at`, unique per media and field)
  and `td_media_deletions`.
- Fill the edit queue where the app saves a media item (the service method or the ORM hook); the
  sync applies feed changes through a path that skips it (a flag argument, or a direct update).
- The lock: `SELECT … FOR UPDATE` on the `td_sync_state` row in a transaction (PostgreSQL,
  MySQL), `BEGIN IMMEDIATE` on SQLite, or a lock row with an expiry. In-process locks do not
  work across workers.
- Run one cycle from a scheduler outside web requests: a system cron line calling
  `node scripts/td.js sync`, a `node-cron` or BullMQ repeatable job in a worker process, every
  few minutes; queue a delayed job a minute after an edit.
- Admin pages (the app's own) for held batches and the resync preview.
- Commands for `TDKIT check`: `node scripts/td.js sync`, `media-inspect <cms_media_id>`,
  `media-add <file>`, `media-edit <cms_media_id> <field> <value>`, `media-delete <cms_media_id>`,
  `reset`.
