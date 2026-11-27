<?php

declare(strict_types=1);

require_once __DIR__ . '/../../src/db.php';

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    if (isset($_FILES['image']) && $_FILES['image']['error'] === UPLOAD_ERR_OK) {
        $name = date('Y/m/') . bin2hex(random_bytes(8)) . '.' . strtolower(pathinfo($_FILES['image']['name'], PATHINFO_EXTENSION));
        @mkdir(dirname(SITE_ROOT . '/public/uploads/' . $name), 0775, true);
        move_uploaded_file($_FILES['image']['tmp_name'], SITE_ROOT . '/public/uploads/' . $name);
        $now = now_utc();
        db()->prepare('INSERT INTO photos (file, title, alt, caption, uploaded_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)')
            ->execute([$name, $_POST['title'] ?? '', $_POST['alt'] ?? '', $_POST['caption'] ?? '', $now, $now]);
    } elseif (isset($_POST['id'])) {
        db()->prepare('UPDATE photos SET title = ?, alt = ?, caption = ?, updated_at = ? WHERE id = ?')
            ->execute([$_POST['title'], $_POST['alt'], $_POST['caption'], now_utc(), (int) $_POST['id']]);
    } elseif (isset($_POST['delete'])) {
        db()->prepare('DELETE FROM photos WHERE id = ?')->execute([(int) $_POST['delete']]);
    }
    header('Location: /admin/photos.php');
    exit;
}
$photos = db()->query('SELECT * FROM photos ORDER BY id DESC')->fetchAll();
?>
<!doctype html>
<html lang="pl">
<head><meta charset="utf-8"><title>Biblioteka zdjęć</title></head>
<body>
<h1>Biblioteka zdjęć</h1>
<form method="post" enctype="multipart/form-data">
    <input type="file" name="image"> <input name="title" placeholder="tytuł">
    <input name="alt" placeholder="alt"> <input name="caption" placeholder="podpis">
    <button>Dodaj</button>
</form>
<?php foreach ($photos as $p): ?>
    <form method="post">
        <img src="/uploads/<?= e($p['file']) ?>" width="120" alt="">
        <input type="hidden" name="id" value="<?= (int) $p['id'] ?>">
        <input name="title" value="<?= e($p['title']) ?>">
        <input name="alt" value="<?= e($p['alt']) ?>">
        <input name="caption" value="<?= e($p['caption']) ?>">
        <button>Zapisz</button>
    </form>
    <form method="post"><button name="delete" value="<?= (int) $p['id'] ?>">Usuń</button></form>
<?php endforeach; ?>
</body>
</html>
