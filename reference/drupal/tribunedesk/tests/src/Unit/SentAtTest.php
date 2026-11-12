<?php

declare(strict_types=1);

namespace Drupal\Tests\tribunedesk\Unit;

use Drupal\Tests\UnitTestCase;
use Drupal\tribunedesk\DeliveryHandler;

/**
 * Ordering of sends by sent_at (guide/1-article-delivery.md, Order of sends).
 *
 * @group tribunedesk
 */
class SentAtTest extends UnitTestCase {

  public function testParsesIso8601WithFractionsAndZones(): void {
    $this->assertSame(1_793_782_800_000_000, DeliveryHandler::microseconds('2026-11-04T09:00:00+00:00'));
    $this->assertSame(1_793_782_800_250_000, DeliveryHandler::microseconds('2026-11-04T09:00:00.25Z'));
    // The same instant in another zone compares equal.
    $this->assertSame(
      DeliveryHandler::microseconds('2026-11-04T09:00:00+00:00'),
      DeliveryHandler::microseconds('2026-11-04T10:00:00+01:00'),
    );
  }

  public function testLaterSendIsGreaterWithinOneSecond(): void {
    $this->assertGreaterThan(
      DeliveryHandler::microseconds('2026-11-04T09:00:00.100Z'),
      DeliveryHandler::microseconds('2026-11-04T09:00:00.200Z'),
    );
  }

  public function testUnusableValuesGiveNull(): void {
    $this->assertNull(DeliveryHandler::microseconds(NULL));
    $this->assertNull(DeliveryHandler::microseconds(''));
    $this->assertNull(DeliveryHandler::microseconds('not a date'));
  }

}
