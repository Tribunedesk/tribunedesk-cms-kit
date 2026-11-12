<?php

declare(strict_types=1);

namespace Drupal\tribunedesk\Plugin\QueueWorker;

use Drupal\Core\Plugin\ContainerFactoryPluginInterface;
use Drupal\Core\Queue\Attribute\QueueWorker;
use Drupal\Core\Queue\QueueWorkerBase;
use Drupal\Core\StringTranslation\TranslatableMarkup;
use Drupal\tribunedesk\LinkBackReporter;
use Symfony\Component\DependencyInjection\ContainerInterface;

/**
 * Retries link back reports on cron.
 */
#[QueueWorker(
  id: 'tribunedesk_link_back',
  title: new TranslatableMarkup('Tribune Desk link back'),
  cron: ['time' => 30],
)]
class LinkBackWorker extends QueueWorkerBase implements ContainerFactoryPluginInterface {

  public function __construct(array $configuration, $plugin_id, $plugin_definition, protected LinkBackReporter $reporter) {
    parent::__construct($configuration, $plugin_id, $plugin_definition);
  }

  public static function create(ContainerInterface $container, array $configuration, $plugin_id, $plugin_definition): static {
    return new static($configuration, $plugin_id, $plugin_definition, $container->get('tribunedesk.link_back'));
  }

  public function processItem($data): void {
    $this->reporter->send($data);
  }

}
