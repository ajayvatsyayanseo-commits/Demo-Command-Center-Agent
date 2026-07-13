<?php

declare(strict_types=1);

namespace NxTutors\DemoCommandCenterAdapter\Http\Controllers;

use Illuminate\Http\Request;
use NxTutors\DemoCommandCenterAdapter\Support\GatewayException;

trait ReadsIdempotencyKey
{
    private function idempotencyKey(Request $request): string
    {
        $key = (string) $request->header('Idempotency-Key', '');
        if (preg_match('/^[A-Za-z0-9][A-Za-z0-9._:-]{7,254}$/', $key) !== 1) {
            throw new GatewayException('IDEMPOTENCY_KEY_INVALID', 422);
        }

        return $key;
    }
}
