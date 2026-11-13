# Changelog

Changes of the Tribune Desk CMS API contract, newest first. Versions follow [Versioning](VERSIONING.md).

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
