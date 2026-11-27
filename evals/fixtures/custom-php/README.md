# Gazeta

Our newspaper's site: plain PHP 8.3 and SQLite, written in house, no framework and no Composer.

- Set up the database: `php bin/setup.php` (creates `data/site.sqlite` with sample categories,
  tags and one post).
- Run locally: `php -S 127.0.0.1:8080 -t public`
- Public pages: `/` (published posts), `/post.php?slug=...`
- Editors' pages: `/admin/` (posts: edit, publish), `/admin/photos.php` (the photo library).
- Production: Apache with PHP-FPM on our server, https://gazeta.example.com. We have shell
  access and can add cron lines.

Code: `src/` (database and post functions), `public/` (pages). There are no automated tests.
