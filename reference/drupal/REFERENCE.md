# Drupal reference integration (levels 1 + 2, webhook)

**Reference to read, not a supported module.** Built by the skill `tribunedesk-integration` in the
`drupal-l12` run (2026-11-12) on a Drupal 11 site (standard profile, SQLite), on top of the
official PHP library `tribunedesk/cms-protocol` (signature check, draft rules, answers,
link back, API errors): 1.0.0 in the run, 1.4.x today.

## What is here

| Path | Goes to |
|---|---|
| `tribunedesk/` | `web/modules/custom/tribunedesk/`: the module (webhook controller, delivery handler with a lock per article, link back on publish with a queue for retries, the publication mode with `hook_cron()` publishing scheduled nodes, Drush commands `td:inspect` and `td:publish`, kernel and unit tests) |
| `settings.tribunedesk.php` | the lines appended to `web/sites/default/settings.php`: secrets and addresses from the environment, never exported configuration |
| `.env.example` | the variable names |
| `tribunedesk.json` | the manifest written from the `tdkit check` report |

## Install it into a Drupal 11 site

The module writes `article` nodes with a `body` field. Since Drupal 11.4 the `standard` profile
no longer creates that type; apply the core recipe first if the site has none:
`vendor/bin/drush recipe web/core/recipes/article_content_type`.

```
composer require tribunedesk/cms-protocol:^1.4 symfony/html-sanitizer:^7.3
cp -r tribunedesk web/modules/custom/
cat settings.tribunedesk.php | tail -n +4 >> web/sites/default/settings.php
vendor/bin/drush en tribunedesk -y
```

## Check it

```
cd web
TD_WEBHOOK_SECRET=whsec_dGRraXQtbW9jay1zaWduaW5nLXNlY3JldC0wMDAwMDA= \
TD_API_BASE=http://127.0.0.1:8787 TD_CMS_TOKEN=tdcms_mock TD_SITE_URL=http://127.0.0.1:8888 \
  php -S 127.0.0.1:8888 .ht.router.php &
cd ..
tdkit check --levels 1,2 --mode webhook --contract v3.9.0-draft --webhook http://127.0.0.1:8888/td/webhook \
  --inspect-cmd "vendor/bin/drush td:inspect {article_id}" \
  --publish-cmd "vendor/bin/drush td:publish {article_id}"
```

`php -S` answers one request at a time, so `l1-overlapping-attempts` passes there without proving
the lock; on Linux or macOS add `PHP_CLI_SERVER_WORKERS=4` before `php -S`, elsewhere check on
the site's real server (skill, `references/php-library.md`, "Running it locally").

On Windows run `vendor\bin\drush.bat`, and before `drush en` add this line to the end of
`settings.php` (or to `settings.local.php`):

```php
$settings['container_yamls'] = array_map(fn ($p) => str_replace(DIRECTORY_SEPARATOR, '/', $p), $settings['container_yamls']);
```

Drupal caches its container under a key built from those paths; the web server spells them with
backslashes and drush with forward slashes, so without the line `drush en` refreshes only drush's
container and every request to the module answers 500 "controller not callable" (the parity-drupal
run of 2026-11-27, found on 2026-11-28; skill, `references/cms/drupal.md`).

`tdkit` is the kit's command line tool:
`uvx --from git+https://github.com/Tribunedesk/tribunedesk-cms-kit@v1.8.1 tdkit` (kit README,
"Run it"). The secret and the token above are the mock's public test values.

Last checked 2026-11-27 in CI (job `reference-drupal`, Ubuntu, PHP 8.3, Drupal 11,
`tribunedesk/cms-protocol` 1.4.0, `symfony/html-sanitizer` 7.x): tdkit 1.8.0, contract 3.9.0-draft, 15 passed, 0 failed.
`tribunedesk.json` was written from that run's report (artifact `reference-drupal-report`).

## Changed by the reviewer

- Kept only what the integration adds; the run's Drupal site, its `composer.lock` and the
  development packages it added for tests are left out.
- 2026-11-17: the embed filter of guide 1 (contract 3.5); 2026-11-25: the publication mode with
  `hook_cron()` publishing scheduled nodes (contract 3.7).
- 2026-11-27: the library comes from Packagist (the run added it as a `git` repository, before
  it was published there); `^1.4` instead of `^1.0`, the release that knows contract 3.8. The
  body filter is an allow list on a parser (`symfony/html-sanitizer`) plus a host and path check
  of iframes, as `guide/complete-integration.md` asks since 3.9 (the regular expressions before
  let `onerror` and `javascript:` through).
