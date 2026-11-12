<?php

declare(strict_types=1);

namespace Drupal\tribunedesk;

use Drupal\Core\Database\Connection;
use Drupal\Core\Entity\EntityTypeManagerInterface;
use Drupal\Core\Site\Settings;
use Drupal\node\NodeInterface;

/**
 * The tribunedesk_article table and the addresses of the nodes it maps.
 *
 * Settings come from $settings['tribunedesk'] in settings.php, filled from
 * environment variables; secrets are never stored in configuration.
 */
class ArticleRegistry {

  public const TABLE = 'tribunedesk_article';

  public const DEFAULT_API_BASE = 'https://api.tribunedesk.com';

  public function __construct(
    protected Connection $database,
    protected EntityTypeManagerInterface $entityTypeManager,
  ) {}

  /**
   * One value of $settings['tribunedesk'], or $default when it is empty.
   */
  public static function setting(string $key, mixed $default = NULL): mixed {
    $value = Settings::get('tribunedesk', [])[$key] ?? NULL;
    return ($value === NULL || $value === '' || $value === FALSE) ? $default : $value;
  }

  public function load(string $article_id): ?object {
    $row = $this->database->select(self::TABLE, 't')
      ->fields('t')
      ->condition('article_id', $article_id)
      ->execute()
      ->fetchObject();
    return $row ?: NULL;
  }

  public function loadByNid(int $nid): ?object {
    $row = $this->database->select(self::TABLE, 't')
      ->fields('t')
      ->condition('nid', $nid)
      ->execute()
      ->fetchObject();
    return $row ?: NULL;
  }

  /**
   * The node made from an article, or NULL.
   */
  public function node(string $article_id): ?NodeInterface {
    $row = $this->load($article_id);
    if ($row === NULL) {
      return NULL;
    }
    $node = $this->entityTypeManager->getStorage('node')->load($row->nid);
    return $node instanceof NodeInterface ? $node : NULL;
  }

  /**
   * Inserts or updates the row of an article.
   *
   * @param array<string, mixed> $fields
   */
  public function save(string $article_id, array $fields): void {
    $this->database->merge(self::TABLE)
      ->key('article_id', $article_id)
      ->fields($fields)
      ->execute();
  }

  public function markReported(string $article_id, string $url): void {
    $this->database->update(self::TABLE)
      ->fields(['reported_url' => $url])
      ->condition('article_id', $article_id)
      ->execute();
  }

  public function deleteByNid(int $nid): void {
    $this->database->delete(self::TABLE)->condition('nid', $nid)->execute();
  }

  /**
   * The public address of a node, or NULL while it is not published.
   */
  public function permalink(NodeInterface $node): ?string {
    if (!$node->isPublished()) {
      return NULL;
    }
    return $node->toUrl('canonical', $this->urlOptions())->toString(TRUE)->getGeneratedUrl();
  }

  /**
   * The edit address, built without access checks.
   *
   * The delivery is a server-to-server call with no editor logged in
   * (guide/1-article-delivery.md, Fields of your answer, edit_url).
   */
  public function editUrl(NodeInterface $node): string {
    return $node->toUrl('edit-form', $this->urlOptions())->toString(TRUE)->getGeneratedUrl();
  }

  /**
   * Absolute URLs on TD_SITE_URL when set, so drush and cron build the same
   * addresses as a web request.
   */
  protected function urlOptions(): array {
    $options = ['absolute' => TRUE];
    $site_url = self::setting('site_url');
    if (is_string($site_url)) {
      $options['base_url'] = rtrim($site_url, '/');
    }
    return $options;
  }

}
