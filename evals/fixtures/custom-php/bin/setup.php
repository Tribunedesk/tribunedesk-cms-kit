<?php

declare(strict_types=1);

require_once __DIR__ . '/../src/db.php';

@mkdir(SITE_ROOT . '/data', 0775, true);
@mkdir(SITE_ROOT . '/public/uploads', 0775, true);
db()->exec(file_get_contents(SITE_ROOT . '/schema.sql'));

$pdo = db();
$pdo->exec("INSERT OR IGNORE INTO categories (id, name, slug) VALUES
    (1, 'Polityka', 'polityka'), (2, 'Sport', 'sport'), (3, 'Kultura', 'kultura')");
$pdo->exec("INSERT OR IGNORE INTO tags (id, name, slug) VALUES
    (1, 'wybory', 'wybory'), (2, 'samorząd', 'samorzad'), (3, 'piłka nożna', 'pilka-nozna')");
$pdo->exec("INSERT OR IGNORE INTO posts (id, title, slug, excerpt, body, status, published_at, category_id, author)
    VALUES (1, 'Witamy', 'witamy', 'Pierwszy wpis.', '<p>Witamy na stronie gazety.</p>', 'published',
    '2026-11-01T08:00:00Z', 1, 'Redakcja')");
$pdo->exec('INSERT OR IGNORE INTO post_tags (post_id, tag_id) VALUES (1, 2)');

echo "data/site.sqlite ready\n";
