<?php

declare(strict_types=1);

require_once __DIR__ . '/../src/posts.php';

$post = post_by_slug((string) ($_GET['slug'] ?? ''));
if ($post === null) {
    http_response_code(404);
    echo 'Not found';
    exit;
}
?>
<!doctype html>
<html lang="pl">
<head><meta charset="utf-8"><title><?= e($post['title']) ?></title></head>
<body>
<h1><?= e($post['title']) ?></h1>
<p><?= e($post['excerpt']) ?></p>
<?= $post['body'] /* HTML written by our editors */ ?>
<p>Tagi: <?= e(implode(', ', array_column(post_tags((int) $post['id']), 'name'))) ?></p>
</body>
</html>
