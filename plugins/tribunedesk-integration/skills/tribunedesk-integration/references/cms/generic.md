# Any other CMS or stack (the general case)

Tell the user there is no specific guide for their CMS and that you follow the general steps,
adapted to what you found in the code. Contract rules come from the downloaded guide. For a PHP
project use `tribunedesk/cms-protocol` (`references/php-library.md`).

## 1. Raw body and the webhook route

- One POST route, outside any CSRF protection and any automatic JSON/body parsing.
- Read the raw bytes, verify the signature on them, only then parse JSON.
- Prefer a Standard Webhooks library for the language (https://www.standardwebhooks.com/); else
  follow `guide/1-article-delivery.md`, Verifying the signature, step by step.
- The exact registered address, no redirects (trailing slash, `http`→`https`, locale prefix).

## 2. Secret and token

Environment variables or the platform's secret store: `TD_WEBHOOK_SECRET`, `TD_CMS_TOKEN`,
`TD_API_BASE`. Never in the repository, in exported configuration or in database seeds;
`.env.example` with names only.

**Secrets without environment variables.** If the platform has neither environment variables nor a
secret store, keep the signing secret and the token in a file outside the repository and outside
the web root, readable by the web server's user only, and put its path in a configuration value.
Never a constant in code, a seed, a fixture or exported configuration.

## 3. Unique key and lock

- A table keyed by `article_id` with a unique constraint, plus `last_sent_at` and the delivery id.
- Read-compare-write inside a transaction with a row lock (or an atomic conditional upsert), so
  two overlapping attempts of one send cannot create two posts or let an older send win.

## 4. Publish hook and link back

Find where the CMS makes a post public (an event, a hook, the publish action). From there queue a
retrying job that sends the link back. For posts published at once in the delivery, answer with
the permalink instead (guide 2).

**Scheduled publication.** A post with a publish date in the future is not public yet: answer the
delivery without `permalink`. Report the address with `POST /v3/cms/articles/published` when the
post goes public, from the scheduler's own event or the first job after that time, because guide 2
asks for the report once the post is public. Take the address from the post as it is then, not
from the scheduled time.

## 5. Edit URL

An absolute `http(s)` address of the post's editor, built from the post id and the site's base URL
without checking the current user (there is none during a delivery).

**No logged-in user.** A delivery and the CLI commands run without an editor's session. So the
absolute addresses they build (`edit_url`, `permalink`) come from `TD_SITE_URL`, the public address
of the site, read from the environment like the other `TD_` names (section 2). The post author comes
from the `author` field of the delivery (guide 1, The fields of the request), and the body goes
through the text filter your CMS applies to editor content, chosen for the system because there is
no user to take it from; check that it keeps the elements listed in guide 1, "The HTML body".

## 6. Images

Download only from the allowed hosts (guide 1, Where images come from), in the background after
answering, with a timeout and a size limit.

Testing with `tdkit`: the mock serves images over https with a test certificate. Trust its CA, the file `TDKIT check` prints as `TD_CA_BUNDLE`, in the test environment only, through your HTTP client's CA option: Python `cafile=`/`REQUESTS_CA_BUNDLE`, PHP `CURLOPT_CAINFO` or Guzzle `verify`, Node `NODE_EXTRA_CA_CERTS`. Never in production: there the system's CAs stay.

## 7. Developer commands

Three commands runnable without a shell (a script, a CLI entry point):
`<cli> inspect <article_id>`, `<cli> publish <article_id>`, `<cli> poll`. Their output contract is
in the kit README, "The commands your integration provides".

`publish` sends the link back before it exits, so `check` finds it: it reads the report right after
the command returns. A retry queue may still handle a failed send later.

## 8. Running the project's tests

Use the project's own test runner. Add tests for the signature check (with the contract's
signature vectors, `examples/vectors/webhook-signature.json` in the downloaded docs), for two
attempts of one send, and for an older send after a newer one.

**No tests in the project.** If the project has no test runner, do not start one on your own: tell
the user and ask before adding a runner or a dependency, since that choice is theirs. The signature
check can still be tested against the contract's vectors (`examples/vectors/webhook-signature.json`)
with a small script the user can run.

## 9. Pitfalls

- Body parsing middleware that runs before your route.
- Clock not synchronised (5-minute tolerance).
- Image downloads inside the request (30-second answer limit).
- Answering 4xx for anything but a bad signature: a 4xx ends the send for good (guide 1, Your
  answer).

## 10. Level 4 (media library)

Build it from `guide/4-media-library.md`; this section only says where things live in a CMS.
The working example is the WordPress plugin: `src/WordPress/CmsSync.php` at
https://github.com/Tribunedesk/tribunedesk-wordpress/blob/v2.2.3/src/WordPress/CmsSync.php (the
cycle), with `MediaMetaSync.php` (the queue of edits), `CmsResync.php` (resync),
`CmsDeletions.php`, `CmsBackfill.php` and `CmsSettingsScreen.php` (the operator's screen) next
to it. Read it for the logic; do not copy WordPress code into another CMS.

**Core and options.** Core: the sync cycle, taking files (`/link`), sending your new files,
field edits and deletions, conflicts, `410` → resync, and the screen for held batches. Optional,
only when the user wants them: historical import (backfill), sending older files
(push-existing) and writing the settings from the CMS (`references/scope.md`).

**State to store.**

- Per organization: the cursor (stored only after the changes it covers are applied), a counter
  of attempts for the change you are stuck on, a "resync needed" flag with the open preview's
  id, and a lock so only one cycle runs at a time.
- Per file: the Tribune Desk `asset_id`, the version of every synced field, the values from the
  feed you set aside because the field was edited locally and not sent yet (with the
  `held_batch_id` when the server held your write), and the result of sending the file.
- A queue of local edits: file, field, and `changed_at` = the time of the last edit by a person.
  Writes coming from the feed must not enter it (switch the tracking off while you apply them).
- A queue of deletions (`cms_media_id`, `deleted_at`).

**Field mapping.** Decide with the user which CMS field is `title`, `alt`, `caption` and
`description` (guide 4, Conflicts and base_version), and leave the rest alone. Values are plain
text: strip markup before sending.

**Schedule.** Pull every few minutes and send your own edits about a minute after an edit (guide
4, The sync cycle, step 6), from the CMS's scheduler or cron, never inside a web request. One
cycle at a time: take the lock first. Honour `retry_after` on `429` and `503`.

**Screens for a person.** Two decisions belong to an operator, never to the sync: held batches
(list with `GET /held`, decide `send` or `discard`) and the resync preview (direction, number of
differences, confirm). After `410` the sync sends the unsent edits, starts a `td_to_cms` preview
and stops; the operator confirms it (or starts `cms_to_td` instead) and the cycle resumes from
the returned cursor (guide 4, Cursors and expiry).

**Staging.** Tribune Desk keeps one feed position per organization, so a staging or local copy
must never use the production organization's token: ask Tribune Desk for a test organization.

**Developer commands for `TDKIT check --levels 4`** (kit README, "The commands your integration
provides"): `sync`, `media-inspect <cms_media_id>`, `media-add <file>`,
`media-edit <cms_media_id> <field> <value>`, `media-delete <cms_media_id>`, and `reset` (clears
the level 4 state for a rerun). Run them as the CMS's own CLI.
