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

## 3. Unique key and lock

- A table keyed by `article_id` with a unique constraint, plus `last_sent_at` and the delivery id.
- Read-compare-write inside a transaction with a row lock (or an atomic conditional upsert), so
  two overlapping attempts of one send cannot create two posts or let an older send win.

## 4. Publish hook and link back

Find where the CMS makes a post public (an event, a hook, the publish action). From there queue a
retrying job that sends the link back. For posts published at once in the delivery, answer with
the permalink instead (guide 2).

## 5. Edit URL

An absolute `http(s)` address of the post's editor, built from the post id and the site's base URL
without checking the current user (there is none during a delivery).

## 6. Images

Download only from the allowed hosts (guide 1, Where images come from), in the background after
answering, with a timeout and a size limit.

## 7. Developer commands

Three commands runnable without a shell (a script, a CLI entry point):
`<cli> inspect <article_id>`, `<cli> publish <article_id>`, `<cli> poll`. Their output contract is
in the kit README, "The commands your integration provides".

## 8. Running the project's tests

Use the project's own test runner. Add tests for the signature check (with the contract's
signature vectors, `examples/vectors/webhook-signature.json` in the downloaded docs), for two
attempts of one send, and for an older send after a newer one.

## 9. Pitfalls

- Body parsing middleware that runs before your route.
- Clock not synchronised (5-minute tolerance).
- Image downloads inside the request (30-second answer limit).
- Answering 4xx for anything but a bad signature: a 4xx ends the send for good (guide 1, Your
  answer).
