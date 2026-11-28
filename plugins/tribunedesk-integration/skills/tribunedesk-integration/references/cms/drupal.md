# Drupal (10 / 11)

A custom module, e.g. `tribunedesk`, built on `tribunedesk/cms-protocol`
(`references/php-library.md`). Contract rules come from the downloaded guide.

Start from the reviewed reference in the kit repository: `reference/drupal`
(https://github.com/Tribunedesk/tribunedesk-cms-kit/tree/main/reference/drupal) is a Drupal module
with the webhook controller, a lock per article, the link-back queue, the Drush commands and kernel
tests. Read it before writing your own, and copy the order of the steps, not its names.

## 1. Raw body and the webhook route

- `tribunedesk.routing.yml`: a route `/td/webhook` with `methods: [POST]`,
  `requirements: _access: 'TRUE'` (the signature is the access check) and
  `options: no_cache: TRUE`.
- A controller reading `$request->getContent()` and verifying it with `WebhookSignature::verify`
  before `json_decode`. Do not use the core REST module or the serializer for this route.
- No CSRF token on a custom POST route without `_csrf_token`; do not add one.

## 2. Secret and token

- In `settings.php` (or `settings.local.php`), read from the environment:
  `$settings['tribunedesk'] = ['secret' => getenv('TD_WEBHOOK_SECRET'), 'token' =>
  getenv('TD_CMS_TOKEN'), 'api_base' => getenv('TD_API_BASE') ?: '<production address>'];`
  and read it with `Settings::get('tribunedesk')`.
- **Never in configuration entities:** `drush config:export` writes config to YAML that goes to
  git. Module config may hold non-secret options only.

## 3. Unique key and lock

- A table of the module (`hook_schema`): `article_id` (varchar 36, unique key), `nid`,
  `last_sent_at`, `last_delivery_id`, serialized links.
- Take the `lock` service (`\Drupal::lock()->acquire('tribunedesk:' . $article_id, 30)`) and a
  database transaction around read-compare-write; the unique key catches the race the lock
  misses.
- Each update can save a new revision (`setNewRevision(TRUE)` with a log message) so editors see
  what Tribune Desk changed. Decide with the user whether an update replaces an already
  published node or goes through Content Moderation. The contract asks only to update the post
  made the first time, and allows `skipped_already_published` for a published one; leaving a
  published node alone is `DraftRules`' policy, and its statuses are WordPress's (`draft`,
  `pending`), so map the node's state to them first.

## 4. Publish hook and link back

- `hook_entity_update()` (or `hook_node_update()`) when `status` flips to published, also for the
  Scheduler module. Put a queue item; a `QueueWorker` plugin (cron) sends the link back with
  Guzzle (`\Drupal::httpClient()`) and `LinkBack`. A repeat is harmless.
- The developer command `drush td:publish` (section 7) is different: it must send the link back
  before it exits, so it processes that queue itself at the end, and does not leave the item to cron.

## 5. Edit URL

`$node->toUrl('edit-form', ['absolute' => TRUE])->toString()` built without access checks (do
not use `->access()`); with no request during cron and drush, build absolute URLs on the site
address from `TD_SITE_URL` in `settings.php` (the reference module's `site_url`), so they are
right.

## 6. Images

Check the host with `ImageHostRule`, then download in a queue worker, save as a file entity
(`file_system`, `public://`) and a Media entity if the site uses Media; set `alt` and `title`.

Testing with `tdkit`: the mock serves images over https with a test certificate. Trust its CA, the file `TDKIT check` prints as `TD_CA_BUNDLE`, in the test environment only, through Guzzle's `verify` option (`['verify' => getenv('TD_CA_BUNDLE')]`). Never in production: there the system's CAs stay.

## 7. Developer commands

Drush commands in `src/Drush/Commands/TribunedeskCommands.php` (Drush 12+ attributes):
`drush td:inspect <article_id>`, `drush td:publish <article_id>`, `drush td:poll`, and at level 3
`drush td:taxonomy-sync` (one full run of your vocabularies' terms to
`POST /v3/cms/taxonomy/terms`). On Windows run
`vendor\bin\drush.bat` or `vendor/bin/drush` explicitly.

`publish` sends the link back before it exits, so `check` finds it: it reads the report right after
the command returns. A retry queue may still handle a failed send later. The reference module does
this: `drush td:publish` processes the link-back queue before it exits.

## 8. Running the project's tests

`vendor/bin/phpunit -c web/core modules/custom/tribunedesk` (Kernel tests for the controller and
storage; Unit tests where the library is enough). A DDEV or Lando project runs them inside the
container (`ddev exec`), and then `tdkit` must run where the site can reach it.

## 9. Pitfalls

- Text formats strip tags: the format used for the body must allow what `html` contains
  (headings, lists, links, `blockquote`) and, if kept, the AI label `<script>` block; otherwise
  drop the block and render the label in the head (`hook_page_attachments`).
- Translations: a node may be translated, the API has one language per article; store the
  delivery's language on the node.
- Page cache and Dynamic Page Cache must not cache the webhook route (`no_cache`).
- Multiple web heads: the lock service must be the database one, not memory.
- **No `article` content type on Drupal 11.4+:** the standard profile no longer creates it; a
  site installed from it may have none. Check the bundles first (`drush entity:bundle-info node`
  or the node type list) and ask which content type posts go to; on a fresh site the core recipe
  `core/recipes/article_content_type` adds the article type (`drush recipe core/recipes/article_content_type`).
- **Local runs with `php -S`:** start it from the `web/` directory (the document root), with
  `.ht.router.php` as the router, or Drupal's routes give 404. It serves one request at a time
  by default (`references/php-library.md`, "Running it locally").
- **Windows: one container for drush and the web server.** Drupal caches its service container
  under a key built from the paths in `$settings['container_yamls']`. The web server spells them
  with backslashes (`C:\site\web/sites/...`), drush with forward slashes, so the site keeps two
  cached containers and `drush en` or `drush cr` refreshes only drush's. Web requests then run
  without the new module and every route of it answers 500 "The controller ... is not callable"
  while drush loads the module fine. Before enabling the module, add this line to
  `web/sites/default/settings.local.php` (local only, not committed; make sure `settings.php`
  includes it) or to the end of `settings.php`:

  ```php
  $settings['container_yamls'] = array_map(fn ($p) => str_replace(DIRECTORY_SEPARATOR, '/', $p), $settings['container_yamls']);
  ```

  It does nothing on Linux or macOS. If the 500 is already there, add the line and run
  `drush cr` once more.

## 10. Level 4 (media library)

The model (state, queue, screens, staging) is in `references/cms/generic.md`, section 10. In
Drupal:

- Module tables (`hook_schema`): `tribunedesk_sync_state` (one row: cursor, attempts, resync
  flag, open preview id) and `tribunedesk_media` keyed by the Media entity id (`asset_id`, field
  versions serialized, set-aside values, send result), plus `tribunedesk_media_edits` (media id,
  field, `changed_at`, unique per media and field) and a deletions table.
- `hook_media_update()` and `hook_media_delete()` fill the queues; the sync applies feed changes
  with a flag the hooks check (a service property set around the save), so they do not enter
  them.
- The lock: `\Drupal::lock()->acquire('tribunedesk:sync', 300)` (the database lock service on
  several web heads) around one cycle.
- `hook_cron()` runs one cycle (needs a real cron calling `drush cron` every few minutes; the
  Automated Cron module runs only after page views); a `QueueWorker` sends the local edits.
- Field mapping: the Media type's `field_media_image` `alt` and `title`, or text fields on the
  Media entity; decide with the user (generic, section 10, Field mapping).
- Admin routes with `_permission: 'administer tribunedesk'` for held batches and the resync
  preview.
- Drush commands for `TDKIT check`: `td:sync`, `td:media-inspect <cms_media_id>`,
  `td:media-add <file>`, `td:media-edit <cms_media_id> <field> <value>`,
  `td:media-delete <cms_media_id>`, `td:media-reset`.
