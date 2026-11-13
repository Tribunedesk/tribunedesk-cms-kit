# tribunedesk-cms-kit

Tools for building a CMS integration with [Tribune Desk](https://tribunedesk.com) and checking
that it works, before you have any access to Tribune Desk itself.

- **`tdkit mock`** runs a local mock of the Tribune Desk CMS API on `127.0.0.1`: the
  `/v3/cms/*` routes of levels 1 to 4 and read mode, tokens and scopes, signed
  `article.delivered` webhooks with retries, and the media library (feed, conflicts, held
  batches, resync, historical import).
- **`tdkit check`** runs conformance scenarios against your integration and reports, point by
  point, which parts of the guide's "Done when" it meets. The exit code tells a script or CI
  whether everything passed.

The contract itself (the guide, the OpenAPI document, examples) lives in
[`Tribunedesk/tribunedesk-cms-api`](https://github.com/Tribunedesk/tribunedesk-cms-api). This
kit reads it from a tag of that repository and never copies it. The **Claude Code plugin**
`tribunedesk-integration` builds an integration with these tools (below).

`tdkit` never connects to `api.tribunedesk.com`. The only network host it talks to is GitHub,
to fetch the contract documentation, and not even that when you give it a local copy.

## Claude Code plugin

This repository is also a Claude Code plugin marketplace. In Claude Code:

```
/plugin marketplace add Tribunedesk/tribunedesk-cms-kit
/plugin install tribunedesk-integration@tribunedesk
```

Then, in your CMS project, ask for example:

- "Build me an integration with Tribune Desk: articles and links back."
- "Our CMS is not reachable from the internet; integrate it with Tribune Desk."
- "Update my Tribune Desk integration to the newest contract."
- "Check my Tribune Desk integration."

**What it does.** It looks at your project, asks what should happen between Tribune Desk and your
CMS (one question at a time), tells you what to request from your Tribune Desk contact (a ready
message), proposes a plan and waits for your approval, then builds the integration level by
level in your code and tests every level with `tdkit check`. At the end it writes
`tribunedesk.json` (contract version, levels, conformance result), which later updates start
from. For PHP projects it uses [`tribunedesk/cms-protocol`](https://github.com/Tribunedesk/tribunedesk-cms-php).
It reads the contract from the documentation of a tag, downloaded into `.tribunedesk/` of your
project (git-ignored), and cites it.

**What it does not do.** It does not order tokens or secrets from Tribune Desk, does not deploy to
production, and never writes secret values into tracked files or reads your `.env` values.

**Needs** [uv](https://docs.astral.sh/uv/) and git (`uvx` installs `tdkit` from this git
repository). **Privacy:** `tdkit` never connects to Tribune Desk; the
mock runs on `127.0.0.1`.

### Po polsku

W Claude Code:

```
/plugin marketplace add Tribunedesk/tribunedesk-cms-kit
/plugin install tribunedesk-integration@tribunedesk
```

Potem w projekcie CMS-a napisz na przykład „Zbuduj mi integrację z Tribune Desk: artykuły i linki
zwrotne”, „Zaktualizuj integrację z Tribune Desk” albo „Sprawdź integrację z Tribune Desk”.
Skill rozpozna projekt, zapyta o zakres, przygotuje wiadomość do kontaktu w Tribune Desk,
zbuduje integrację poziom po poziomie i przetestuje ją lokalną atrapą (`tdkit check`). Nie
zamawia tokenów, nie wdraża na produkcję i nie wpisuje sekretów do repozytorium. Wymaga `uv`
i gita.

## Run it

You need [uv](https://docs.astral.sh/uv/) and Python 3.12 or newer. No installation:

```bash
uvx --from git+https://github.com/Tribunedesk/tribunedesk-cms-kit@v1.1.0 tdkit --help
```

### Which contract

`tdkit` supports every patch of contract 3.4 (`3.4.0-draft`, `3.4.1-draft`, `3.4.2-draft` and later patches). It takes the documentation from,
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
           [--token-scopes articles:read,articles:write | --tokens tokens.json]
           [--webhook URL] [--retry-scale 1] [--disabled] [--media-hosts cms.example]
```

It prints what your CMS needs and stays in the foreground (Ctrl+C stops it):

- the API at `http://127.0.0.1:8787/v3/cms/`; set `TD_API_BASE=http://127.0.0.1:8787` in your
  CMS;
- the token `tdcms_mock`, with every scope unless `--token-scopes` narrows it, or the tokens
  of `--tokens FILE`:

  ```json
  {"tokens": [{"token": "tdcms_reader", "scopes": ["media:read", "settings:read"]},
              {"token": "tdcms_writer", "scopes": ["media:read", "media:write"]}]}
  ```

- the signing secret `whsec_dGRraXQtbW9jay1zaWduaW5nLXNlY3JldC0wMDAwMDA=`.

The token and the secret are public test values: they only work against the mock.

What the mock does:

| Route | Behaviour |
|---|---|
| `GET /v3/cms/status` | `contract_version` of the tag, the token's `scopes`, `state`, `image_hosts` (`["127.0.0.1"]`) |
| `GET /v3/cms/changes` | `article_sent` changes in read mode, only for `articles:read`; level 4 changes (`new_asset`, `fields`, `settings`, `deleted`, `restored`), only for `media:read`; opaque cursors; `409 state_conflict` while the integration is disabled; `410 cursor_expired` after a re-enable or `/_tdkit/expire-cursors`, after which the earlier feed is gone, which is stricter than the guide documents; `422` for a cursor from an earlier run of the mock |
| `GET /v3/cms/articles/awaiting` | the sends still waiting for a result, oldest first |
| `GET /v3/cms/articles/{article_id}` | the sent article with its `X-Delivery-Id`; `404` when it was never sent |
| `POST /v3/cms/articles/{article_id}/result` | closes the send named by `delivery_id`; `409 state_conflict` for a replaced send or a never-sent article; unknown fields come back in `ignored_fields` |
| `POST /v3/cms/articles/published` | `ok`, `not_found` or `invalid_url` per item |
| `GET /v3/cms/openapi.json` | the tag's OpenAPI document, no token |
| `GET /files/<name>` | a small JPEG; the mock records every download |
| `POST /v3/cms/media`, `/media/fields`, `/media/deletions`, `/media/{asset_id}/link`, `/media/push-existing` | as guide 4: per-item results, the six steps of "Conflicts and base_version", the mass-change threshold (60-minute run, `held`), `422` for NUL and for a time without a zone |
| `POST /v3/cms/resync`, `GET /v3/cms/held`, `POST /v3/cms/held/{id}/decision` | preview pages and confirmation, `held` over the threshold, the cursor from the start of the preview |
| `GET`/`PUT /v3/cms/settings` | variants, `custom`, `option_locked`; every change enters the feed as `kind="settings"` |
| `GET /v3/cms/backfill/requests`, `POST …/pages` | requests with filters, pages up to 1000, `is_last`, `max_files`, paused requests |
| `GET /files/<asset_id>.png` | the file of a `new_asset` change (a PNG of its size) |

Order of checks, as in the contract: a malformed JSON body `422`, then `401` (token), `403`
(scope), `422` (the body against the schema of the tag's OpenAPI document, literally, with its
`additionalProperties`), then `409`. Errors have the body `{"code", "message"}`.

**Retries.** With `--webhook`, a send whose attempt fails with a network error, a timeout,
`5xx`, `408`, `425` or `429` is tried again on the guide's schedule (2, 10, 30, 120, 360 and 840
minutes), shortened to seconds by `--retry-scale` (default `1`: a second for a minute; `0`: no
retries). Every attempt keeps the `webhook-id` and is signed anew; a newer send of the article
cancels the retries of an older one.

**Switching the integration.** `--disabled` starts with the integration disabled;
`POST /_tdkit/integration {"enabled": true|false}` switches it. Enabling it again expires the
cursors from before the break (`410`), as in production.

**Level 4 controls** (no token, the mock's own routes): `POST /_tdkit/media` (a new file in
Tribune Desk; body `{fields?, width?, height?}`, answers `asset_id`),
`POST /_tdkit/media/<asset_id>/fields` (`{field, value}`: an editor's edit),
`POST /_tdkit/media/<asset_id>/trash` (`{trashed}`), `POST /_tdkit/settings` (`{option: value}`),
`POST /_tdkit/import` (pairs the files accepted by `POST /media`), `POST /_tdkit/backfill`
(`{filters?}`: an export request) and `POST /_tdkit/expire-cursors`. File URLs your CMS sends
(`POST /media`, `/link`) may be on `127.0.0.1` or `localhost`, any port, `http` or `https`, plus
the hosts of `--media-hosts`; the mock does not download them.

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
tdkit check --levels 4 --mode none --sync-cmd "…" --media-inspect-cmd "…{cms_media_id}…"
            --media-add-cmd "…{file}…" --media-edit-cmd "…{cms_media_id} {field} {value}…"
            --media-delete-cmd "…{cms_media_id}…" [--reset-cmd "…"] [--backfill]
            [--media-fields alt,caption] [--media-hosts cms.example]
```

`--mode none` is for level 4 alone; with `--levels 1,4` the level 4 scenarios run in webhook or
read mode too.

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
arguments (on Windows only double quotes group, so `C:\Users\O'Brien\...` needs no quoting),
the program is looked up on `PATH` (so `drush.bat` or `npx.cmd` work on Windows), and it runs
without a shell, with a 60-second limit. A non-zero exit code fails the scenario.

| Option | Needed for | What the command does |
|---|---|---|
| `--inspect-cmd` | always | prints, as JSON on stdout (UTF-8), the post your CMS made from `{article_id}`, or `null` when there is none |
| `--publish-cmd` | levels 2 and 3 | publishes the post made from `{article_id}`, the way an editor would; your CMS then reports its address (link back) |
| `--poll-cmd` | read mode | runs one poll of your read mode client: `GET /changes`, then fetch, apply and `POST /result` for each sent article |
| `--sync-cmd` | level 4 | runs one whole sync cycle of the media library: `GET /changes` until `has_more` is false, apply, store the cursor, send your new files, field edits and deletions, answer import requests (with `--backfill`); it finishes sending before it exits |
| `--media-inspect-cmd` | level 4 | prints the file `{cms_media_id}` of your library as JSON (below), or `null` |
| `--media-add-cmd` | level 4 | adds the image `{file}` (a PNG `check` writes) to your library as an editor would, and prints `{"cms_media_id": "…"}` |
| `--media-edit-cmd` | level 4 | sets `{field}` of `{cms_media_id}` to `{value}` as an editor would (`{value}` is one argument, spaces included) |
| `--media-delete-cmd` | level 4 | deletes `{cms_media_id}` as an editor would |
| `--reset-cmd` | level 4, optional | clears your level 4 state (cursor, versions, queues, pairs) before the scenarios; without it a rerun polls with a cursor of the previous mock and the first scenario fails with a hint |

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

**What `--media-inspect-cmd` prints.** `cms_media_id`; `asset_id` (the Tribune Desk file it is
paired with, or `null`); `sha256` of the stored file; `fields`, an object of the fields your CMS
maps (`alt`, `caption`, `title`, `description`); `deleted_in_td`, the mark a `kind="deleted"`
change sets. Level 4 scenarios edit the first field of `--media-fields` (default `alt`).

### Exit codes and the report

`0` when every scenario that ran passed, `1` when one failed, `2` for a usage or configuration
error (for example `--levels 4` without `--sync-cmd`: `level 4 needs --sync-cmd`). The text report goes to
stdout; for a failed scenario it quotes the guide's point and names the guide file. `--json FILE`
also writes:

```json
{"tdkit": "1.1.0", "contract": "3.4.2-draft", "levels": [1, 2], "mode": "webhook",
 "results": [{"id": "l1-creates-draft", "level": 1, "done_when": "An editor's …",
              "guide": "guide/1-article-delivery.md#done-when", "passed": true, "detail": "…"}]}
```

`passed` is `null` for a skipped scenario (another mode, `l2-social-flag` without
`--social-flag`, `l4-backfill-answered` without `--backfill`), with the reason in `detail`.

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
| `l1-image-host` | 1 webhook | the image on a host outside `image_hosts`: `localhost`, or `127.0.0.1` when your webhook is on `localhost` (a receiver may trust its own host) | 2xx, and the mock saw no download (also passes for a CMS that never downloads images) | Download images only from these hosts and refuse any other address. |
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

| `l4-first-poll` | 4 | two syncs | every poll after the first sends the stored cursor | Your CMS polls `GET /v3/cms/changes` and stores the cursor only after applying the changes it returned. |
| `l4-new-asset-linked` | 4 | 101 field changes, then a new file in Tribune Desk; one sync | `/link` with your `cms_media_id`; the stored file has the same `sha256` and texts; every page was read | Call `POST /v3/cms/media/{asset_id}/link` with `cms_media_id` … |
| `l4-cursor-after-apply` | 4 | a new file whose download fails; sync; then it works; sync | not linked while it failed, linked after: the cursor stayed before it | (as `l4-first-poll`) |
| `l4-field-versions` | 4 | versions 2, 3, then an older 2, then 3 repeated with a new value | the older version skipped, the same version applied | Apply by version: skip a change only when its `version` is lower than yours, … |
| `l4-cms-new-file` | 4 | `--media-add-cmd`, an edit, the import pairs it | `POST /media` with `width`, `height`, `mime_type`; the edit made before the import arrives; `asset_id` learned; no other id for the file | New files, field changes and deletions on your side reach Tribune Desk, and a repeated request creates no duplicates. |
| `l4-cms-field-edit` | 4 | an edit in Tribune Desk, then in your CMS; two syncs | one write, with the `base_version` you held | (same) |
| `l4-cms-deletion` | 4 | `--media-delete-cmd` | `POST /media/deletions` with `deleted_at` | (same) |
| `l4-conflict-winning-value` | 4 | rule `td`, edits on both sides | `winning_value` adopted, the losing value not sent again | A field result `conflict` (in a `200` answer) is resolved by adopting `winning_value`, … |
| `l4-both-sides-edited` | 4 | a local edit, then a change of that field in the feed | the local edit is sent with the version you held, the feed's value is not applied over it | If a change from the feed touches a field you edited and have not sent yet, … |
| `l4-held-not-resent` | 4 | threshold 1, two edits | the `held` field is not sent again and no batch is decided by the sync (the operator's screen is yours to check) | Held batches are shown to a person who decides them. |
| `l4-settings-and-unknown-kinds` | 4 | `kind="settings"`, an unknown kind, a new file | `GET /settings` read again; the unknown kind skipped, the file linked | A `kind="settings"` change has no `asset_id` and no values: … |
| `l4-td-trash-mark` | 4 | a file trashed, then restored in Tribune Desk | `deleted_in_td` true, then false; the file stays | Do what suits your CMS, such as a hidden mark; … |
| `l4-backfill-answered` | 4, with `--backfill` | a request with candidates and one without | each got a page and is closed (`is_last`) | If you have no candidates, send one page with an empty `items` and `is_last` true: … |
| `l4-cursor-expired-resync` | 4 (runs last) | an unsent edit, then `410` | no poll from now; the edit sent, then a `td_to_cms` preview with `is_last`; not confirmed by the sync | An expired cursor (`410`) leads to a resync, not to a fresh start from now. |

In read mode the webhook-only `l1-*` scenarios are skipped and the report says so; levels 2 and
3 then send through the mock and `--poll-cmd`.

**Your clock.** `check` cannot see your server's clock. A receiver more than 5 minutes off
answers `401` to real deliveries and loses articles: keep it in sync.

## Limits of 1.1

- `check` sends each delivery attempt itself; the mock's retries are for `tdkit mock`.
- `push-existing` and `PUT /settings` work in the mock but have no scenario: both are an
  operator's action, not part of the sync cycle.
- The screens for held batches and the resync preview are a person's: `check` proves the sync
  never decides them, not how they look.
- No rate limit (`429`) and no frozen organization (`project_deactivated`).

## How close the mock is to production

- **Signatures** are checked against the signature vectors of the tag
  (`examples/vectors/webhook-signature.json`), which Tribune Desk's own code is tested on too.
- **Shapes** come from the tag's OpenAPI document: request bodies are validated with its schemas.
- **Behaviour** (cursor, `awaiting`, `409`, `410`, level 4: versions, conflicts, threshold,
  resync, import) is written by hand from the guide.
- **Level 4 file hosts** are relaxed: the mock accepts `http` and any port on `127.0.0.1` and
  `localhost` in `file_url` of `POST /media` and `/link` (production wants `https` on port 443
  on your organization's hosts), never downloads those URLs, and pairs files accepted by
  `POST /media` only when told (`/_tdkit/import`; `check` does it in `l4-cms-new-file`).
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

The plugin is validated in CI (job `plugin`) with `claude plugin validate --strict .` and
`claude plugin validate --strict plugins/tribunedesk-integration`; run both before a PR that
touches `.claude-plugin/` or `plugins/`. To try the skill with a local `tdkit` before a release,
set `TDKIT_CMD="uv run --project <this checkout> tdkit" (`--project`, not `--directory`: the command must run in the integration's folder)`.

## Evals

Six scenarios check the skill on real projects (`evals/scenarios/`): a Django blog with levels 1
and 2 in Polish, the same on Drupal 11 in English with the PHP library, a photos-only site, a
site on an intranet (read mode), an update from contract 3.2.0-draft and a Ghost(Pro) site. Run
one with `uv run python evals/run.py <scenario>`; it works on Windows, macOS and Linux and needs
Claude Code, uv and git (and PHP 8.3 with Composer for Drupal). See [`evals/README.md`](evals/README.md).

Last runs, 2026-11-12 (Claude Code 2.1.293, one run per scenario; later edits of the skill only
reconcile its wording):

| Scenario | Automatic checks | Review | Cost |
|---|---|---|---|
| `django-l12` | all pass: tdkit 13 passed, 0 failed | pass | 1.61 USD |
| `drupal-l12` | all pass: tdkit 13 passed, 0 failed, `tribunedesk/cms-protocol` | pass | 3.64 USD |
| `photos-only` | all pass: no webhook, no tdkit check, manifest level 4 (tdkit 1.0; 1.1 checks a green level 4 report, not run yet) | pass | 2.10 USD |
| `no-public-endpoint` | all pass: tdkit read mode 3 passed, 0 failed | pass | 1.66 USD |
| `update-3.2` | all pass: tdkit 13 passed, 0 failed, manifest 3.4.1-draft | pass | 1.08 USD |
| `ghost` | all pass: no code, bridge or read mode explained | pass | 0.30 USD |

The integrations of the Django and Drupal runs are in [`reference/`](reference/README.md).

## License

MIT
