<?php

declare(strict_types=1);

namespace Drupal\tribunedesk\EventSubscriber;

use Drupal\tribunedesk\LinkBackReporter;
use Symfony\Component\EventDispatcher\EventSubscriberInterface;
use Symfony\Component\HttpKernel\KernelEvents;

/**
 * Sends the link back queued by this request after the response went out,
 * so an editor's save never waits for Tribune Desk.
 */
class LinkBackTerminateSubscriber implements EventSubscriberInterface {

  public function __construct(protected LinkBackReporter $reporter) {}

  public static function getSubscribedEvents(): array {
    return [KernelEvents::TERMINATE => ['onTerminate', 0]];
  }

  public function onTerminate(): void {
    if ($this->reporter->hasQueuedThisRequest()) {
      $this->reporter->processQueue();
    }
  }

}
