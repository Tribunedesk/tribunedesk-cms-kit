<?php

declare(strict_types=1);

namespace Drupal\Tests\tribunedesk\Kernel;

use Drupal\Core\Queue\DelayedRequeueException;
use Drupal\Core\Queue\SuspendQueueException;
use Drupal\KernelTests\KernelTestBase;
use Drupal\node\Entity\Node;
use Drupal\node\Entity\NodeType;
use Drupal\tribunedesk\LinkBackReporter;
use GuzzleHttp\Client;
use GuzzleHttp\Handler\MockHandler;
use GuzzleHttp\HandlerStack;
use GuzzleHttp\Middleware;
use GuzzleHttp\Psr7\Response;

/**
 * The link back after publishing (level 2, guide/2-link-back.md).
 *
 * @group tribunedesk
 */
class LinkBackTest extends KernelTestBase {

  protected const ARTICLE_ID = '3f2b8c1e-5d4a-4e6b-9c7d-1a2b3c4d5e6f';

  protected static $modules = ['system', 'user', 'node', 'field', 'text', 'filter', 'tribunedesk'];

  /**
   * Requests the mocked HTTP client sent.
   */
  protected array $history = [];

  protected MockHandler $responses;

  protected function setUp(): void {
    parent::setUp();
    $this->installEntitySchema('user');
    $this->installEntitySchema('node');
    $this->installSchema('node', ['node_access']);
    $this->installSchema('tribunedesk', ['tribunedesk_article']);
    $this->installConfig(['field', 'filter', 'node']);
    NodeType::create(['type' => 'article', 'name' => 'Article'])->save();
    $this->setSetting('tribunedesk', [
      'token' => 'tdcms_test',
      'api_base' => 'http://td.test',
      'site_url' => 'https://news.example.com',
    ]);

    $this->responses = new MockHandler();
    $stack = HandlerStack::create($this->responses);
    $stack->push(Middleware::history($this->history));
    $this->container->set('http_client', new Client(['handler' => $stack]));
  }

  public function testPublishingQueuesOneReport(): void {
    $node = $this->deliveredDraft();
    $this->assertSame(0, $this->queue()->numberOfItems());

    $node->setPublished()->save();
    $this->assertSame(1, $this->queue()->numberOfItems());

    $item = $this->queue()->claimItem();
    $this->assertSame(self::ARTICLE_ID, $item->data['article_id']);
    $this->assertSame("https://news.example.com/node/{$node->id()}", $item->data['url']);
  }

  public function testSendReportsAndRemembersTheAddress(): void {
    $node = $this->deliveredDraft();
    $node->setPublished()->save();
    $this->responses->append(new Response(200, [], json_encode(['results' => [['article_id' => self::ARTICLE_ID, 'status' => 'ok']]])));

    $results = $this->reporter()->processQueue();
    $this->assertSame([self::ARTICLE_ID => 'ok'], $results);
    $this->assertSame(0, $this->queue()->numberOfItems());

    $request = $this->history[0]['request'];
    $this->assertSame('http://td.test/v3/cms/articles/published', (string) $request->getUri());
    $this->assertSame('Bearer tdcms_test', $request->getHeaderLine('Authorization'));
    $body = json_decode((string) $request->getBody(), TRUE);
    $this->assertSame("https://news.example.com/node/{$node->id()}", $body['items'][0]['url']);

    // Saving again at the same address reports nothing new.
    Node::load($node->id())->save();
    $this->assertSame(0, $this->queue()->numberOfItems());
  }

  public function testNotFoundIsLoggedNotRetried(): void {
    $this->deliveredDraft()->setPublished()->save();
    $this->responses->append(new Response(200, [], json_encode(['results' => [['article_id' => self::ARTICLE_ID, 'status' => 'not_found']]])));
    $this->assertSame([self::ARTICLE_ID => 'not_found'], $this->reporter()->processQueue());
    $this->assertSame(0, $this->queue()->numberOfItems());
  }

  public function testUnavailableIsRetriedLater(): void {
    $this->responses->append(new Response(503, ['Retry-After' => '5'], json_encode(['code' => 'unavailable', 'message' => 'x', 'retry_after' => 45])));
    try {
      $this->reporter()->send(['article_id' => self::ARTICLE_ID, 'url' => 'https://news.example.com/node/1']);
      $this->fail('A 503 must be retried.');
    }
    catch (DelayedRequeueException $e) {
      $this->assertSame(45, $e->getDelay());
    }
  }

  public function testBadTokenKeepsTheQueue(): void {
    $this->responses->append(new Response(401, [], json_encode(['code' => 'unauthorized', 'message' => 'x'])));
    $this->expectException(SuspendQueueException::class);
    $this->reporter()->send(['article_id' => self::ARTICLE_ID, 'url' => 'https://news.example.com/node/1']);
  }

  protected function deliveredDraft(): Node {
    $node = Node::create(['type' => 'article', 'title' => 'Draft', 'status' => 0]);
    $node->save();
    $this->container->get('tribunedesk.registry')->save(self::ARTICLE_ID, ['nid' => (int) $node->id()]);
    return $node;
  }

  protected function reporter(): LinkBackReporter {
    return $this->container->get('tribunedesk.link_back');
  }

  protected function queue() {
    return $this->container->get('queue')->get(LinkBackReporter::QUEUE, TRUE);
  }

}
