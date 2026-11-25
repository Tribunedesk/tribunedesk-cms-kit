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

  /**
   * Players whose iframes stay (guide/1-article-delivery.md, The HTML body,
   * Embeds). Each prefix ends with "/", so a look-alike host does not pass.
   */
  public const TRUSTED_PLAYERS = [
    'https://www.youtube.com/embed/',
    'https://player.vimeo.com/video/',
  ];

  /**
   * Drops every script (with its content) but the AI label block, and every
   * iframe whose src is not a trusted player.
   *
   * The text format filters on output, but a delivery is stored as sent and
   * arrives with no user logged in; this keeps the stored body clean. The
   * text format must allow <iframe src width height title allow
   * allowfullscreen frameborder> for the trusted players to show.
   */
  public static function filterEmbeds(string $html): string {
    $html = preg_replace_callback(
      '#<script\b([^>]*)>.*?</script>#is',
      static fn (array $m): string => str_contains($m[1], 'data-hf-provenance') ? $m[0] : '',
      $html,
    ) ?? '';
    return preg_replace_callback(
      '#<iframe\b[^>]*\bsrc=["\']([^"\']*)["\'][^>]*>.*?</iframe>#is',
      static function (array $m): string {
        foreach (self::TRUSTED_PLAYERS as $prefix) {
          if (str_starts_with($m[1], $prefix)) {
            return $m[0];
          }
        }
        return '';
      },
      $html,
    ) ?? '';
  }

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
      return $this->answer($node, $status, self::publishAt($row));
    }

    $action = DraftRules::action($node === NULL ? NULL : ($node->isPublished() ? 'published' : 'draft'));
    $title = mb_substr(DraftRules::title($article), 0, 255);
    $html = self::filterEmbeds((string) ($article['html'] ?? ''));
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

    // Publication mode (contract 3.7): a draft, a node scheduled for `at`, or
    // one published now. A scheduled node is unpublished with publish_at set,
    // so a new send updates it like a draft; hook_cron() publishes it.
    $publish_at = $row !== NULL ? self::publishAt($row) : NULL;
    $state = $node->isPublished() ? 'publish' : ($publish_at !== NULL ? 'future' : 'draft');
    $target = self::publicationTarget($action === DraftRules::CREATE ? NULL : $state, $article['publication'] ?? NULL, $this->time->getCurrentTime());
    if ($target['status'] !== 'keep') {
      $publish_at = $target['at'];
    }

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
      'publish_at' => $publish_at,
    ]);

    if ($target['status'] === 'publish' && !$node->isPublished()) {
      // After the row is saved, so hook_node_update() finds the article and
      // reports the address (level 2).
      $node->setPublished();
      $node->setNewRevision(TRUE);
      $node->setRevisionLogMessage('Published by the Tribune Desk publication mode');
      $node->save();
    }

    return $this->answer($node, $action, $publish_at);
  }

  protected function answer(NodeInterface $node, string $status, ?int $publish_at): array {
    // permalink only for a public node (level 2): a draft has no address.
    $answer = DeliveryAnswer::build(
      (string) $node->id(),
      $status,
      $this->registry->editUrl($node),
      $this->registry->permalink($node),
      NULL,
    );
    // The state of the node after this delivery (contract 3.7).
    if ($node->isPublished()) {
      // Drupal core keeps no publication moment of its own.
      $answer['publication'] = ['status' => 'published', 'at' => NULL];
    }
    elseif ($publish_at !== NULL) {
      $answer['publication'] = ['status' => 'scheduled', 'at' => gmdate('Y-m-d\TH:i:s\Z', $publish_at)];
    }
    else {
      $answer['publication'] = ['status' => 'draft', 'at' => NULL];
    }
    return $answer;
  }

  /**
   * The status a delivery's `publication` gives a node (contract 3.7).
   *
   * States are WordPress's words, as in TribuneDesk\Protocol: NULL (a new
   * node), `draft`, `future` (scheduled) and `publish`. A published node is
   * never changed; a field that cannot be read is ignored, like any field this
   * module does not know; a time already past is published at once.
   *
   * @return array{status: string, at: int|null}
   *   `status` is `draft`, `future`, `publish` or `keep`.
   */
  public static function publicationTarget(?string $state, mixed $publication, int $now): array {
    $keep = ['status' => 'keep', 'at' => NULL];
    if ($state === 'publish' || !is_array($publication)) {
      return $keep;
    }
    $mode = $publication['mode'] ?? NULL;
    if ($mode === 'draft' || $mode === 'publish') {
      return ['status' => $mode, 'at' => NULL];
    }
    $at = $mode === 'schedule' ? self::instant($publication['at'] ?? NULL) : NULL;
    if ($at === NULL) {
      return $keep;
    }
    return $at > $now ? ['status' => 'future', 'at' => $at] : ['status' => 'publish', 'at' => NULL];
  }

  /**
   * Publishes the scheduled nodes whose time has come (hook_cron()).
   */
  public function publishDue(): int {
    $due = $this->database->select(ArticleRegistry::TABLE, 't')
      ->fields('t', ['article_id'])
      ->condition('publish_at', $this->time->getCurrentTime(), '<=')
      ->execute()
      ->fetchCol();
    foreach ($due as $article_id) {
      $node = $this->registry->node((string) $article_id);
      $this->registry->save((string) $article_id, ['publish_at' => NULL]);
      if ($node !== NULL && !$node->isPublished()) {
        $node->setPublished();
        $node->setNewRevision(TRUE);
        $node->setRevisionLogMessage('Published at the time Tribune Desk scheduled');
        $node->save();
      }
    }
    return count($due);
  }

  protected static function publishAt(object $row): ?int {
    return isset($row->publish_at) && $row->publish_at !== '' ? (int) $row->publish_at : NULL;
  }

  /**
   * An ISO 8601 moment with an offset (`Z` or `+01:00`) as Unix time, or NULL.
   */
  protected static function instant(mixed $value): ?int {
    if (!is_string($value) || !preg_match('/(Z|[+-]\d{2}:?\d{2})$/', $value)) {
      return NULL;
    }
    $us = self::microseconds($value);
    return $us === NULL ? NULL : intdiv($us, 1_000_000);
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
