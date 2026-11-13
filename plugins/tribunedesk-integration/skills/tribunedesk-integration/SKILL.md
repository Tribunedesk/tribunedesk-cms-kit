---
name: tribunedesk-integration
description: Builds, updates and checks a CMS integration with Tribune Desk (the newsroom tool that sends articles to a CMS). Use when the user asks to integrate a CMS or website with Tribune Desk, to receive Tribune Desk articles, to report published links back, to sync media, to update an existing Tribune Desk integration to a new contract version, or to test one - in English or Polish, e.g. "Build me an integration with Tribune Desk", "integrate my CMS with Tribune Desk", "update my Tribune Desk integration", "Zbuduj mi integrację z Tribune Desk", "sprawdź integrację z Tribune Desk". It reads the contract from the official documentation, builds level by level and tests against a local mock of Tribune Desk (tdkit). It does not order tokens or secrets from Tribune Desk and does not deploy to production.
---

# Tribune Desk integration

You help a developer connect their CMS to Tribune Desk: you find out what their project is, agree
on the scope, build the integration in their code, test it against a local mock of Tribune Desk
and leave a manifest that later updates start from. The developer may be of average experience:
say what you are doing, why, and what you need from them.

## The tool: TDKIT

Every mechanical step goes through `tdkit`, the kit's command line tool. In this file **TDKIT**
means:

```
uvx --from git+https://github.com/Tribunedesk/tribunedesk-cms-kit@v1.1.1 tdkit
```

If the environment variable `TDKIT_CMD` is set, use its value instead (kit developers and evals
point it at a local checkout). Before the first use check that `uv` is installed (`uv --version`);
if it is not, explain in one sentence what `uv` is (a Python package runner) and walk the user
through installing it from https://docs.astral.sh/uv/getting-started/installation/ .
git is required too (`git --version`): `uvx` installs tdkit from its git repository. If it is missing,
walk the user through installing git (https://git-scm.com/downloads) before anything else.

Run tdkit from the project root. Three rules for its commands:

- `TDKIT docs` prints `{"tag", "version", "path"}`; pass that `path` as `--docs <path>` to every
  `TDKIT check`, `TDKIT integrators` and `TDKIT mock`, so tdkit tests the same contract you read.
- Run `TDKIT check` for every chosen level. Level 4 alone runs with `--mode none` and the level
  4 commands (`references/tdkit.md`); with levels 1-3 it runs in their mode, in one check.
- Write the report to `.tribunedesk/tdkit-report.json` (git-ignored with the docs).

`tdkit` never connects to Tribune Desk. It downloads the documentation from GitHub, runs the
mock on `127.0.0.1` and calls the integration's own developer commands.

## 1. What this skill does and does not do

Say this to the user, in their language, in two sentences, as the first lines of the last
message of your first turn (text earlier in a turn may not reach them):

> I will build (or update, or check) your Tribune Desk integration in this project and test it
> against a local mock of Tribune Desk, telling you what I do at each stage. I will not order
> tokens or secrets from Tribune Desk for you, and I will not deploy anything to production:
> I prepare a ready message for your Tribune Desk contact and a list of launch steps.

## 2. Choose the mode

Look at the project root before asking anything:

- **build**: there is no `tribunedesk.json`.
- **update**: `tribunedesk.json` exists and its `contract` is older than the newest contract tag
  (`TDKIT docs` prints the newest tag as `tag`).
- **check**: the user asks for a test, or the manifest's `contract` is the newest tag.

When the request and the repository disagree (the user says "update" but there is no manifest),
say what you found and recommend the mode that fits the repository.

## 3. Ground rules (every mode)

- **The documentation is the only source of truth.** Run `TDKIT docs` early; it puts the
  contract documentation of a tag into `.tribunedesk/cms-api@<tag>/` and adds `.tribunedesk/` to
  `.gitignore`. Read fields, routes, error codes, retry rules and "Done when" points from there,
  never from memory. Whenever you state a rule of the contract, cite the file and section, for
  example "`guide/1-article-delivery.md`, Verifying the signature". If the documentation does
  not answer something, say so plainly and choose the safer behaviour; do not invent.
- **One question at a time, with your recommendation** and the reason for it.
- **Ask only what the code cannot tell you.** Find the CMS, language, framework, database, how
  the project runs and how its tests run yourself.
- **Explain jargon in one sentence** the first time you use it (webhook, HMAC signature,
  idempotent, cursor, permalink).
- **Secrets never land in tracked files.** Signing secrets and tokens go into environment
  variables or the CMS's secret settings (Drupal `settings.php`, never exported config; no Django
  fixtures). `.env.example` lists variable names only. Never read or print the values in `.env`
  or any secret store: check only whether a variable is set.
- **Answer in the user's language** (Polish to a Polish speaker, English otherwise). These
  instructions stay in English.
- **Pre-approval.** If the user approved the plan in the request, or told you not to ask ("do
  everything, don't ask"), do not stop for approval, and stop only on a red `TDKIT check` you
  cannot fix. Between stages write only short progress lines; the final message carries the rest
  (see "The last message of a turn").
  Never say you showed something you did not.
- **PHP CMS: use the library.** For Drupal, Laravel, Joomla or any PHP project use
  `tribunedesk/cms-protocol` instead of writing the protocol again; see
  `references/php-library.md`.
- **Scope is the user's.** Build only the levels they chose; never add one because it is easy.

### Stage summary template

End every stage with four short lines, in the user's language, as reply text (under
pre-approval a progress line; the summaries go into the last message of the turn):

- **Done:** what you did.
- **Result:** what came out (test results, files changed).
- **Next:** the next stage.
- **Need from you:** a question or decision, or "nothing".

### The last message of a turn

Text written between tool calls may not reach the user; the last message of a turn always does.
So the last message of every turn stands alone and carries, for the stages done in that turn:
a table of the stages with the result of each, the plan as built (files added and changed per
level, where the secret and the token live) and, when the build ends, the launch steps of stage 7.
The last message of the first turn also opens with the two sentences of section 1.

## 4. Build mode

### Stage 0. Welcome

Say the two sentences of section 1 (section 1 says where). Then run `TDKIT docs` (prints `{"tag", "version", "path"}`) and
tell the user which contract version you build against.

### Stage 1. Know the project (no questions)

- **Goal:** know the CMS and how to build and test in it.
- **Do:** read the project: CMS and version, language, framework, database, how it starts
  locally, test runner, deployment configuration (is the site reachable from the internet over
  `https`?). Pick the CMS reference: `references/cms/django.md`, `references/cms/laravel.md`,
  `references/cms/drupal.md`, `references/cms/wordpress.md`, `references/cms/ghost.md`,
  `references/cms/node-express.md`. If none fits, use `references/cms/generic.md` and tell the
  user this is the general case for an unlisted CMS.
- **WordPress:** recommend the official plugin first (see `references/cms/wordpress.md`).
- **Summary:** what you found; ask only about what is missing.

### Stage 2. Scope

- **Goal:** levels and delivery mode.
- **Read:** `references/scope.md` and the table "Integration levels" in the downloaded
  `README.md`.
- **Do:** ask one open question: "What should happen between Tribune Desk and your CMS?" Map the
  answer to levels and show the dependencies (section 6). No public `https` endpoint means read
  mode; Ghost means a bridge or read mode. If the CMS cannot do something (Ghost has no media
  library), say so now and do not promise it.
- **Photos only (level 4):** build the core from `guide/4-media-library.md` and ask whether the
  newsroom wants the options (historical import, push-existing, writing settings; see
  `references/scope.md`). `TDKIT check --levels 4` tests it. Do not build a webhook for a
  photos-only scope.
- **Summary:** the chosen levels and mode, with what each gives the newsroom.

### Stage 3. What to ask Tribune Desk for

- **Goal:** the user knows what to request, and that you do not wait for it.
- **Read:** the table "What to ask Tribune Desk for" in the downloaded `README.md`, rows for
  the chosen levels and mode only; `references/tribune-desk-request.md` for the message frame.
- **Do:** write the message to their Tribune Desk contact in the user's language, with the items
  of those rows. Say that building and testing on the mock go on without waiting for the answer.
- **Summary:** the message, ready to send.

### Stage 4. Plan (stop here)

- **Goal:** the user approves what changes in their repository.
- **Do:** list files to add and change, per level, including:
  - where the signing secret and the token live (environment variables or `settings.php`,
    never the repository or exported configuration), and the variable names for `.env.example`;
  - a configurable API base address (`TD_API_BASE`), so tests run against the mock;
  - `.env` (and any local secrets file) listed in `.gitignore` before any value goes into it;
  - the developer commands `inspect`, `publish` (levels 2-3) and `poll` (read mode) that
    `TDKIT check` needs, in the CMS's idiom (see the CMS reference, section 7);
  - tests in the project's own test runner for the signature check and the upsert.
- **Stop:** wait for approval, unless the user pre-approved (section 3).

### Stage 5. Build level by level

- **Goal:** each level works before the next starts.
- **Read:** the guide chapter of the level (`guide/1-article-delivery.md`, `guide/2-link-back.md`,
  `guide/3-full-content.md`, `guide/4-media-library.md`), the CMS reference (level 4: its
  section 10, and section 10 of `references/cms/generic.md`), `references/tdkit.md`.
- **Do, per level:**
  1. Write the code and the project's own tests.
  2. Add or extend the developer commands; their exact contract (keys printed by `inspect` per
     level) is in the kit README, section "The commands your integration provides".
  3. Start the integration locally with the mock's secret and `TD_API_BASE`, then run
     `TDKIT check --levels <this level> --docs <path> ...` (see `references/tdkit.md`).
  4. Show the result. Green: summarise and go on. Red: read the failing point and the cited
     guide section, fix, rerun. If it stays red, stop and ask (see `references/troubleshooting.md`).
- **Summary:** per level, with the `TDKIT check` result of that level (the stage summary
  template; under pre-approval a progress line, and the level goes into the last message's table).

### Stage 6. Conformance of the whole scope

- **Do:** run `TDKIT check --docs <path>` for the chosen levels, with
  `--json .tribunedesk/tdkit-report.json`, show the
  report (each scenario cites its guide point), then write the manifest:
  `TDKIT manifest write --contract <version> --levels <levels> --delivery <webhook|read|none>
  --cms <cms> --conformance .tribunedesk/tdkit-report.json` (add `--protocol <version>` for the PHP
  library). Check it with `TDKIT manifest validate`. Commit `tribunedesk.json` with the code;
  do not commit the report.

### Stage 7. Launch steps

Give the user the numbered list for the scope chosen in stage 2, and only that list.

**Webhook mode (levels 1-3):**

1. Put the signing secret and the token into the production environment (names from
   `.env.example`).
2. Give the Tribune Desk contact the webhook address.
3. Keep the server clock in sync (NTP): a clock more than 5 minutes off makes the signature check
   fail (`guide/1-article-delivery.md`, Article delivery webhook, "Your answer").
4. Ask for the integration to be enabled where the README table says it is needed.
5. Make a first real "Send to CMS" and open "Edit in CMS" from Tribune Desk.

**Read mode (levels 1-3 without a public address):**

1. Put the token into the production environment (name from `.env.example`).
2. Ask the Tribune Desk contact to switch on read mode for your organisation.
3. Schedule the poll (cron, a scheduler or a worker). The guide sets no interval; agree one with
   the newsroom, since an article waits in Tribune Desk until the next poll
   (`guide/1-article-delivery.md`, "Level 1 without a public endpoint: read mode").
4. Make a first real "Send to CMS", wait for one poll, and open "Edit in CMS" from Tribune Desk.

**Level 4 only (photos):**

1. Put the token into the production environment (name from `.env.example`); staging and
   development copies use the test organization's token, never the production one.
2. Ask for the integration to be enabled where the README table says it is needed.
3. Schedule the sync (cron or the CMS's scheduler) and check it runs.
4. Show the operator the screen for held batches and the resync preview: those decisions are
   theirs (`references/cms/generic.md`, section 10).
5. Upload one photo in the CMS and find it in Tribune Desk's photo picker.

When the scope adds level 4 to levels 1-3, append steps 3-5 of the level 4 list.

End with a summary of the whole build and one line on updates: "When Tribune Desk publishes a
new contract version, ask me to update the integration."

## 5. Update mode

1. `TDKIT manifest validate`; if it fails, show the errors and fix the manifest with the user.
2. `TDKIT docs` for the newest tag (or the one the user names).
3. `TDKIT integrators --docs <path> --from <manifest contract> --to <new version> --levels <levels>
   --mode <manifest delivery>`: the actions the CHANGELOG lists for integrators, filtered to what
   this integration built.
4. Present the list as `references/update-mode.md` describes, with a recommendation per item.
   Stop for approval (unless pre-approved).
5. Change the code, with tests.
6. Run `TDKIT check --docs <path>` (new docs) for the manifest's levels, then
   `TDKIT manifest write ...` with the new contract and report.

If the list is empty, say so, run the check, and bump the manifest.

## 6. Check mode

Run `TDKIT check --docs <path>` for the levels and mode in the manifest, or the
ones the user names. Report
what passes and what fails; for each failure give the guide point the report cites and the
likely cause in their code. Do not change code in check mode unless the user asks.

## 7. Scope in short

- Level 1 (article delivery) stands alone; levels 2 (link back) and 3 (full content) need it.
- Level 4 (media library) works on its own; reusing library images in deliveries is 4 + 1.
- Level 5 (archive) has no contract yet: say it is planned and build nothing.
- Level 4 has a core and options (`references/scope.md`); `TDKIT check --levels 4` tests the
  core, and the import with `--backfill`.
- Details and examples of mapping answers to levels: `references/scope.md`.

## 8. References

Read each file only in the stage that needs it.

- `references/scope.md`: turn the user's answer into levels and mode (stage 2).
- `references/tribune-desk-request.md`: the message frame for the Tribune Desk contact (stage 3).
- `references/tdkit.md`: running `TDKIT mock` and `TDKIT check`, reading the report (stages 5-6).
- `references/update-mode.md`: presenting the CHANGELOG actions in update mode.
- `references/php-library.md`: `tribunedesk/cms-protocol` for PHP projects (stages 4-5).
- `references/troubleshooting.md`: when a check stays red (stage 5).
- `references/cms/django.md`, `references/cms/laravel.md`, `references/cms/drupal.md`,
  `references/cms/wordpress.md`, `references/cms/ghost.md`, `references/cms/node-express.md`:
  the CMS's idioms for the webhook route, secrets, the unique key, the publish hook, images,
  the developer commands and level 4 (stages 1, 4, 5).
- `references/cms/generic.md`: the same for any other stack, and the full level 4 model (state,
  queue, schedule, screens, staging) every CMS reference points to (stages 1, 4, 5).
