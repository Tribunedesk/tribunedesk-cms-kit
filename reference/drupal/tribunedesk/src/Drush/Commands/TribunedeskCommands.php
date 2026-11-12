<?php

declare(strict_types=1);

namespace Drupal\tribunedesk\Drush\Commands;

use Drupal\tribunedesk\ArticleRegistry;
use Drupal\tribunedesk\LinkBackReporter;
use Drush\Attributes as CLI;
use Drush\Commands\DrushCommands;
use Symfony\Component\DependencyInjection\ContainerInterface;

/**
 * Developer commands used by `tdkit check` (and handy when debugging).
 */
final class TribunedeskCommands extends DrushCommands {

  public function __construct(
    protected ArticleRegistry $registry,
    protected LinkBackReporter $linkBack,
  ) {
    parent::__construct();
  }

  public static function create(ContainerInterface $container): self {
    return new self(
      $container->get('tribunedesk.registry'),
      $container->get('tribunedesk.link_back'),
    );
  }

  /**
   * Prints the node made from a Tribune Desk article as JSON, or null.
   */
  #[CLI\Command(name: 'td:inspect')]
  #[CLI\Argument(name: 'article_id', description: 'Tribune Desk article_id.')]
  public function inspect(string $article_id): void {
    $article_id = strtolower(trim($article_id));
    $node = $this->registry->node($article_id);
    $data = NULL;
    if ($node !== NULL) {
      $row = $this->registry->load($article_id);
      $body = $node->get('body');
      $data = [
        'cms_post_id' => (string) $node->id(),
        'title' => $node->getTitle(),
        'html' => (string) $body->value,
        'excerpt' => (string) $body->summary,
        'status' => $node->isPublished() ? 'published' : 'draft',
        'featured_image_url' => $row->image_url ?? NULL,
        'permalink' => $this->registry->permalink($node),
        'edit_url' => $this->registry->editUrl($node),
      ];
    }
    $this->output()->writeln(json_encode($data, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES));
  }

  /**
   * Publishes the node made from an article, as an editor would, and reports
   * its address to Tribune Desk.
   */
  #[CLI\Command(name: 'td:publish')]
  #[CLI\Argument(name: 'article_id', description: 'Tribune Desk article_id.')]
  public function publish(string $article_id): int {
    $article_id = strtolower(trim($article_id));
    $node = $this->registry->node($article_id);
    if ($node === NULL) {
      $this->logger()->error("No node for article $article_id.");
      return self::EXIT_FAILURE;
    }
    if (!$node->isPublished()) {
      $node->setPublished();
      $node->setNewRevision(TRUE);
      $node->setRevisionLogMessage('Published (drush td:publish)');
      // hook_node_update() queues the report.
      $node->save();
    }
    // Report again even when nothing changed: a repeat is harmless.
    $this->linkBack->enqueueArticle($article_id);
    $results = $this->linkBack->processQueue();
    $result = $results[$article_id] ?? 'not_sent';
    $this->logger()->notice("Link back of $article_id: $result");
    return $result === 'ok' ? self::EXIT_SUCCESS : self::EXIT_FAILURE;
  }

}
