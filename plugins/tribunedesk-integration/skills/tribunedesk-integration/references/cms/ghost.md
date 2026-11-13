# Ghost

Ghost (and Ghost(Pro)) cannot host a custom endpoint, so the integration is a **bridge**: a
small separate service (any language; Node is natural) that receives deliveries and calls the
Ghost Admin API. Without a public address for the bridge, use **read mode**: the bridge polls
Tribune Desk instead. Say both limits at stage 2:

- **No level 4:** Ghost has no media library entity, so media sync is not possible.
- **HTML is converted:** Ghost stores posts in Lexical; HTML sent with `?source=html` is
  converted and unknown elements and `<script>` blocks are dropped. Put the AI label into the
  post's code injection head instead.

Contract rules come from the downloaded guide.

## 1. Raw body and the webhook route

The bridge's own route, e.g. `POST /td/webhook` with a raw body parser (see
`node-express.md`, section 1). Verify, then call Ghost.

## 2. Secret and token

Bridge environment variables: `TD_WEBHOOK_SECRET`, `TD_CMS_TOKEN`, `TD_API_BASE`, and the Ghost
Admin API key (`GHOST_ADMIN_API_KEY`, from a Ghost custom integration) plus `GHOST_URL`. Never in
the bridge's repository.

## 3. Unique key and lock

Ghost has no custom post fields: keep the mapping `article_id → ghost post id` (plus
`last_sent_at`, links, read-more relations) in the bridge's own database (SQLite is enough),
with a unique key on `article_id` and a transaction around the upsert. For updates send Ghost's
`updated_at` with the edit (Ghost rejects a stale one), and retry once after re-reading.

## 4. Publish hook and link back

A Ghost webhook (`post.published`, and `post.published.edited` for slug changes) to the bridge;
the bridge sends the link back from a retrying job.

## 5. Edit URL

`<GHOST_URL>/ghost/#/editor/post/<id>`.

## 6. Images

Download only from allowed hosts, upload with the Admin API images endpoint, then set the post's
feature image, its alt text and caption.

## 7. Developer commands

Bridge CLI scripts: `node bridge.js inspect <article_id>`, `node bridge.js publish <article_id>`
(publishes through the Admin API), `node bridge.js poll`. `inspect` reads the bridge database and
Ghost.

`publish` sends the link back before it exits, so `check` finds it: it reads the report right after
the command returns. A retry queue may still handle a failed send later.

## 8. Running the project's tests

The bridge's own tests (`npm test`), with the Ghost Admin API faked (e.g. `nock`) or a local Ghost
(`ghost-cli` / Docker). `tdkit check` runs against the bridge.

## 9. Pitfalls

- Excerpt length is limited in Ghost (custom excerpt): cut it, the guide says text fields have no
  limit on the Tribune Desk side.
- Authors must be Ghost staff users; fall back to the default author.
- The "read more" box needs a theme helper or rewriting older posts (each rewrite is a Ghost
  revision): say this cost before agreeing to level 3.
- No focus keyphrase field: store it in the bridge or drop it.
