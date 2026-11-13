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
  published node or goes through Content Moderation; `DraftRules` covers the contract side.

## 4. Publish hook and link back

- `hook_entity_update()` (or `hook_node_update()`) when `status` flips to published, also for the
  Scheduler module. Put a queue item; a `QueueWorker` plugin (cron) sends the link back with
  Guzzle (`\Drupal::httpClient()`) and `LinkBack`. A repeat is harmless.
- The developer command `drush td:publish` (section 7) is different: it must send the link back
  before it exits, so it processes that queue itself at the end, and does not leave the item to cron.

## 5. Edit URL

`$node->toUrl('edit-form', ['absolute' => TRUE])->toString()` built without access checks (do
not use `->access()`); with no request during cron, set the base URL in settings so absolute
URLs are right.

## 6. Images

Check the host with `ImageHostRule`, then download in a queue worker, save as a file entity
(`file_system`, `public://`) and a Media entity if the site uses Media; set `alt` and `title`.

Testing with `tdkit`: the mock serves images over https with a test certificate. Trust its CA, the file `TDKIT check` prints as `TD_CA_BUNDLE`, in the test environment only, through Guzzle's `verify` option (`['verify' => getenv('TD_CA_BUNDLE')]`). Never in production: there the system's CAs stay.

## 7. Developer commands

Drush commands in `src/Drush/Commands/TribunedeskCommands.php` (Drush 12+ attributes):
`drush td:inspect <article_id>`, `drush td:publish <article_id>`, `drush td:poll`. On Windows run
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
  `.ht.router.php` as the router, or Drupal's routes give 404.
