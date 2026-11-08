# When a check stays red

Read the failing scenario's guide point first; then look here for the usual causes.

## Every signed delivery gets 401

- **The framework parsed the body before the check.** The signature is over the raw bytes. A
  framework that parses JSON first and re-serialises it changes spacing, key order or escaping
  (non-ASCII titles), and the check fails. Read the raw body (CMS reference, section 1).
- **Wrong secret.** Locally the integration must use the secret `TDKIT mock` prints (or pass
  yours with `--secret`). Check the variable is set, without printing it.
- **The `whsec_` prefix was kept in the key.** The key is the base64 part after `whsec_`
  (`guide/1-article-delivery.md`, Verifying the signature).
- **Header names.** Some servers rename headers (`webhook-id` to `HTTP_WEBHOOK_ID` in PHP,
  `webhook_id` in WordPress). Read them case-insensitively and in the server's form.

## Only `l1-clock-skew` or production deliveries fail with 401

The clock. The timestamp check allows 5 minutes. tdkit cannot see the server's clock; a real
server more than 5 minutes off answers 401 to real deliveries and loses articles. Turn on NTP.

## 403 or 419 from the webhook

CSRF protection. The webhook route must be exempt (Django `csrf_exempt`, Laravel
`VerifyCsrfToken::$except`); the signature is its protection.

## 301/302 from the webhook

Tribune Desk does not follow redirects (`guide/1-article-delivery.md`, Article delivery webhook):
a redirect ends the send. Common causes: `http` redirected to `https`, a missing or extra
trailing slash, a locale prefix (`/en/td/webhook`). Register the exact address.

## Timeouts or duplicates

- The answer must come within 30 seconds; download images in the background.
- Two posts for one article: the unique key on `article_id` or the row lock is missing
  (CMS reference, section 3).

## The mock cannot start, or the integration cannot reach it

- **Port in use:** a previous `tdkit mock` or `check` is still running. Stop it or use `--port`
  and update `TD_API_BASE`.
- **Proxy:** with `HTTP_PROXY` set, some clients send `127.0.0.1` through the proxy. Add
  `127.0.0.1,localhost` to `NO_PROXY` for local runs.
- **Docker:** inside a container `127.0.0.1` is the container. Run the integration on the host,
  or run `tdkit` in the same container.

## Windows

- Commands are run without a shell. `tdkit` looks the program up on `PATH`, so `drush`, `npx`
  and `composer` (`.bat`/`.cmd` files) work; a shell builtin or an alias does not. Use the real
  program, e.g. `php artisan …`, `vendor\bin\drush.bat …`.
- Quote paths with spaces in double quotes; single quotes are ordinary characters on Windows.
- `inspect` must print UTF-8. In Python on Windows set `PYTHONUTF8=1` for the command or
  reconfigure stdout.

## Read mode

- **No result reported:** the poll must fetch the article, save it and report the result with
  the send's `delivery_id` (`guide/1-article-delivery.md`, Level 1 without a public endpoint).
- **409 on the result:** a newer send replaced the one you fetched. Fetch the article again.
- **`read-cursor-expired` fails:** keep the cursor between polls and handle 410 as the guide's
  step 4 says.
