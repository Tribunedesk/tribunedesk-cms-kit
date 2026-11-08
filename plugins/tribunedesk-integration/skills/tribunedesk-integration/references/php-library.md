# PHP projects: tribunedesk/cms-protocol

For any PHP CMS (Drupal, Laravel, Joomla, a custom PHP site) use the library
`tribunedesk/cms-protocol` instead of writing the protocol rules again. The Tribune Desk
WordPress plugin runs on the same classes. Its README is the reference for the API:
https://github.com/Tribunedesk/tribunedesk-cms-php#readme . Read it before writing code.

## Installing

PHP 8.3 or newer, no runtime dependencies. Once the package is on Packagist:

```
composer require tribunedesk/cms-protocol:^1.0
```

Until then (check https://packagist.org/packages/tribunedesk/cms-protocol), add the repository
to the project's `composer.json` first, then require it:

```
"repositories": [
    {"type": "vcs", "url": "https://github.com/Tribunedesk/tribunedesk-cms-php"}
]
```

Record the installed version in the manifest: `TDKIT manifest write … --protocol 1.0.0`.

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

`ChangesFeed` and `Resync` are for level 4; `ContractVersion::TESTED` says which contract a
release is tested against. If it is older than the documentation you downloaded, read the
CHANGELOG between the two with `TDKIT integrators` and handle the difference in your code.

## What the library does not do

There is **no HTTP transport**: the CMS sends requests with its own client (Guzzle in Drupal,
the `Http` facade in Laravel) and passes bodies and answers to the library. Persistence, locks,
queues and the publish hook are the CMS's job too (see the CMS reference).
