<?php

declare(strict_types=1);

namespace Drupal\tribunedesk\Controller;

use Drupal\Core\DependencyInjection\ContainerInjectionInterface;
use Drupal\tribunedesk\ArticleRegistry;
use Drupal\tribunedesk\DeliveryHandler;
use Drupal\tribunedesk\Exception\LockBusyException;
use Psr\Log\LoggerInterface;
use Symfony\Component\DependencyInjection\ContainerInterface;
use Symfony\Component\HttpFoundation\JsonResponse;
use Symfony\Component\HttpFoundation\Request;
use TribuneDesk\Protocol\DeliveryAnswer;
use TribuneDesk\Protocol\WebhookSignature;

/**
 * Receives the article.delivered webhook (guide/1-article-delivery.md).
 *
 * Any 4xx ends a send for good, so 401 is answered only for a signature that
 * does not verify; our own trouble answers 5xx so Tribune Desk tries again.
 */
class WebhookController implements ContainerInjectionInterface {

  public function __construct(
    protected DeliveryHandler $handler,
    protected LoggerInterface $logger,
  ) {}

  public static function create(ContainerInterface $container): static {
    return new static(
      $container->get('tribunedesk.delivery_handler'),
      $container->get('logger.channel.tribunedesk'),
    );
  }

  public function receive(Request $request): JsonResponse {
    $secret = (string) ArticleRegistry::setting('secret', '');
    if (!WebhookSignature::is_valid_secret($secret)) {
      $this->logger->error('TD_WEBHOOK_SECRET is not set or is not a whsec_ secret; deliveries wait for it.');
      return new JsonResponse(['error' => 'not_configured'], 503, ['Retry-After' => '600']);
    }

    // Verify the raw bytes before any JSON parsing.
    $body = $request->getContent();
    if (!WebhookSignature::verify($secret, $request->headers->all(), $body)) {
      return new JsonResponse(['error' => 'invalid_signature'], 401);
    }

    $article = json_decode($body, TRUE);
    if (!is_array($article)) {
      $this->logger->error('A signed delivery had a body that is not a JSON object.');
      return new JsonResponse(['error' => 'invalid_body'], 400);
    }

    $delivery_id = $request->headers->get('X-Delivery-Id') ?? $request->headers->get('webhook-id');
    try {
      return new JsonResponse($this->handler->apply($article, $delivery_id), 200);
    }
    catch (LockBusyException $e) {
      // 503 is retried by Tribune Desk.
      $this->logger->warning($e->getMessage());
      return new JsonResponse(['error' => 'busy'], 503, ['Retry-After' => '30']);
    }
    catch (\InvalidArgumentException $e) {
      $this->logger->error('Delivery rejected: @message', ['@message' => $e->getMessage()]);
      return new JsonResponse(['error' => 'invalid_body'], 400);
    }
    catch (\Throwable $e) {
      $this->logger->error('Delivery failed: @message', ['@message' => (string) $e]);
      return new JsonResponse(DeliveryAnswer::internal_error(), 500);
    }
  }

}
