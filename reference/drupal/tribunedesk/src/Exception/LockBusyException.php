<?php

declare(strict_types=1);

namespace Drupal\tribunedesk\Exception;

/**
 * Another attempt of the same article is still being written.
 */
class LockBusyException extends \RuntimeException {}
