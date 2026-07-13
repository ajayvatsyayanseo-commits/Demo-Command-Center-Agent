<?php

declare(strict_types=1);

namespace NxTutors\DemoCommandCenterAdapter\Application;

final readonly class IdempotencyResult
{
    /** @param array<string, mixed> $body */
    public function __construct(
        public array $body,
        public int $status,
        public bool $replayed,
    ) {}
}
