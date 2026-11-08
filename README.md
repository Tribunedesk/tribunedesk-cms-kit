# tribunedesk-cms-kit

Tools for building a CMS integration with [Tribune Desk](https://tribunedesk.com) and checking
that it works, before you have any access to Tribune Desk itself.

- **`tdkit mock`** runs a local mock of the Tribune Desk CMS API on `127.0.0.1`: the
  `/v3/cms/*` routes of levels 1 to 3 and read mode, tokens and scopes, and signed
  `article.delivered` webhooks.
- **`tdkit check`** runs conformance scenarios against your integration and reports, point by
  point, which parts of the guide's "Done when" it meets. The exit code tells a script or CI
  whether everything passed.

The contract itself (the guide, the OpenAPI document, examples) lives in
[`Tribunedesk/tribunedesk-cms-api`](https://github.com/Tribunedesk/tribunedesk-cms-api). This
kit reads it from a tag of that repository and never copies it. A Claude Code plugin that builds
an integration with these tools is coming to this repository next.

`tdkit` never connects to `api.tribunedesk.com`. The only network host it talks to is GitHub,
to fetch the contract documentation, and not even that when you give it a local copy.

## Run it

You need [uv](https://docs.astral.sh/uv/) and Python 3.12 or newer. No installation:

```bash
uvx --from git+https://github.com/Tribunedesk/tribunedesk-cms-kit@v1.0.0 tdkit --help
```

(Until the `v1.0.0` tag exists, use `@main`.)

### Which contract

`tdkit` supports the contracts `3.4.0-draft` and `3.4.1-draft`. It takes the documentation from,
first found:

1. `--docs DIR`, a checkout of `tribunedesk-cms-api`;
2. the environment variable `TRIBUNEDESK_DOCS_DIR`;
3. its cache, `~/.cache/tdkit/cms-api@<tag>`;
4. `git clone --depth 1 --branch <tag>` of `tribunedesk-cms-api` into that cache.

`--contract v3.4.1-draft` picks a tag; without it `tdkit` takes the newest `v*` tag. A contract
outside the supported range ends with exit code 2 and `contract <v> is not supported by tdkit
<version>; update the plugin`.

## `tdkit mock`

```bash
tdkit mock [--port 8787] [--docs DIR] [--contract TAG] [--read-mode]
           [--token-scopes articles:read,articles:write] [--webhook URL]
```

It prints what your CMS needs and stays in the foreground (Ctrl+C stops it):

- the API at `http://127.0.0.1:8787/v3/cms/`; set `TD_API_BASE=http://127.0.0.1:8787` in your
  CMS;
- the token `tdcms_mock`, with every scope unless `--token-scopes` narrows it;
- the signing secret `whsec_dGRraXQtbW9jay1zaWduaW5nLXNlY3JldC0wMDAwMDA=`.

The token and the secret are public test values: they only work against the mock.

What the mock does:

| Route | Behaviour |
|---|---|
| `GET /v3/cms/status` | `contract_version` of the tag, the token's `scopes`, `state`, `image_hosts` (`["127.0.0.1"]`) |
| `GET /v3/cms/changes` | `article_sent` changes in read mode, only for `articles:read`; opaque cursors; `409 state_conflict` while the integration is disabled; `410 cursor_expired` |
| `GET /v3/cms/articles/awaiting` | the sends still waiting for a result, oldest first |
| `GET /v3/cms/articles/{article_id}` | the sent article with its `X-Delivery-Id`; `404` when it was never sent |
| `POST /v3/cms/articles/{article_id}/result` | closes the send named by `delivery_id`; `409 state_conflict` for a replaced send or a never-sent article; unknown fields come back in `ignored_fields` |
| `POST /v3/cms/articles/published` | `ok`, `not_found` or `invalid_url` per item |
| `GET /v3/cms/openapi.json` | the tag's OpenAPI document, no token |
| `GET /files/<name>` | a small JPEG; the mock records every download |
| any other route of the OpenAPI document | `401` without a token, otherwise `501 not_implemented` (level 4 comes in tdkit 1.1) |

Order of checks, as in the contract: a malformed JSON body `422`, then `401` (token), `403`
(scope), `422` (the body against the schema of the tag's OpenAPI document, literally, with its
`additionalProperties`), then `409`. Errors have the body `{"code", "message"}`.

**Making a send.** `POST http://127.0.0.1:8787/_tdkit/send` (no token; a JSON body, if any,
overrides fields of the tag's sample article) makes a "Send to CMS" of a new article. In read
mode it waits in the feed for your client; otherwise the mock signs it and delivers it once to
`--webhook`, and answers with what your webhook said. Unlike production, the mock may deliver
to `http://localhost`. This route is the mock's own, not part of the Tribune Desk API.

## `tdkit check`

```bash
tdkit check --levels 1,2,3 [--mode webhook|read] --webhook URL
            --inspect-cmd "…{article_id}…" [--publish-cmd "…{article_id}…"] [--poll-cmd "…"]
            [--secret whsec_…] [--social-flag] [--port 8787] [--json report.json]
            [--docs DIR] [--contract TAG]
```

`check` starts the mock itself, on `--port` (default 8787), and sends articles to your
integration, each with a new `article_id`, built from the sample delivery of the tag. Your
integration must be running and configured for the mock:

- webhook mode: your webhook listens at `--webhook` and verifies signatures with the mock's
  secret, or with `--secret` if you configured your own. The report only says whether you gave
  a secret, never its value;
- level 2, level 3 and read mode: your CMS calls the API at `TD_API_BASE=http://127.0.0.1:<port>`
  with the token `tdcms_mock`. `check` also sets `TD_API_BASE` and `TD_CMS_TOKEN` in the
  environment of the commands below.

### The commands your integration provides

`check` cannot look into your database, so the integration gives it three developer commands.
Each is a template: `{article_id}` is replaced by the article's id. The command is split into
arguments (on Windows only double quotes group, so `C:\Users\O'Brien\...` needs no quoting) and
run without a shell, with a 60-second limit. A non-zero exit code fails the scenario.

| Option | Needed for | What the command does |
|---|---|---|
| `--inspect-cmd` | always | prints, as JSON on stdout (UTF-8), the post your CMS made from `{article_id}`, or `null` when there is none |
| `--publish-cmd` | levels 2 and 3 | publishes the post made from `{article_id}`, the way an editor would; your CMS then reports its address (link back) |
| `--poll-cmd` | read mode | runs one poll of your read mode client: `GET /changes`, then fetch, apply and `POST /result` for each sent article |

For example `python manage.py td_inspect {article_id}` (Django) or
`drush td:inspect {article_id}` (Drupal).

**What `--inspect-cmd` prints.** One JSON object, keys by level (extra keys are ignored):

| Level | Key | Value |
|---|---|---|
| 1 | `cms_post_id` | your post id, as text |
| 1 | `title`, `html`, `excerpt` | as stored on the post |
| 1 | `status` | your post status: `draft`, `published`, … |
| 1 | `featured_image_url` | the post's main image (your copy or the delivered URL) |
| 2 | `permalink` | the public address of the post, `null` while it is not public |
| 3 | `seo_title`, `meta_description`, `language` | as stored |
| 3 | `author` | the post's author (any non-empty value) |
| 3 | `read_more` | the `article_id`s of the articles shown in **this** post's "read more" box |
| 3 | `ai_provenance_jws` | the `jws` of the AI label on the public page, or `null` |

### Exit codes and the report

`0` when every scenario that ran passed, `1` when one failed, `2` for a usage or configuration
error (for example `--levels 4`: `level 4 is not covered by tdkit 1.0`). The text report goes to
stdout; for a failed scenario it quotes the guide's point and names the guide file. `--json FILE`
also writes:

```json
{"tdkit": "1.0.0", "contract": "3.4.1-draft", "levels": [1, 2], "mode": "webhook",
 "results": [{"id": "l1-creates-draft", "level": 1, "done_when": "An editor's …",
              "guide": "guide/1-article-delivery.md#done-when", "passed": true, "detail": "…"}]}
```

`passed` is `null` for a skipped scenario (another mode, or `l2-social-flag` without
`--social-flag`), with the reason in `detail`.

### Scenarios

`Done when` quotes the guide: a point of its "Done when" section, or, where the section has no
point for the behaviour, the guide's sentence that requires it.

| id | level / mode | what it does | passes when | Done when (guide) |
|---|---|---|---|---|
| `l1-creates-draft` | 1 webhook | one delivery | 2xx; the post has the title, the text of the html and the excerpt of the delivery, an image, and is not published | An editor's "Send to CMS" makes a draft post with `title`, `html`, `excerpt` and `featured_image`. |
| `l1-answer-fields` | 1 webhook | one delivery | the answer has `cms_post_id` (text), `status` and an `http(s)` `edit_url` | Your answer carries `cms_post_id`, `status` and `edit_url`, so the editor gets an "Edit in CMS" link. |
| `l1-bad-signature` | 1 webhook | a wrong signature | `401`, no post | A request whose signature does not verify, or whose `webhook-timestamp` is more than 5 minutes off, gets `401` and changes nothing. |
| `l1-clock-skew` | 1 webhook | `webhook-timestamp` 301 s old | `401`, no post | (same) |
| `l1-duplicate-attempt` | 1 webhook | attempts 1 and 2 of one send | one post | A repeated attempt with the same `webhook-id` makes no second draft, and a new send of the same `article_id` updates the post you made the first time. |
| `l1-resend-updates` | 1 webhook | a new send with a new title | the same post, new title | (same) |
| `l1-older-send-ignored` | 1 webhook | a newer send, then an older one | the newer title stays | An attempt of an older send that arrives after a newer one does not overwrite the post. |
| `l1-overlapping-attempts` | 1 webhook | two attempts of one send at once | one post | Keep `article_id` unique in your database and lock the row while you write, or you get two posts. |
| `l1-unknown-fields` | 1 webhook | an unknown field and an unknown link `kind` | 2xx, post made | Fields you do not know are ignored, not rejected; … |
| `l1-non-ascii` | 1 webhook | title `Zażółć gęślą jaźń — „test”` | the title comes back identical | (as `l1-creates-draft`) |
| `l1-image-host` | 1 webhook | the image on `localhost`, outside `image_hosts` | the mock saw no download (also passes for a CMS that never downloads images) | Download images only from these hosts and refuse any other address. |
| `read-delivers-result` | 1 read | a send, `--poll-cmd` | `POST /result` with the send's `delivery_id`; post made | The body (`ArticleResultReport`) is what your webhook would answer with, plus `delivery_id`: … |
| `read-superseded-409` | 1 read | a newer send right after your fetch, `--poll-cmd` twice | the old send's result got `409`, the last accepted result is for the newer send | With it the result closes exactly that send; if a newer send of the article replaced it you get `409` … |
| `read-cursor-expired` | 1 read | `410` on your next cursor, `--poll-cmd` | you listed `/articles/awaiting` and reported the waiting send | List the sends still waiting with `GET /v3/cms/articles/awaiting` … |
| `l2-reports-url` | 2 any | a delivery, `--publish-cmd` | the reported address equals the post's `permalink` | Every post made from a delivered article is reported once it is public, … |
| `l2-repeat-is-harmless` | 2 any | `--publish-cmd` twice | both succeed, the address is unchanged | Reporting the same post again does no harm, … |
| `l2-social-flag` | 2 any, with `--social-flag` | as `l2-reports-url` | every report carries `social_queue_exclude` | Once your CMS has the setting, send the field every time, also as `false`; … |
| `l3-placeholder-unwrapped` | 3 any | a placeholder link to an article you do not have, published | the link is gone, its text stays | Placeholders are replaced with your addresses, or the link text is left without a link, … |
| `l3-placeholder-resolved-later` | 3 any | target delivered and published, then a placeholder link to it | the html links to the target's `permalink` | (same) |
| `l3-backlinks-rules` | 3 any | B with `backlink_sources=[A]`, then without the key, then `[]` | A's `read_more`: `[B]`, `[B]`, `[]` | The "read more" box follows `backlink_sources`, including the missing-key and empty-list rules. |
| `l3-seo-author-language` | 3 any | the sample's SEO, author and language | stored as sent; author not empty | SEO fields, author and language are stored on the post. |
| `l3-ai-label` | 3 any | a delivery with `ai_provenance`, published | `ai_provenance_jws` equals the delivery's `jws` | The AI label is in the `<head>` of every public page made from a delivery whose `ai_provenance` is not `null`. |

In read mode the webhook-only `l1-*` scenarios are skipped and the report says so; levels 2 and
3 then send through the mock and `--poll-cmd`.

**Your clock.** `check` cannot see your server's clock. A receiver more than 5 minutes off
answers `401` to real deliveries and loses articles: keep it in sync.

## Limits of 1.0

- Level 4 (media library, held batches, resync, backfill) is not covered: those routes answer
  `501` and `--levels 4` is a usage error. It comes in tdkit 1.1. Build level 4 from the guide.
- The mock does not retry a delivery on its own; scenarios send each attempt explicitly.
- No rate limit (`429`), no frozen organization (`project_deactivated`).

## How close the mock is to production

- **Signatures** are checked against the signature vectors of the tag
  (`examples/vectors/webhook-signature.json`), which Tribune Desk's own code is tested on too.
- **Shapes** come from the tag's OpenAPI document: request bodies are validated with its schemas.
- **Behaviour** (cursor, `awaiting`, `409`, `410`) is written by hand from the guide.
- This repository's CI runs `tdkit check --levels 1,2` on the official Python examples of the
  tag (`examples/python`); both must agree with the guide.

If the mock and production disagree, please open an issue.

## Development

```bash
uv sync
uv run ruff check . && uv run ruff format --check . && uv run pyright
uv run pytest -q
```

`ci/example_harness.py` wraps the official examples for the CI job `examples`.

## License

MIT
