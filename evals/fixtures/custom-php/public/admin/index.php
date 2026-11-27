<?php

declare(strict_types=1);

// Behind HTTP basic auth on the production server (Apache), not in this code.
require_once __DIR__ . '/../../src/posts.php';

if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['publish'])) {
    publish_post((int) $_POST['publish']);
    header('Location: /admin/');
    exit;
}
$posts = db()->query('SELECT * FROM posts ORDER BY id DESC')->fetchAll();
?>
<!doctype html>
<html lang="pl">
<head><meta charset="utf-8"><title>Panel</title></head>
<body>
<h1>Wpisy</h1>
<table>
<?php foreach ($posts as $post): ?>
    <tr>
        <td><a href="/admin/edit.php?id=<?= (int) $post['id'] ?>"><?= e($post['title']) ?></a></td>
        <td><?= e($post['status']) ?></td>
        <td>
        <?php if ($post['status'] !== 'published'): ?>
            <form method="post"><button name="publish" value="<?= (int) $post['id'] ?>">Opublikuj</button></form>
        <?php endif; ?>
        </td>
    </tr>
<?php endforeach; ?>
</table>
<p><a href="/admin/photos.php">Biblioteka zdjęć</a></p>
</body>
</html>
