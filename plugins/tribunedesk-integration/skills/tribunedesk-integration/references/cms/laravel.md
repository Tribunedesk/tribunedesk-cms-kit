# Laravel

Use `tribunedesk/cms-protocol` for the protocol rules (`references/php-library.md`). Contract
rules come from the downloaded guide.

## 1. Raw body and the webhook route

- A route in `routes/api.php` (no session, no CSRF), e.g. `Route::post('td/webhook',
  TribuneDeskWebhookController::class)`. If it must live in `web.php`, add it to the CSRF
  exceptions (`VerifyCsrfToken::$except`, or `validateCsrfTokens(except: [...])` in Laravel 11+).
- Verify `$request->getContent()` (raw string) with `WebhookSignature::verify($secret,
  $request->headers->all(), $body)` before `json_decode`. Do not use `$request->json()` or a
  FormRequest for this route.

## 2. Secret and token

- `.env`: `TD_WEBHOOK_SECRET`, `TD_CMS_TOKEN`, `TD_API_BASE`; read them only in
  `config/services.php` (`'tribunedesk' => ['secret' => env('TD_WEBHOOK_SECRET'), ...]`) and use
  `config('services.tribunedesk.secret')` elsewhere (env() is null after `config:cache`).
- `.env.example` with the names only.

## 3. Unique key and lock

- Migration: table `tribunedesk_articles` with `article_id` (uuid, unique), `post_id`,
  `last_sent_at`, `last_delivery_id`, JSON columns for links.
- `DB::transaction(fn () => ...)` with `TribunedeskArticle::where('article_id', $id)
  ->lockForUpdate()->first()`; create under the unique index and catch
  `UniqueConstraintViolationException` once.

## 4. Publish hook and link back

- A model observer (`updated` when the post becomes published) or the publish action dispatches
  a queued job that sends the link back with `Http::withToken(...)->post(...)` and
  `LinkBack` from the library. Queue retries cover failures; a repeat is harmless.

## 5. Edit URL

`route('admin.posts.edit', $post)` or `url("/admin/posts/{$post->id}/edit")`, built with the
app URL from config (`APP_URL`), without auth checks.

## 6. Images

Check the host with `ImageHostRule`, then download in a queued job (`Http::timeout(...)`), store
with `Storage::put` and attach.

## 7. Developer commands

Artisan commands in `app/Console/Commands`: `php artisan td:inspect {article_id}`,
`php artisan td:publish {article_id}`, `php artisan td:poll`. Print with
`$this->line(json_encode($data, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES))`.

## 8. Running the project's tests

`php artisan test` (or `vendor/bin/phpunit`/`pest`). Feature test: post a signed request
(signed with the mock secret) to the route and assert one row for two attempts.

## 9. Pitfalls

- `TrimStrings`/`ConvertEmptyStringsToNull` middleware do not touch `getContent()`, but a custom
  JSON middleware may: keep the route out of it.
- `config:cache` makes `env()` return null outside config files.
- Queue worker not running locally: links back and images never happen; run
  `php artisan queue:work` or the `sync` driver in tests.

## 10. Level 4 (media library)

The model (state, queue, screens, staging) is in `references/cms/generic.md`, section 10. In
Laravel:

- Migrations for `td_sync_state` (one row: cursor, attempts, resync flag) and columns or a side
  table on the media model (`asset_id`, field versions as JSON, set-aside values, send result),
  plus `td_media_edits` (media id, field, `changed_at`, unique per media and field).
- A model observer on the media model fills the edit queue; apply feed changes inside
  `Model::withoutEvents()` so they do not enter it.
- `Cache::lock('td-sync', 300)->get(...)` around one cycle; schedule it in `routes/console.php`
  (`Schedule::command('td:sync')->everyFiveMinutes()->withoutOverlapping()`), and dispatch a
  delayed job a minute after an edit.
- Filament or Nova pages (or a plain admin controller) for held batches and the resync preview.
- Commands for `TDKIT check`: `php artisan td:sync`, `td:media-inspect {cms_media_id}`,
  `td:media-add {file}`, `td:media-edit {cms_media_id} {field} {value}`,
  `td:media-delete {cms_media_id}`, `td:media-reset`.
