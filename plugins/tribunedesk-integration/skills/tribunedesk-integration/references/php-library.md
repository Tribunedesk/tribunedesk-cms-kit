# PHP projects: tribunedesk/cms-protocol

For any PHP CMS (Drupal, Laravel, Joomla, a custom PHP site) use the library
`tribunedesk/cms-protocol` instead of writing the protocol rules again. The Tribune Desk
WordPress plugin runs on the same classes. Its README is the reference for the API:
https://github.com/Tribunedesk/tribunedesk-cms-php#readme . Read it before writing code.

## Installing

PHP 8.3 or newer, no runtime dependencies. Take the newest release (its tags:
https://github.com/Tribunedesk/tribunedesk-cms-php/tags) and require that minor, for example
`^1.4` for 1.4.x; an older minor may not know the contract you downloaded. Once the package is on
Packagist:

```
composer require tribunedesk/cms-protocol:^1.4
```

Until then (check https://packagist.org/packages/tribunedesk/cms-protocol), add the repository
to the project's `composer.json` first, then require it:

```
composer config repositories.tribunedesk-cms-php git https://github.com/Tribunedesk/tribunedesk-cms-php.git
```

Use the `git` type with the `https` address: with the `vcs` type and no GitHub token, Composer
may fall back to cloning over SSH, which fails without an SSH key on GitHub.

Record the version Composer installed (`composer show tribunedesk/cms-protocol`) in the manifest:
`TDKIT manifest write … --protocol <that version>`.

## A PHP site without Composer

Many hand-written PHP sites have no `composer.json`. Ask before adding Composer to the project
(it is the user's choice). If they do not want it, use the library without it:

1. Download the release's archive from its tag on GitHub and copy its `src/` into the project,
   outside the web root, for example `lib/tribunedesk-cms-protocol/` (MIT licence: keep its
   `LICENSE` next to it).
2. Load it with a small autoloader in the site's bootstrap (the path relative to that file):

   ```php
   spl_autoload_register(function (string $class): void {
       $prefix = 'TribuneDesk\\Protocol\\';
       if (str_starts_with($class, $prefix)) {
           require __DIR__ . '/lib/tribunedesk-cms-protocol/'
               . str_replace('\\', '/', substr($class, strlen($prefix))) . '.php';
       }
   });
   ```

3. Record the copied version with `--protocol <version>`, and say in the launch steps that a new
   contract means copying a newer release by hand.

## PHP older than 8.3

The library does not install on PHP 8.0-8.2 (its `composer.json` requires 8.3). Check the version
the site runs in production (`php -v` on the server, not only on the laptop). Then:

- Recommend upgrading PHP first: PHP 8.1 is out of security support since 2025-12-31 and 8.2
  leaves it on 2026-12-31 (https://www.php.net/supported-versions.php), so the site needs the
  upgrade anyway.
- If the user cannot upgrade now, build without the library: write the protocol from the guide,
  as `references/cms/generic.md` says. The signature check is
  `base64_encode(hash_hmac('sha256', $signedContent, $key, true))` compared with `hash_equals`
  to each `v1,` entry, with the signed content and the key exactly as
  `guide/1-article-delivery.md`, Verifying the signature, defines them; test it against the
  contract's signature vectors
  (`examples/vectors/webhook-signature.json`). Every other rule (draft rules, the answer, link
  back, placeholders) is in the guide chapter of its level. Leave `--protocol` out of the
  manifest, and add "move to `tribunedesk/cms-protocol` after the PHP upgrade" to the launch
  steps.

## Running it locally for `TDKIT check`

`php -S` serves one request at a time. `l1-overlapping-attempts` sends two attempts at once, and
on a one-request server they never overlap, so the scenario passes without proving the lock.
Run the check on a server that handles requests in parallel:

- Linux and macOS: `PHP_CLI_SERVER_WORKERS=4 php -S 127.0.0.1:8888 router.php` (the built-in
  server forks workers; not on Windows);
- Windows, or to be close to production: the project's own stack (Apache or nginx with PHP-FPM,
  DDEV, Laragon, XAMPP), or the Docker image the site deploys with.

Say which one you used when you report `l1-overlapping-attempts`.

## The HTML filter

Guide 1 ("The HTML body") asks you to pass `html` through the filter your CMS applies to editor
content. A hand-written PHP site often has none. Then use a maintained sanitizer, for example
HTML Purifier (`ezyang/htmlpurifier`, also usable without Composer from its standalone
download), with an allow-list: the usual elements of guide 1, `figure`/`img`/`figcaption` with
the `data-td-*` attributes, `a` with `href`, `target`, `rel`, the trusted `iframe` players with
the attributes guide 1 lists, and nothing else. A regular expression or `strip_tags` is not a
filter: they leave event attributes (`onerror`, `onclick`) and `javascript:` addresses through,
which `TDKIT check` does not test (`l1-embeds` checks only `script` and `iframe`). Add the
project's own test for them.

## Which class for what

All classes are in `TribuneDesk\Protocol` and have static methods only.

| Class | Use it for | Level |
|---|---|---|
| `WebhookSignature` | verifying the delivery's signature on the raw body | 1 |
| `DraftRules` | create, update or skip a delivery for a post that already exists | 1 |
| `DeliveryAnswer` | building the answer to a delivery | 1 (2, 4 for some fields) |
| `ImageHostRule` | which hosts images may be downloaded from | 1 |
| `LinkBack` | building the link back request and reading its results | 2 |
| `PlaceholderLinks` | replacing placeholder links, unwrapping the missing ones | 3 |
| `BacklinkSources` | the "read more" box rules | 3 |
| `AuthorOrder` | the order in which people of a delivery are matched to CMS users | 3 |
| `ApiErrors` | reading any error answer of the API (code, retry wait) | all |
| `BodyFigures` | finding library photos in `html` (`find`) and replacing each with your native image markup (`replace`) | 1 + 4 |

`ChangesFeed` and `Resync` are for level 4; `ContractVersion::TESTED` says which contract a
release is tested against. If it is older than the documentation you downloaded, read the
CHANGELOG between the two with `TDKIT integrators` and handle the difference in your code.

## What the library does not do

There is **no HTTP transport**: the CMS sends requests with its own client (Guzzle in Drupal,
the `Http` facade in Laravel) and passes bodies and answers to the library. Persistence, locks,
queues and the publish hook are the CMS's job too (see the CMS reference).

## Secret and token names

The library takes the secret and the token as arguments: `WebhookSignature::verify($secret, ...)`
(see `references/cms/laravel.md`, section 1). The names of the environment variables that hold them
are the kit's names, the same in every CMS reference and in `.env.example`: `TD_WEBHOOK_SECRET`
(the signing secret), `TD_CMS_TOKEN` (the `tdcms_` token) and `TD_API_BASE` (the API address),
plus `TD_SITE_URL` (the site's public address, for `edit_url` and `permalink` built outside a
web request). Read them in your CMS's configuration and pass the values on.

The library's own README reads the secret with `getenv('TRIBUNEDESK_WEBHOOK_SECRET')`. That name
is only its example: in an integration built with this kit use `TD_WEBHOOK_SECRET`, so the
variable matches the CMS reference, `.env.example` and the kit's checks.
