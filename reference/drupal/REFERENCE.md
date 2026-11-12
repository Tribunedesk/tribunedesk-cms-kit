# Drupal reference integration (levels 1 + 2, webhook)

**Reference to read, not a supported module.** Built by the skill `tribunedesk-integration` in the
`drupal-l12` run (2026-11-12) on a Drupal 11 site (standard profile, SQLite), on top of the
official PHP library `tribunedesk/cms-protocol` 1.0.0 (signature check, draft rules, answers,
link back, API errors).

## What is here

| Path | Goes to |
|---|---|
| `tribunedesk/` | `web/modules/custom/tribunedesk/`: the module (webhook controller, delivery handler with a lock per article, link back on publish with a queue for retries, Drush commands `td:inspect` and `td:publish`, kernel and unit tests) |
| `settings.tribunedesk.php` | the lines appended to `web/sites/default/settings.php`: secrets and addresses from the environment, never exported configuration |
| `.env.example` | the variable names |
| `tribunedesk.json` | the manifest written from the `tdkit check` report |

## Install it into a Drupal 11 site

```
composer config repositories.tribunedesk-cms-php vcs https://github.com/Tribunedesk/tribunedesk-cms-php
composer require tribunedesk/cms-protocol:^1.0
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
tdkit check --levels 1,2 --mode webhook --contract v3.4.1-draft --webhook http://127.0.0.1:8888/td/webhook \
  --inspect-cmd "vendor/bin/drush td:inspect {article_id}" \
  --publish-cmd "vendor/bin/drush td:publish {article_id}"
```

Start the PHP server from inside `web/`: started from the project root with `-t web` it answered
500 once the module was enabled (found in the run).

## Changed by the reviewer

- Kept only what the integration adds; the run's Drupal site, its `composer.lock` and the
  development packages it added for tests are left out.
- The run added the library as a `git` repository; the install line above uses `vcs`, as
  `references/php-library.md` of the skill says. Both work.
