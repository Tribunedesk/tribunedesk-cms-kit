<?php

declare(strict_types=1);

namespace Drupal\Tests\tribunedesk\Kernel;

use Drupal\KernelTests\KernelTestBase;
use Drupal\node\Entity\Node;
use Drupal\node\Entity\NodeType;
use Drupal\tribunedesk\Controller\WebhookController;
use Symfony\Component\HttpFoundation\Request;

/**
 * The delivery webhook: signature, upsert and order of sends (level 1).
 *
 * @group tribunedesk
 */
class DeliveryTest extends KernelTestBase {

  protected const SECRET = 'whsec_dGVzdC1zZWNyZXQtZm9yLXRyaWJ1bmVkZXNrLWtlcm5lbA==';

  protected const ARTICLE_ID = '3f2b8c1e-5d4a-4e6b-9c7d-1a2b3c4d5e6f';

  protected static $modules = ['system', 'user', 'node', 'field', 'text', 'filter', 'tribunedesk'];

  protected function setUp(): void {
    parent::setUp();
    $this->installEntitySchema('user');
    $this->installEntitySchema('node');
    $this->installSchema('node', ['node_access']);
    $this->installSchema('tribunedesk', ['tribunedesk_article']);
    $this->installConfig(['field', 'filter', 'node']);
    NodeType::create(['type' => 'article', 'name' => 'Article'])->save();
    node_add_body_field(NodeType::load('article'));
    $this->setSetting('tribunedesk', [
      'secret' => self::SECRET,
      'site_url' => 'https://news.example.com',
    ]);
  }

  public function testBadSignatureIs401AndChangesNothing(): void {
    $request = $this->signedRequest($this->article('Title'), 'msg_1');
    $request->headers->set('webhook-signature', 'v1,' . base64_encode('wrong'));
    $this->assertSame(401, $this->receive($request)->getStatusCode());
    $this->assertSame([], Node::loadMultiple());
  }

  public function testOldTimestampIs401(): void {
    $request = $this->signedRequest($this->article('Title'), 'msg_1', time() - 301);
    $this->assertSame(401, $this->receive($request)->getStatusCode());
    $this->assertSame([], Node::loadMultiple());
  }

  public function testDeliveryMakesDraftAndAnswers(): void {
    $response = $this->receive($this->signedRequest($this->article('Zażółć gęślą jaźń', ['unknown_field' => 1]), 'msg_1'));
    $this->assertSame(200, $response->getStatusCode());
    $answer = json_decode((string) $response->getContent(), TRUE);
    $this->assertSame('created', $answer['status']);
    $this->assertSame("https://news.example.com/node/{$answer['cms_post_id']}/edit", $answer['edit_url']);
    $this->assertArrayNotHasKey('permalink', $answer);

    $node = Node::load($answer['cms_post_id']);
    $this->assertFalse($node->isPublished());
    $this->assertSame('Zażółć gęślą jaźń', $node->getTitle());
    $this->assertSame('<p>Body</p>', $node->get('body')->value);
    $this->assertSame('Excerpt', $node->get('body')->summary);
    $row = $this->container->get('tribunedesk.registry')->load(self::ARTICLE_ID);
    $this->assertSame('https://media.example.com/a.jpg', $row->image_url);
  }

  public function testRepeatAndResendUpdateTheSameNode(): void {
    $this->receive($this->signedRequest($this->article('First', [], '2026-11-04T09:00:00+00:00'), 'msg_1'));
    $this->receive($this->signedRequest($this->article('First', [], '2026-11-04T09:00:00+00:00'), 'msg_1'));
    $answer = json_decode((string) $this->receive($this->signedRequest($this->article('Second', [], '2026-11-04T09:05:00+00:00'), 'msg_2'))->getContent(), TRUE);
    $this->assertSame('updated', $answer['status']);
    $nodes = Node::loadMultiple();
    $this->assertCount(1, $nodes);
    $this->assertSame('Second', reset($nodes)->getTitle());
  }

  public function testOlderSendDoesNotOverwrite(): void {
    $this->receive($this->signedRequest($this->article('Newer', [], '2026-11-04T09:05:00+00:00'), 'msg_2'));
    $response = $this->receive($this->signedRequest($this->article('Older', [], '2026-11-04T09:00:00+00:00'), 'msg_1'));
    $this->assertSame(200, $response->getStatusCode());
    $nodes = Node::loadMultiple();
    $this->assertSame('Newer', reset($nodes)->getTitle());
  }

  public function testPublishedNodeKeepsNewsroomEdits(): void {
    $answer = json_decode((string) $this->receive($this->signedRequest($this->article('First', [], '2026-11-04T09:00:00+00:00'), 'msg_1'))->getContent(), TRUE);
    $node = Node::load($answer['cms_post_id']);
    $node->setTitle('Edited by the desk')->setPublished()->save();

    $answer = json_decode((string) $this->receive($this->signedRequest($this->article('Resent', [], '2026-11-04T09:10:00+00:00'), 'msg_3'))->getContent(), TRUE);
    $this->assertSame('skipped_already_published', $answer['status']);
    $this->assertSame("https://news.example.com/node/{$node->id()}", $answer['permalink']);
    $this->assertSame('Edited by the desk', Node::load($node->id())->getTitle());
  }

  /**
   * @param array<string, mixed> $extra
   */
  protected function article(string $title, array $extra = [], string $sent_at = '2026-11-04T09:00:00+00:00'): array {
    return [
      'article_id' => self::ARTICLE_ID,
      'org_code' => 'example-org',
      'sent_at' => $sent_at,
      'title' => $title,
      'html' => '<p>Body</p>',
      'excerpt' => 'Excerpt',
      'featured_image' => ['url' => 'https://media.example.com/a.jpg', 'asset_id' => 'x'],
    ] + $extra;
  }

  /**
   * A request signed as guide/1-article-delivery.md, Verifying the signature.
   */
  protected function signedRequest(array $article, string $id, ?int $timestamp = NULL): Request {
    $body = json_encode($article, JSON_UNESCAPED_UNICODE);
    $timestamp ??= time();
    $key = base64_decode(substr(self::SECRET, strlen('whsec_')));
    $signature = base64_encode(hash_hmac('sha256', "$id.$timestamp.$body", $key, TRUE));
    $request = Request::create('/td/webhook', 'POST', [], [], [], [], $body);
    $request->headers->add([
      'webhook-id' => $id,
      'webhook-timestamp' => (string) $timestamp,
      'webhook-signature' => "v1,$signature",
      'X-Delivery-Id' => $id,
      'Content-Type' => 'application/json',
    ]);
    return $request;
  }

  protected function receive(Request $request) {
    return WebhookController::create($this->container)->receive($request);
  }

}
