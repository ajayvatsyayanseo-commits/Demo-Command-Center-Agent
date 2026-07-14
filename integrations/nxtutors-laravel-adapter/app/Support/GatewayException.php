<?php

declare(strict_types=1);

namespace NxTutors\DemoCommandCenterAdapter\Support;

use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
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

    public function render(Request $request): JsonResponse
    {
        return GatewayResponse::error($request, $this->errorCode, $this->status, $this->details);
    }

    public function report(): bool
    {
        return false;
    }
}
