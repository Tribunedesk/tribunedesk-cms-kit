<?php

declare(strict_types=1);

namespace Drupal\Tests\tribunedesk\Unit;

use Drupal\Tests\UnitTestCase;
use Drupal\tribunedesk\DeliveryHandler;

/**
 * Publication mode of a delivery (guide/1-article-delivery.md, contract 3.7).
 *
 * @group tribunedesk
 */
class PublicationTargetTest extends UnitTestCase {

  private const NOW = 1_800_000_000;

  public function testModes(): void {
    $at = '2027-01-16T08:00:00Z';
    $schedule = ['mode' => 'schedule', 'at' => $at];
    foreach ([NULL, 'draft', 'future'] as $state) {
      $this->assertSame(['status' => 'future', 'at' => self::NOW + 86_400], DeliveryHandler::publicationTarget($state, $schedule, self::NOW));
      $this->assertSame(['status' => 'draft', 'at' => NULL], DeliveryHandler::publicationTarget($state, ['mode' => 'draft'], self::NOW));
      $this->assertSame(['status' => 'publish', 'at' => NULL], DeliveryHandler::publicationTarget($state, ['mode' => 'publish'], self::NOW));
      $this->assertSame(['status' => 'keep', 'at' => NULL], DeliveryHandler::publicationTarget($state, NULL, self::NOW));
    }
  }

  public function testPublishedNodeIsNeverChanged(): void {
    foreach ([['mode' => 'draft'], ['mode' => 'schedule', 'at' => '2027-01-16T08:00:00Z']] as $publication) {
      $this->assertSame(['status' => 'keep', 'at' => NULL], DeliveryHandler::publicationTarget('publish', $publication, self::NOW));
    }
  }

  public function testPastTimeIsPublishedAtOnceAndUnreadableIsIgnored(): void {
    $past = ['mode' => 'schedule', 'at' => '2027-01-15T07:00:00+00:00'];
    $this->assertSame(['status' => 'publish', 'at' => NULL], DeliveryHandler::publicationTarget('draft', $past, self::NOW));
    foreach ([['mode' => 'later'], ['mode' => 'schedule'], ['mode' => 'schedule', 'at' => '2027-01-16T08:00:00']] as $bad) {
      $this->assertSame(['status' => 'keep', 'at' => NULL], DeliveryHandler::publicationTarget('draft', $bad, self::NOW));
    }
  }

}
