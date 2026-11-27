<?php

declare(strict_types=1);

require_once __DIR__ . '/../src/posts.php';
?>
<!doctype html>
<html lang="pl">
<head><meta charset="utf-8"><title>Gazeta</title></head>
<body>
<h1>Gazeta</h1>
<ul>
<?php foreach (published_posts() as $post): ?>
    <li><a href="<?= e(post_url($post)) ?>"><?= e($post['title']) ?></a></li>
<?php endforeach; ?>
</ul>
</body>
</html>
