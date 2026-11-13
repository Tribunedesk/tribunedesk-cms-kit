# Working with tdkit

`TDKIT` is defined in `SKILL.md`. The full reference of `tdkit` is the kit's README
(https://github.com/Tribunedesk/tribunedesk-cms-kit#readme); this file says how to use it while
building. Do not copy the README into the user's project.

## What the integration needs to be testable

1. **A configurable API base address.** The code reads it from an environment variable
   (recommended name `TD_API_BASE`) that defaults to the production address; tests point it at
   the mock, `http://127.0.0.1:<port>`.
2. **The signing secret from configuration**, so it can be the mock's secret locally. The mock's
   secret is `whsec_dGRraXQtbW9jay1zaWduaW5nLXNlY3JldC0wMDAwMDA=` (`TDKIT mock` prints it too);
   `TDKIT check` signs with it unless you pass `--secret`. It is a public test value, safe to put
   into a local `.env`, never into production.
3. **Three developer commands** in the CMS's idiom (CMS reference, section 7). Their exact
   contract, including the JSON keys `inspect` prints per level, is in the kit README, section
   "The commands your integration provides". Read it there; they are:
   - `inspect <article_id>`: prints the post made from that article as JSON, or `null`;
   - `publish <article_id>`: publishes that post the way an editor would (levels 2-3);
   - `poll`: runs one poll of the read mode client (read mode).
   - Level 4 adds `sync`, `media-inspect`, `media-add`, `media-edit`, `media-delete` and `reset`
     (CMS reference, section 10; the README has their contract).

   These are development tools. Keep them out of production menus, but they may ship with the
   code (a management command, an artisan command, a drush command).

## TDKIT check

Start the integration first (its web server, with the mock secret and `TD_API_BASE` pointing at
the mock's port), then:

```
TDKIT check --levels 1,2 --mode webhook \
  --webhook http://127.0.0.1:8000/td/webhook \
  --inspect-cmd "python manage.py td_inspect {article_id}" \
  --publish-cmd "python manage.py td_publish {article_id}" \
  --docs <path> \
  --json .tribunedesk/tdkit-report.json
```

- `--docs <path>`: the `path` that `TDKIT docs` printed, the contract of the tag you build against.
- `--mode read` with `--poll-cmd "…"` instead of `--webhook`.
- `--port` changes the mock's port (default 8787); the integration's `TD_API_BASE` must match.
  `check` also sets `TD_API_BASE` and `TD_CMS_TOKEN` in the environment of the three commands.
- `--secret` when the integration verifies with its own secret instead of the mock's; the
  report never shows the value. Never pass a production secret.
- `--social-flag` when the CMS has a "keep this post off Facebook" setting.
- Level 4: `--levels 4 --mode none` (level 4 alone) with `--sync-cmd`, `--media-inspect-cmd`,
  `--media-add-cmd`, `--media-edit-cmd`, `--media-delete-cmd` and `--reset-cmd`; add
  `--backfill` when the integration answers import requests. With levels 1-3 as well, run one
  check with all levels in their mode. The scenario `l4-held-not-resent` proves the sync does not
  decide held batches; the operator's screen itself you check by hand.

Exit code 0 means every scenario that ran passed, 1 means one failed, 2 means a usage error.

## Reading the report

Each line is `PASS`, `FAIL` or `SKIP` with a short detail. A `FAIL` also quotes the guide point
("Done when") and names the guide file and section. To fix one:

1. Read the cited section in `.tribunedesk/cms-api@<tag>/guide/…`.
2. Read the detail: it says what the integration did (status code, what `inspect` printed).
3. Fix the code, rerun only that level.

`SKIP` lines are expected for another mode (read mode scenarios in webhook mode) and for
`l2-social-flag` without `--social-flag`.

## TDKIT mock, for manual work

`TDKIT mock [--port 8787] [--read-mode] [--webhook URL]` runs the mock in the foreground and
prints the API address, the token (`tdcms_mock`) and the signing secret. `POST /_tdkit/send` on
the mock makes a "Send to CMS" of a sample article (read mode: it waits for the poll; otherwise
it is delivered to `--webhook`). Use it to watch one delivery while debugging; use `check` to
prove the integration.

## When the port is taken

`check` and `mock` fail with a usage error when the port is in use (often a previous mock still
running). Stop the old process or pass another `--port` and update `TD_API_BASE`.
