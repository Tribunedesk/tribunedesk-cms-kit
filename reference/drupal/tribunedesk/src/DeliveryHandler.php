<?php

declare(strict_types=1);

namespace Drupal\tribunedesk;

use Drupal\Component\Datetime\TimeInterface;
use Drupal\Core\Database\Connection;
use Drupal\Core\Entity\EntityTypeManagerInterface;
use Drupal\Core\Lock\LockBackendInterface;
use Drupal\node\NodeInterface;
use Drupal\tribunedesk\Exception\LockBusyException;
use TribuneDesk\Protocol\DeliveryAnswer;
use TribuneDesk\Protocol\DraftRules;

/**
 * Turns a verified article delivery into a draft node (level 1).
 *
 * Rules: guide/1-article-delivery.md, Article delivery webhook ("Order of
 * sends", "Store under a unique key") and Done when.
 */
class DeliveryHandler {

  public function __construct(
    protected ArticleRegistry $registry,
    protected EntityTypeManagerInterface $entityTypeManager,
    protected Connection $database,
    protected LockBackendInterface $lock,
    protected TimeInterface $time,
  ) {}

  /**
   * Applies one delivery and returns the answer body (ArticleDeliveryResult).
   *
   * @param array<string, mixed> $article
   *   The decoded ArticleDelivery; unknown fields are ignored.
   * @param string|null $delivery_id
   *   X-Delivery-Id of the request, the same for every attempt of one send.
   *
   * @throws \InvalidArgumentException
   *   When the body has no usable article_id.
   * @throws \Drupal\tribunedesk\Exception\LockBusyException
   *   When another attempt of the same article holds the lock.
   */
  public function apply(array $article, ?string $delivery_id = NULL): array {
    $article_id = strtolower(trim((string) ($article['article_id'] ?? '')));
    if ($article_id === '' || strlen($article_id) > 64) {
      throw new \InvalidArgumentException('The delivery has no usable article_id.');
    }

    // Two attempts of one send can overlap: lock the article while we write;
    // the primary key on article_id catches anything the lock misses.
    $lock_name = 'tribunedesk:' . $article_id;
    if (!$this->lock->acquire($lock_name, 30.0)) {
      $this->lock->wait($lock_name, 20);
      if (!$this->lock->acquire($lock_name, 30.0)) {
        throw new LockBusyException("Article $article_id is locked by another attempt.");
      }
    }

    try {
      $transaction = $this->database->startTransaction();
      try {
        return $this->applyLocked($article_id, $article, $delivery_id);
      }
      catch (\Throwable $e) {
        $transaction->rollBack();
        throw $e;
      }
    }
    finally {
      $this->lock->release($lock_name);
    }
  }

  /**
   * @param array<string, mixed> $article
   */
  protected function applyLocked(string $article_id, array $article, ?string $delivery_id): array {
    $row = $this->registry->load($article_id);
    $node = $row !== NULL ? $this->registry->node($article_id) : NULL;
    $sent_at = is_string($article['sent_at'] ?? NULL) ? $article['sent_at'] : NULL;
    $sent_at_us = self::microseconds($sent_at);

    // An attempt of an older send that arrives after a newer one leaves the
    // node alone (guide/1-article-delivery.md, Order of sends).
    if ($node !== NULL && $sent_at_us !== NULL && $sent_at_us < (int) $row->sent_at_us) {
      $status = $node->isPublished() ? DraftRules::SKIP : DraftRules::UPDATE;
      return $this->answer($node, $status);
    }

    $action = DraftRules::action($node === NULL ? NULL : ($node->isPublished() ? 'published' : 'draft'));
    $title = mb_substr(DraftRules::title($article), 0, 255);
    $html = (string) ($article['html'] ?? '');
    $excerpt = (string) ($article['excerpt'] ?? '');
    $format = (string) ArticleRegistry::setting('text_format', 'basic_html');
    $log = sprintf('Tribune Desk send of %s', $sent_at ?? 'unknown time');

    if ($action === DraftRules::CREATE) {
      /** @var \Drupal\node\NodeInterface $node */
      $node = $this->entityTypeManager->getStorage('node')->create([
        'type' => (string) ArticleRegistry::setting('node_type', 'article'),
        'title' => $title,
        'body' => ['value' => $html, 'summary' => $excerpt, 'format' => $format],
        'uid' => (int) ArticleRegistry::setting('author_uid', 1),
        'status' => NodeInterface::NOT_PUBLISHED,
      ]);
      $node->setRevisionLogMessage($log);
      $node->save();
    }
    elseif ($action === DraftRules::UPDATE) {
      $current_summary = (string) ($node->get('body')->summary ?? '');
      $node->setTitle($title);
      $node->set('body', [
        'value' => $html,
        // An excerpt the editor wrote survives a new send.
        'summary' => DraftRules::fills_excerpt($excerpt, $current_summary) ? $excerpt : $current_summary,
        'format' => $node->get('body')->format ?: $format,
      ]);
      $node->setNewRevision(TRUE);
      $node->setRevisionLogMessage($log);
      $node->setRevisionCreationTime($this->time->getRequestTime());
      $node->save();
    }
    // DraftRules::SKIP: a published node keeps the newsroom's edits.

    // The main image is kept as its delivered URL only: this site does not
    // download photos (no media library integration).
    $image = $article['featured_image'] ?? NULL;
    $image_url = is_array($image) && is_string($image['url'] ?? NULL) ? $image['url'] : NULL;

    $this->registry->save($article_id, [
      'nid' => (int) $node->id(),
      'sent_at' => $sent_at,
      'sent_at_us' => max($sent_at_us ?? 0, (int) ($row->sent_at_us ?? 0)),
      'delivery_id' => $delivery_id ?? ($row->delivery_id ?? NULL),
      'image_url' => $image_url,
    ]);

    return $this->answer($node, $action);
  }

  protected function answer(NodeInterface $node, string $status): array {
    // permalink only for a public node (level 2): a draft has no address.
    return DeliveryAnswer::build(
      (string) $node->id(),
      $status,
      $this->registry->editUrl($node),
      $this->registry->permalink($node),
      NULL,
    );
  }

  /**
   * An ISO 8601 time as Unix microseconds, or NULL when it does not parse.
   */
  public static function microseconds(?string $iso): ?int {
    if ($iso === NULL || trim($iso) === '') {
      return NULL;
    }
    try {
      $date = new \DateTimeImmutable($iso);
    }
    catch (\Exception) {
      return NULL;
    }
    return (int) $date->format('U') * 1_000_000 + (int) $date->format('u');
  }

}
