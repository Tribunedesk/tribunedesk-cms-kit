# Tribune Desk CMS API: integration guide

This API connects a content management system (CMS) with Tribune Desk, a newsroom tool that writes articles. Your CMS receives the articles editors send, tells Tribune Desk where they were published, and can keep its media library in sync. Any CMS can be a client; nothing here assumes a particular product. The Tribune Desk plugin for WordPress is one implementation of it; you do not need it to build your own.

The guide, the examples and the OpenAPI document live in the public repository [tribunedesk/tribunedesk-cms-api](https://github.com/tribunedesk/tribunedesk-cms-api). A Polish version is in its [`pl`](https://github.com/tribunedesk/tribunedesk-cms-api/tree/main/pl) folder.

For media, the API lets the CMS keep the metadata of its media files (title, alt text, caption, description) in sync with Tribune Desk, in both directions. The CMS is the client: it asks Tribune Desk for changes and sends its own. Tribune Desk never calls your API (the one call it makes is the [article delivery webhook](guide/1-article-delivery.md#article-delivery-webhook)), but it does fetch the file URLs you send, so they must be publicly fetchable (no login, no IP restriction).

## Integration levels

Each level works without the higher ones. Start with level 1, which is a day of work, and add the others when you need them. Level 3 adds fields to the same deliveries as level 1; it does not need new routes.

| Level | What your CMS does | What it uses | What the newsroom gets |
|---|---|---|---|
| [1. Article delivery](guide/1-article-delivery.md) | exposes an endpoint and makes a draft post from the title, HTML, excerpt and main image | the `article.delivered` webhook, or read mode | “Send to CMS” |
| [2. Link back](guide/2-link-back.md) | reports the address and date of publication | `POST /v3/cms/articles/published` | the link in Tribune Desk; the article becomes a link target |
| [3. Full content](guide/3-full-content.md) | resolves internal links, keeps the “read more” box, SEO, author, language, AI label | the level 3 fields of the delivery | full publishing quality |
| [4. Media library](guide/4-media-library.md) | syncs files and their descriptions both ways | the media, settings, held, resync and backfill routes | one library |
| [5. Archive](guide/5-archive.md) | sends older articles | planned | links to the archive |

The contract is described by the [OpenAPI document](openapi.json) (also served at `https://api.tribunedesk.com/v3/cms/openapi.json`). How versions change: [Versioning](VERSIONING.md). What changed: [CHANGELOG](CHANGELOG.md). Working clients in Python: [level 1](examples/python/level1_receiver.py) and [level 2](examples/python/level2_link_back.py).

## Build it with Claude

An open-source plugin for Claude Code builds and tests an integration for your CMS, at the levels you choose. It reads this guide at a tagged version, asks what you need, tells you what to ask Tribune Desk for, writes the code and checks it against a local mock of Tribune Desk before any real delivery. When the contract changes, it lists what your integration must change and updates it.

```
/plugin marketplace add tribunedesk/tribunedesk-cms-kit
/plugin install tribunedesk-integration@tribunedesk
```

Then ask: “Build me an integration with Tribune Desk.” The plugin does not order tokens and does not deploy: the setup on the Tribune Desk side stays with your contact (see [What to ask Tribune Desk for](#what-to-ask-tribune-desk-for)). The same repository, [tribunedesk/tribunedesk-cms-kit](https://github.com/tribunedesk/tribunedesk-cms-kit), has `tdkit`: the local mock and the conformance checks, which you can run without Claude. A CMS written in PHP can use the protocol rules from [tribunedesk/tribunedesk-cms-php](https://github.com/tribunedesk/tribunedesk-cms-php).

## What works today

- **Working now:** `GET /v3/cms/status` and `GET /v3/cms/changes` (need `media:read` or `articles:read`), `GET /v3/cms/held` (needs `media:read`), `GET /v3/cms/articles/{article_id}` and `GET /v3/cms/articles/awaiting` (need `articles:read`), `POST /v3/cms/articles/{article_id}/result` and `POST /v3/cms/articles/published` (need `articles:write`),`POST /v3/cms/media`, `POST /v3/cms/media/fields`, `POST /v3/cms/media/{asset_id}/link`, `POST /v3/cms/media/push-existing`, `POST /v3/cms/media/deletions`, `POST /v3/cms/resync` and `POST /v3/cms/held/{held_id}/decision` (need `media:write`), `GET /v3/cms/settings` and `PUT /v3/cms/settings` (need `settings:read` and `settings:write`), `GET /v3/cms/backfill/requests` and `POST /v3/cms/backfill/requests/{request_id}/pages` (need `backfill:write`) and `GET /v3/cms/openapi.json` (no token). A super admin enables the integration for your organization; the first poll does not enable it, but it does switch your organization to this API (see Switching to this API). Until then `state` in `/status` is `disabled` and `GET /changes`, `/settings` and `POST /resync` answer `409` with `state_conflict`. Once enabled, `state` is `active`, or `stalled` when there has been no poll for 24 hours. `last_changes_poll_at` and `pending_changes` are `null` while disabled. `held_batches` counts the batches waiting for a decision (`null` while disabled). `recent_errors` is always empty today: nothing fills it yet, so an empty list does not mean there were no errors, and a file that failed to import does not show up there. Today the feed carries changes of `kind="fields"`, `kind="new_asset"`, `kind="settings"`, with `td_deletion_marks_in_cms`, `kind="deleted"` and `kind="restored"`, and, in read mode for tokens with `articles:read`, `article_sent`. The organization has one acknowledged position in the feed, whichever token passes the cursor, and only polls of a token with `media:read` move it and count for `stalled` and `pending_changes`; a token with only article scopes reads with the same kind of cursor without moving them. In read mode without a media client, `stalled` means a send has waited more than 24 hours for your CMS to read it. New files, field changes and deletions sent by the CMS are accepted now.
- **Planned routes:** none today. A future operation that is not ready yet carries `x-status: planned` in the OpenAPI document; it checks your token and scope, then answers `501` with error code `not_implemented`. Order of checks on such a route: `401` (token), `403` (scope), `429` (rate limit), `409` (frozen organization, for writes), `422` (request shape), then `501`. A malformed JSON body is rejected with `422` before the token check, so it never reaches authentication.

## Getting a token and scopes

Tokens are issued by Tribune Desk; there is no self-service sign-up. Ask your Tribune Desk contact. A token belongs to one organization and carries a set of scopes. Send it on every request:

```
Authorization: Bearer tdcms_...
```

Keep it secret, store it outside source control, and ask for a new one if it leaks. A token does not expire; only a super admin revokes it. An organization can hold several tokens at once, so to rotate one: get a new token, switch your CMS to it, then ask for the old one to be revoked. A missing, unknown or revoked token gives `401`. A valid token without the scope of the route gives `403`.

| Scope | Allows |
|---|---|
| `media:read` | read changes, status and held batches |
| `media:write` | send new files, field changes, deletions and links; decide held batches; start a resync; push existing files |
| `settings:read` | read the sync settings |
| `settings:write` | change the sync settings |
| `backfill:write` | take part in the one-time import of historical files |
| `articles:read` | read status, and in read mode the `article_sent` changes and the sent articles |
| `articles:write` | report where articles were published (link back) and the result of a delivery in read mode |

Check what your token can do:

```
curl -sS https://api.tribunedesk.com/v3/cms/status \
  -H "Authorization: Bearer $TD_CMS_TOKEN"
```

```
{"org_code":"example-org","contract_version":"3.4.2-draft","scopes":["media:read"],"state":"active", ...}
```

## What to ask Tribune Desk for

Tribune Desk sets up each integration by hand. Pick the levels you build, then ask your Tribune Desk contact for what their rows list.

| Level | Ask for | Why |
|---|---|---|
| 1, webhook | a signing secret (`whsec_`, shown once) and your webhook address set for your organization (`https://` on a public host); a newsroom user can also set it in Tribune Desk Settings, Integrations | Without an active signing secret or a webhook address, “Send to CMS” sends nothing. The integration does not need to be enabled. |
| 1, webhook, image hosts | a token with `articles:read`, or the list of Tribune Desk storage hosts | With the token, `GET /v3/cms/status` lists `image_hosts`, the hosts you may download images from. |
| 1, read mode | read mode switched on for your organization, the integration enabled, and a token with `articles:read` and `articles:write` | Read mode works only while the integration is enabled; you read sent articles and report the result with these scopes. |
| 2 | a token with `articles:write` (a read mode token already has it) | The link back needs only this scope; the integration does not need to be enabled. |
| 3 | nothing for links, SEO, author and the AI label; for the “read more” box, ask Tribune Desk to switch it on for your organization | Until it is switched on, deliveries leave out `backlink_sources`. |
| 4 | the integration and the media library enabled for your organization; a token with `media:read`, `media:write` and `settings:read`, plus `settings:write` if your CMS changes the sync settings and `backfill:write` for the historical import; the extra hosts that serve your files (a CDN, a media subdomain) | The media routes answer `409` until both are switched on; Tribune Desk fetches your files only from allowed hosts. |

One token may carry every scope you need; ask for one token per organization. Everything else is in this guide: you can build your integration and test it before you get any of these.

## Routes and the scope each needs

| Route | Scope | Purpose |
|---|---|---|
| `GET /v3/cms/status` | `media:read` or `articles:read` | Integration state and counters (working today) |
| `GET /v3/cms/changes` | `media:read` or `articles:read` | Pull changes since a cursor (working today); each token sees only the kinds of its scopes |
| `POST /v3/cms/media` | `media:write` | Send files that are new in the CMS (working today) |
| `POST /v3/cms/media/{asset_id}/link` | `media:write` | Confirm the CMS took a file from Tribune Desk (working today) |
| `POST /v3/cms/media/fields` | `media:write` | Send field changes (working today) |
| `POST /v3/cms/media/deletions` | `media:write` | Report files deleted in the CMS (working today) |
| `POST /v3/cms/media/push-existing` | `media:write` | Queue existing Tribune Desk files for the CMS (working today) |
| `GET /v3/cms/settings` | `settings:read` | Read the sync settings and limits (working today) |
| `PUT /v3/cms/settings` | `settings:write` | Save the sync settings (working today) |
| `POST /v3/cms/resync` | `media:write` | Compare fields after an outage or an expired cursor (working today) |
| `GET /v3/cms/held` | `media:read` | List held batches (working today) |
| `POST /v3/cms/held/{held_id}/decision` | `media:write` | Send or discard a held batch (working today) |
| `GET /v3/cms/backfill/requests` | `backfill:write` | Export requests for the historical import |
| `POST /v3/cms/backfill/requests/{request_id}/pages` | `backfill:write` | Upload one page of export results (up to 1000 candidates) |
| `GET /v3/cms/articles/awaiting` | `articles:read` | List sends waiting for a result (read mode) |
| `GET /v3/cms/articles/{article_id}` | `articles:read` | Read a sent article (read mode) |
| `POST /v3/cms/articles/{article_id}/result` | `articles:write` | Report the outcome of a sent article (read mode) |
| `POST /v3/cms/articles/published` | `articles:write` | Report where delivered articles were published (level 2, link back) |

## Retries

- Retry on `429`, `500`, `503`, network errors and the `502` and `504` a gateway may answer without our JSON body: wait at least `retry_after` seconds, then back off exponentially with jitter. Our `Retry-After` header holds the same whole number of seconds as `retry_after`; a gateway may send it as a date.
- Do not retry other `4xx` errors unchanged: fix the request or the state first.
- Keep your retries idempotent: store a cursor only after applying its changes, and key your own records by the ids in the request (`cms_media_id`), so that repeating a batch does not create duplicates. A repeated file answers `known` and a repeated field change `unchanged`.
- If your process died before storing the cursor, poll again with the old cursor and apply the changes again.

Every route is safe to repeat after a lost answer. What a repeat gives:

| Route | Repeat answers |
|---|---|
| `POST /media` | `known`. |
| `POST /media/fields` | `unchanged` for values applied; waiting values stay in their batch. |
| `POST /media/{asset_id}/link` | `known`. |
| `POST /media/deletions` | `known`. |
| `POST /media/push-existing` | Queues nothing twice: files with an unread change are skipped. A lost `next_after` is harmless; repeat the same call. |
| `POST /resync`, a preview page | Replaces that page. A first page repeated without `resync_id` starts a second session; drop the first. A last page repeated gives `409`: start a new preview. |
| `POST /resync`, a confirmation | The same answer and cursor. |
| `POST /held/{held_id}/decision` | `409`: read `GET /held` and compare `state`. |
| `PUT /settings` | The same settings. |
| `POST /backfill/requests/{request_id}/pages` | The same results. After a lost answer to a last page: `409`, which means done. |

## Errors

Every error produced by the application on these routes has the same JSON body (errors from a gateway or proxy in front of it may not): `{"code": "...", "message": "...", "retry_after": 5}`. `retry_after` is present only when waiting helps. Messages are for people; match on `code`. The body never echoes values you sent; a validation error can still name an unknown field.

| Code | HTTP | Meaning and what to do |
|---|---|---|
| `unauthorized` | 401 | Token missing, unknown or revoked. Check the header; ask for a new token. |
| `forbidden` | 403 | The token lacks the scope of this route. Ask for the scope. |
| `not_found` | 404 | No such object in your organization. Check the id; do not retry. |
| `project_deactivated` | 409 | The organization is frozen and rejects writes (`POST`, `PUT`). Reads, including `GET /changes` and `GET /settings`, still work and never answer this code. Stop writing and contact Tribune Desk. |
| `option_locked` | 409 | You tried to change a setting locked by Tribune Desk (see `locked_options` in the settings). Leave it as it is. |
| `state_conflict` | 409 | The object is not in a state that allows this, for example a held batch already decided, or a resync preview that is not ready, has expired or predates a re-enable of the integration, or the integration not being enabled. Re-read the state and act on that. On `GET /changes` and `GET /settings` it means only that the integration is not enabled. |
| `cursor_expired` | 410 | Your cursor is older than 90 days, or the integration was disabled and enabled again since you got it. Run a resync and resume from the cursor it returns. |
| `validation_error` | 422 | The request does not match the schema; the message names the fields. Fix the request; do not retry it unchanged. |
| `rate_limited` | 429 | Too many requests. Wait `retry_after` seconds, then retry. |
| `internal_error` | 500 | Our fault. Retry with back-off; report it if it persists. |
| `not_implemented` | 501 | The route is planned and not available yet. Do not retry. |
| `unavailable` | 503 | Temporary. Wait `retry_after` seconds, then retry. |

## Rate limit

600 requests per minute per token. The window is fixed (one clock minute), not sliding, so a burst around a minute boundary may pass, up to twice the limit within a short time. Do not rely on that. Over the limit you get `429` with `rate_limited`, `retry_after` and a `Retry-After` header. The same `429` with a short wait (about a second) is returned when the limiter is momentarily busy. Handle both the same way: wait, then retry, without a tight loop. There are no headers with the remaining quota; a normal sync stays far below the limit.

The settings response lists the limits that apply to you (batch size, field length, file URL lifetime, requests per minute).
