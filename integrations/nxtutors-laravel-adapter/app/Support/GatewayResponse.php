<?php

declare(strict_types=1);

namespace NxTutors\DemoCommandCenterAdapter\Support;

use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

final class GatewayResponse
{
    /** @param array<string, mixed> $data */
    public static function success(Request $request, array $data, int $status = 200): JsonResponse
    {
        return response()->json([
            'schema_version' => 'website-gateway.v1',
            'generated_at' => now()->utc()->toIso8601String(),
            'request_id' => (string) $request->attributes->get('dcc.request_id'),
            'data' => $data,
        ], $status);
    }

    /** @param array<string, mixed> $details */
    public static function error(Request $request, string $code, int $status, array $details = []): JsonResponse
    {
        $body = [
            'schema_version' => 'website-gateway.v1',
            'request_id' => (string) $request->attributes->get('dcc.request_id', ''),
            'error' => ['code' => $code],
        ];
        if ($details !== []) {
            $body['error']['details'] = $details;
        }

        return response()->json($body, $status);
    }
}
