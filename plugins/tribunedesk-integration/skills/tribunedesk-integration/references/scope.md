# Scope: from the user's words to levels and mode

The levels and what each gives the newsroom are in the downloaded `README.md`, table
"Integration levels"; each level has its own chapter in `guide/`. This file only helps you map
what the user says onto them.

## Typical answers

| The user says | Levels | Delivery | Notes |
|---|---|---|---|
| "Articles should land in our CMS as drafts" | 1 | webhook | The minimum. |
| "Articles and links" / "Tribune Desk should know where we published" | 1 + 2 | webhook | Level 2 lets other articles link to the published post. |
| "Everything: links inside articles, the read-more box, SEO, the AI label" | 1 + 2 + 3 | webhook | Level 3 is more fields of the same delivery, no new route. |
| "Only photos" / "keep our media library in sync" | 4 | none | No webhook. tdkit 1.0 does not test level 4: say so. |
| "Articles, and reuse images already in our library" | 1 + 4 | webhook | Reuse needs level 4 data. |
| "Our CMS is not reachable from the internet" / "only behind VPN" | 1 (+2, +3) | read | The CMS polls Tribune Desk instead of receiving requests. |
| "We are on Ghost(Pro)" | 1 (+2, +3) | webhook through a bridge, or read | Ghost cannot host the endpoint; no level 4 (no media library). See `cms/ghost.md`. |
| "Our old articles too" | none yet | - | Level 5 (archive) has no contract yet (`guide/5-archive.md`). |

When the answer is vague, recommend 1 + 2: it is what most newsrooms need first, and the other
levels can be added later without rework.

## Showing dependencies

Show the chosen set with what each level needs, for example:

```
Level 1  Article delivery   (needed by 2 and 3)
Level 2  Link back          (needs 1)
Level 3  Full content       (needs 1; works best with 2, so links can point to published posts)
Level 4  Media library      (stands alone; 1 + 4 reuses library images in deliveries)
```

## Choosing the delivery mode

- **webhook**: the CMS has a public `https` address Tribune Desk can call. Preferred: articles
  arrive at once.
- **read**: no public address. The CMS polls; read mode must be switched on and the integration
  enabled by Tribune Desk (see the README table "What to ask Tribune Desk for").
- **none**: level 4 only.

For local development neither mode needs a public address: `tdkit check` runs the mock on
`127.0.0.1`. A tunnel (`cloudflared`, `ngrok`) is only for trying a real delivery before launch.

## Where each level is documented

- Level 1: `guide/1-article-delivery.md` (webhook and read mode, signature, fields, images).
- Level 2: `guide/2-link-back.md`.
- Level 3: `guide/3-full-content.md`.
- Level 4: `guide/4-media-library.md`.
- Level 5: `guide/5-archive.md` (planned).
- Errors, scopes, retries: `README.md`.
