# Changelog

Changes of the Tribune Desk CMS API contract, newest first. Versions follow [Versioning](VERSIONING.md).

## 3.8.0-draft – 2026-11-25

- `POST /v3/cms/taxonomy/terms` (`articles:write`): your CMS sends its categories and tags, up to 1000 per request; a full run (`run_id`, `is_last`) also removes the terms your CMS no longer has; run one full run at a time, since a page with a new `run_id` abandons the previous run. `GET /v3/cms/status` shows `taxonomy`.
- `ArticleDelivery` has an optional `taxonomy` (`categories` and `tags`, each term with `name` and, when known, `cms_term_id`): the terms the editor chose. Without it, nothing changes.
- `ArticleDeliveryResult` (and the read-mode result) has an optional `taxonomy`: the categories and tags of the post after the delivery, and the `ignored` terms with a `reason` (`unknown_term` or `wrong_taxonomy`; more values may be added).

**Integrators:**

- `L3`: send your categories and tags to `POST /v3/cms/taxonomy/terms` (a full run daily, single changes as they happen); set the terms a delivery names in `taxonomy` (by `cms_term_id`, else by name; never create terms) and answer with `taxonomy`.

## 3.7.1-draft – 2026-11-25

- `examples/python/level1_receiver.py` applies `publication` and answers with it, as guide 1 asks since 3.7.0-draft.
- `examples/payloads/article-delivered.json` asks for a draft in `publication`; its scheduled time had passed, so a receiver tested on the sample published it at once.

**Integrators:**

- Nothing to do.

## 3.7.0-draft – 2026-11-24

- `ArticleDelivery` has an optional `publication` (`mode` `draft`, `schedule` with `at`, or `publish`): how the editor wants the post published. Without it, nothing changes.
- `ArticleDeliveryResult` (and the read-mode result) has an optional `publication` (`status` `draft`, `scheduled` or `published`, and `at`): the state of the post after the delivery.
- Guide 1: a scheduled post takes a new send like a draft; a published post is never unpublished.

**Integrators:**

- `L1`: publish, schedule or keep a draft as `publication` asks, answer with `publication`, and update a scheduled post on a new send as you update a draft.

## 3.6.1-draft – 2026-11-24

- Guide 1: `html` may carry images from the media library as `figure` with `data-td-asset-id` and `data-td-cms-media-id` on the `img`; the guide used to say there are no media in the body.

**Integrators:**

- `L1`: keep `figure`/`img` from `html` through your content filter, including the `data-td-*` attributes on `img` (a sanitizer that drops unknown `data-*` breaks `L4`).
- `L4`: recommended, not a "Done when" point: turn a figure with your `data-td-cms-media-id` into your native image instead of downloading the file.

## 3.6.0-draft – 2026-11-21

- **Breaking:** `POST /v3/cms/media` answers `rejected` with `collage`, `screenshot`, `graphic` or `import_failed` for a file Tribune Desk already received and its import refused; it used to answer `known` with `asset_id` `null`.

**Integrators:**

- `L4`: do not send a file to `POST /media` again after `rejected` with `collage`, `screenshot`, `graphic` or `import_failed`.

## 3.5.1-draft – 2026-11-17

- `examples/python/level1_receiver.py` keeps embeds only from trusted players and removes other scripts, as guide 1 asks since 3.5.0-draft.

**Integrators:**

- Nothing to do.

## 3.5.0-draft – 2026-11-17

- Guide 1: which embeds to keep in `html`, and that a delivery arrives with no editor logged in.
- Guide 2: a failed report of the published address is sent again; posts public before the token are reported once.
- Guide 4: files already in the library are not sent as new files.

**Integrators:**

- `L1`: keep an `iframe` only from players you trust and remove every `script` other than the AI label block, with its content; check that your content filter keeps those embeds when no editor is logged in.
- `L2`: send a report of the published address again when it fails with a network error, `429` or `5xx`.
- `L4`: do not send files that were in your library before level 4 as new files.

## 3.4.2-draft – 2026-11-12

- README: “Build it with Claude”, the Claude Code plugin that builds and tests an integration.
- Guide 1: “Done when” covers overlapping attempts, `image_hosts` and read mode; read mode says where a poll without a cursor starts and how `GET /v3/cms/articles/awaiting` pages.
- Guide 2: `published_at` without a time zone fails the whole request with `422`; “Done when” covers `social_queue_exclude`.
- Guide 3: going back to earlier posts when a link target is published is optional, as the chapter says.
- `examples/python/level1_receiver.py` answers an older send with `status`.

**Integrators:**

- Nothing to do.

## 3.4.1-draft – 2026-11-08

- README: what to ask Tribune Desk for, per level.
- Every version in this CHANGELOG lists what integrators must do.
- `examples/vectors/webhook-signature.json`: signature test vectors for receivers.
- The 3.4.0-draft note on request bodies names its exception, `ArticleResultReport`.

**Integrators:**

- Nothing to do.

## 3.4.0-draft – 2026-11-07

- Every delivery is signed: an organization without a signing secret gets no deliveries.
- Schemas of what Tribune Desk sends no longer forbid unknown properties (`additionalProperties`); request bodies still do, except `ArticleResultReport` (`POST /v3/cms/articles/{article_id}/result`), which lists unknown fields in `ignored_fields`.
- `sent_at` is when the editor made the send, the same in every attempt (retries used to carry the time of the attempt).
- `ArticleDeliveryResult`: optional `social_queue_exclude`, stored before `permalink`.
- Read mode: `GET /v3/cms/articles/{article_id}` returns the `X-Delivery-Id` header; `POST /v3/cms/articles/{article_id}/result` takes `ArticleResultReport` with optional `delivery_id` and `error` and answers with `ignored_fields`; new `GET /v3/cms/articles/awaiting`.
- `DeliveryImage.cms_media_id` and `FeaturedImageResult.cms_media_id`: the file identifier as text. `cms_attachment_id` and `attachment_id` are deprecated.
- `GET /v3/cms/status` lists `image_hosts`.
- `409` descriptions name only the codes each route returns; `POST /result` documents `state_conflict` (it said `conflict`).
- Webhook headers are declared as parameters; `429` and `503` declare `Retry-After`; `GET /v3/cms/openapi.json` is in `paths`.
- A path id that is not a UUID gives `404 not_found` (it gave `422`).
- `POST /v3/cms/articles/published`: an article of another organization is `not_found`; `forbidden` is no longer returned.
- Retries honour `Retry-After` of your answer, up to one hour.

**Integrators:**

- `L1`: answer `401` to a delivery without a valid signature; every delivery is signed now.
- `L1`: do not validate deliveries with a schema that rejects unknown properties.
- `L1`: skip a body whose `sent_at` is older than the one you applied last; `sent_at` is now the time of the send.
- `L4`: read `cms_media_id` (text) instead of `cms_attachment_id`, and answer `featured_image.cms_media_id` instead of `attachment_id`.
- `L2`: send `social_queue_exclude` together with `permalink` in the delivery answer when your CMS has such a setting.
- `L2`: treat `forbidden` from `POST /v3/cms/articles/published` like `not_found`.
- `L1`: without `settings:read`, take `image_hosts` from `GET /v3/cms/status`; a token with `articles:read` is enough.
- `read`: send `delivery_id` (from `X-Delivery-Id`) with the result, send `error` when your CMS could not take the article, and after `410 cursor_expired` go through `GET /v3/cms/articles/awaiting`.
- `read`: match `state_conflict` on a `409` from `POST /v3/cms/articles/{article_id}/result`; the docs used to say `conflict`.

## 3.3.0-draft – 2026-11-06

- `POST /v3/cms/articles/published`: optional `social_queue_exclude` per item keeps a post off the Tribune Desk Facebook queue. Leaving it out keeps the stored value.
- **Breaking** (2026-11-06): `X-Webhook-Secret` is no longer sent with deliveries. The signature (`webhook-id`, `webhook-timestamp`, `webhook-signature`) is the only authentication of a delivery.
- **Breaking** (2026-11-06): `POST /v2/cms/published-urls` is removed. Use `POST /v3/cms/articles/published`.

**Integrators:**

- `L1`: verify the signature; `X-Webhook-Secret` is no longer sent.
- `L2`: move from `POST /v2/cms/published-urls` to `POST /v3/cms/articles/published`.
- `L2`: send `social_queue_exclude` with each item when your CMS has such a setting.

## 3.2.0-draft – 2026-11-04

- Deliveries are signed following Standard Webhooks (`webhook-id`, `webhook-timestamp`, `webhook-signature`) when the organization has a signing secret. `X-Webhook-Secret` is deprecated.
- Scopes `articles:read` and `articles:write` for `tdcms_` tokens.
- `POST /v3/cms/articles/published`: the link back with a `tdcms_` token. `POST /v2/cms/published-urls` is deprecated.
- Read mode: change kind `article_sent`, `GET /v3/cms/articles/{article_id}` and `POST /v3/cms/articles/{article_id}/result`.
- `link_placeholder_prefix` in `ArticleDelivery`.
- `image_hosts` in `GET /v3/cms/settings`.
- `GET /v3/cms/status` and `GET /v3/cms/changes` accept `articles:read`.

**Integrators:**

- `L1`: verify the Standard Webhooks signature of deliveries.
- `L2`: use a `tdcms_` token with `articles:write` for the link back.
- `L3`: read `link_placeholder_prefix` from each delivery instead of a fixed prefix.
- `L1`: download images only from the hosts in `image_hosts` of `GET /v3/cms/settings`.
- `read`: read mode is available for a CMS without a public endpoint.

## 3.1.0-draft – 2026-11-03

- The `article.delivered` webhook is part of the contract, with `ArticleDelivery` and `ArticleDeliveryResult`.
- New fields `excerpt` and `featured_image` next to the existing ones.
- Tribune Desk stores `cms_post_id` and `edit_url` from your answer.

**Integrators:**

- `L1`: answer with `cms_post_id` and `edit_url`, and use `excerpt` and `featured_image`.

## 3.0.0-draft – 2026-10-31

- First version of `/v3/cms`: media sync (changes feed, new files, field changes, deletions, resync, held batches, settings, historical import).

**Integrators:**

- `L4`: first version of the media sync; build it from the guide.
