<?php

declare(strict_types=1);

namespace Drupal\tribunedesk;

use Drupal\Component\Datetime\TimeInterface;
use Drupal\Core\Queue\DelayableQueueInterface;
use Drupal\Core\Queue\DelayedRequeueException;
use Drupal\Core\Queue\QueueFactory;
use Drupal\Core\Queue\RequeueException;
use Drupal\Core\Queue\SuspendQueueException;
use Drupal\node\NodeInterface;
use GuzzleHttp\ClientInterface;
use GuzzleHttp\Exception\GuzzleException;
use Psr\Log\LoggerInterface;
use TribuneDesk\Protocol\ApiErrors;
use TribuneDesk\Protocol\LinkBack;

/**
 * Tells Tribune Desk where delivered articles were published (level 2).
 *
 * Items go through the tribunedesk_link_back queue: they are sent right after
 * the response (see LinkBackTerminateSubscriber), and whatever fails with a
 * retryable error is retried by cron. Rules: guide/2-link-back.md and
 * README.md, Retries.
 */
class LinkBackReporter {

  public const QUEUE = 'tribunedesk_link_back';

  /**
   * Article ids queued during this request.
   *
   * @var array<string, true>
   */
  protected array $queued = [];

  public function __construct(
    protected ArticleRegistry $registry,
    protected ClientInterface $httpClient,
    protected QueueFactory $queueFactory,
    protected TimeInterface $time,
    protected LoggerInterface $logger,
  ) {}

  /**
   * Queues a report when a mapped node is public at an address not yet sent.
   */
  public function onNodeSaved(NodeInterface $node): void {
    $row = $this->registry->loadByNid((int) $node->id());
    $url = $this->registry->permalink($node);
    if ($row === NULL || $url === NULL || $url === $row->reported_url) {
      return;
    }
    $this->enqueue($row->article_id, $url);
  }

  /**
   * Queues a report of the node made from an article, whatever was sent before.
   */
  public function enqueueArticle(string $article_id): bool {
    $node = $this->registry->node($article_id);
    $url = $node ? $this->registry->permalink($node) : NULL;
    if ($url === NULL) {
      return FALSE;
    }
    if (!isset($this->queued[$article_id])) {
      $this->enqueue($article_id, $url);
    }
    return TRUE;
  }

  protected function enqueue(string $article_id, string $url): void {
    $this->queueFactory->get(self::QUEUE, TRUE)->createItem([
      'article_id' => $article_id,
      'url' => $url,
      'published_at' => gmdate('Y-m-d\TH:i:s+00:00', $this->time->getCurrentTime()),
    ]);
    $this->queued[$article_id] = TRUE;
  }

  public function hasQueuedThisRequest(): bool {
    return $this->queued !== [];
  }

  /**
   * Sends one report. Throws the queue exceptions so cron retries.
   *
   * @param array{article_id: string, url: string, published_at?: string} $item
   *
   * @return string
   *   The result Tribune Desk gave the item: ok, not_found, invalid_url, or
   *   dropped when it was not sent.
   */
  public function send(array $item): string {
    $token = (string) ArticleRegistry::setting('token', '');
    if ($token === '') {
      throw new SuspendQueueException('TD_CMS_TOKEN is not set; link back reports wait in the queue.');
    }
    [$items, $dropped] = LinkBack::prepare([$item]);
    if ($items === []) {
      $this->logger->warning('Link back item dropped (no UUID article_id or no URL): @item', ['@item' => json_encode($item)]);
      return 'dropped';
    }

    $api_base = rtrim((string) ArticleRegistry::setting('api_base', ArticleRegistry::DEFAULT_API_BASE), '/');
    try {
      $response = $this->httpClient->request('POST', $api_base . LinkBack::PATH, [
        'headers' => [
          'Authorization' => 'Bearer ' . $token,
          'Accept' => 'application/json',
        ],
        'json' => LinkBack::body($items),
        'timeout' => 15,
        'http_errors' => FALSE,
      ]);
    }
    catch (GuzzleException $e) {
      throw new DelayedRequeueException(60, 'Link back network error: ' . $e->getMessage());
    }

    $status = $response->getStatusCode();
    $body = (string) $response->getBody();
    $decoded = json_decode($body, TRUE);

    if ($status >= 200 && $status < 300) {
      $article_id = $items[0]['article_id'];
      $result = LinkBack::results($body)[$article_id] ?? 'invalid_response';
      if ($result === 'ok') {
        $this->registry->markReported($article_id, $items[0]['url']);
      }
      else {
        // Logged, not retried unchanged (guide/2-link-back.md, Done when).
        $this->logger->warning('Link back of @id answered @result.', ['@id' => $article_id, '@result' => $result]);
      }
      return $result;
    }

    $code = ApiErrors::code($status, $decoded);
    if (in_array($status, [429, 500, 502, 503, 504], TRUE)) {
      $wait = max(ApiErrors::retry_after($decoded) ?? (int) $response->getHeaderLine('Retry-After'), 30);
      throw new DelayedRequeueException($wait, "Link back answered $status $code; retrying.");
    }
    if (in_array($status, [401, 403], TRUE)) {
      // A token problem: keep the reports until the token is fixed.
      throw new SuspendQueueException("Link back answered $status $code; check TD_CMS_TOKEN and its articles:write scope.");
    }
    $this->logger->error('Link back of @id refused: @status @code.', ['@id' => $items[0]['article_id'], '@status' => $status, '@code' => $code]);
    return $code;
  }

  /**
   * Processes up to $limit queued reports now.
   *
   * @return array<string, string>
   *   article_id => result, for the items handled.
   */
  public function processQueue(int $limit = 20): array {
    $queue = $this->queueFactory->get(self::QUEUE, TRUE);
    $results = [];
    // Every failure stops the run, so an item released for a retry is not
    // claimed again here; cron picks it up later.
    while ($limit-- > 0 && ($item = $queue->claimItem(60))) {
      try {
        $results[$item->data['article_id'] ?? ''] = $this->send($item->data);
        $queue->deleteItem($item);
      }
      catch (DelayedRequeueException $e) {
        $this->logger->warning($e->getMessage());
        $results[$item->data['article_id'] ?? ''] = 'retry_later';
        $queue instanceof DelayableQueueInterface ? $queue->delayItem($item, $e->getDelay()) : $queue->releaseItem($item);
        break;
      }
      catch (SuspendQueueException | RequeueException $e) {
        $this->logger->error($e->getMessage());
        $results[$item->data['article_id'] ?? ''] = 'retry_later';
        $queue->releaseItem($item);
        break;
      }
      catch (\Throwable $e) {
        $this->logger->error('Link back failed: @message', ['@message' => (string) $e]);
        $results[$item->data['article_id'] ?? ''] = 'retry_later';
        $queue->releaseItem($item);
        break;
      }
    }
    return $results;
  }

}
