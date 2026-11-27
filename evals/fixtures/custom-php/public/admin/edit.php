<?php

declare(strict_types=1);

require_once __DIR__ . '/../../src/posts.php';

$id = (int) ($_GET['id'] ?? 0);
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    save_post($id, $_POST);
    header('Location: /admin/');
    exit;
}
$post = post_by_id($id);
if ($post === null) {
    http_response_code(404);
    exit;
}
$categories = db()->query('SELECT * FROM categories ORDER BY name')->fetchAll();
?>
<!doctype html>
<html lang="pl">
<head><meta charset="utf-8"><title>Edycja</title></head>
<body>
<form method="post">
    <p><input name="title" value="<?= e($post['title']) ?>"></p>
    <p><input name="author" value="<?= e($post['author']) ?>"></p>
    <p><select name="category_id"><option value="">—</option>
    <?php foreach ($categories as $c): ?>
        <option value="<?= (int) $c['id'] ?>" <?= $c['id'] == $post['category_id'] ? 'selected' : '' ?>><?= e($c['name']) ?></option>
    <?php endforeach; ?>
    </select></p>
    <p><textarea name="excerpt"><?= e($post['excerpt']) ?></textarea></p>
    <p><textarea name="body" rows="20"><?= e($post['body']) ?></textarea></p>
    <button>Zapisz</button>
</form>
</body>
</html>
