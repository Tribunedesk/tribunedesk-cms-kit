<?php

declare(strict_types=1);

require_once __DIR__ . '/db.php';

function post_by_id(int $id): ?array
{
    $stmt = db()->prepare('SELECT * FROM posts WHERE id = ?');
    $stmt->execute([$id]);
    return $stmt->fetch() ?: null;
}

function post_by_slug(string $slug): ?array
{
    $stmt = db()->prepare("SELECT * FROM posts WHERE slug = ? AND status = 'published'");
    $stmt->execute([$slug]);
    return $stmt->fetch() ?: null;
}

function published_posts(): array
{
    return db()->query("SELECT * FROM posts WHERE status = 'published' ORDER BY published_at DESC")
        ->fetchAll();
}

function save_post(int $id, array $fields): void
{
    $stmt = db()->prepare(
        'UPDATE posts SET title = ?, excerpt = ?, body = ?, category_id = ?, author = ? WHERE id = ?'
    );
    $stmt->execute([
        $fields['title'], $fields['excerpt'], $fields['body'],
        $fields['category_id'] ?: null, $fields['author'], $id,
    ]);
}

/** The editor's "Publish" button. */
function publish_post(int $id): void
{
    $stmt = db()->prepare(
        "UPDATE posts SET status = 'published', published_at = COALESCE(published_at, ?) WHERE id = ?"
    );
    $stmt->execute([now_utc(), $id]);
}

function post_url(array $post): string
{
    return '/post.php?slug=' . rawurlencode($post['slug']);
}

function post_tags(int $postId): array
{
    $stmt = db()->prepare(
        'SELECT t.* FROM tags t JOIN post_tags pt ON pt.tag_id = t.id WHERE pt.post_id = ?'
    );
    $stmt->execute([$postId]);
    return $stmt->fetchAll();
}
