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

`${process.env.ADMIN_URL}/posts/${id}/edit`, built without the current user.

## 6. Images

Check the host, answer, then download in the job (`fetch` with `AbortSignal.timeout`), store and
attach.

## 7. Developer commands

Scripts in `package.json`, run with node directly so `tdkit` can call them without a shell:
`node scripts/td.js inspect <article_id>`, `node scripts/td.js publish <article_id>`,
`node scripts/td.js poll`. (`npm run td -- inspect …` works too; on Windows `tdkit` finds
`npm.cmd` on `PATH`.)

## 8. Running the project's tests

`npm test` (Jest, Vitest or `node --test`), with `supertest` for the route: a signed request
(mock secret) and two attempts for one `article_id`.

## 9. Pitfalls

- A global `express.json()` registered first consumes the stream: the raw route gets an empty
  body or a parsed object, and the signature fails.
- `bodyParser.json({ verify })` keeping a raw copy also works, but only if every path keeps it.
- Comparing signatures with `===` leaks timing; use `timingSafeEqual` on equal-length buffers.
- Serverless platforms may decode or re-encode bodies; check the platform's raw body option.
