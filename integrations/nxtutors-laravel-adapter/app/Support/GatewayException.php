<?php

declare(strict_types=1);

namespace NxTutors\DemoCommandCenterAdapter\Support;

use RuntimeException;

final class GatewayException extends RuntimeException
{
    /** @param array<string, mixed> $details */
    public function __construct(
        public readonly string $errorCode,
        public readonly int $status,
        public readonly array $details = [],
    ) {
        parent::__construct($errorCode);
    }
}
