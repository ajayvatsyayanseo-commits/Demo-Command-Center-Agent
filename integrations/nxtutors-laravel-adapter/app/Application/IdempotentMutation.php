<?php

declare(strict_types=1);

namespace NxTutors\DemoCommandCenterAdapter\Application;

use Closure;
use Illuminate\Support\Facades\DB;
use NxTutors\DemoCommandCenterAdapter\Support\GatewayException;

final class IdempotentMutation
{
    /**
     * @param Closure(): array{body: array<string, mixed>, status: int} $mutation
     */
    public function execute(string $scope, string $key, string $requestHash, Closure $mutation): IdempotencyResult
    {
        return DB::transaction(function () use ($scope, $key, $requestHash, $mutation): IdempotencyResult {
            $existing = DB::table('demo_gateway_idempotency')
                ->where('operation_scope', $scope)
                ->where('idempotency_key', $key)
                ->lockForUpdate()
                ->first();
            if ($existing !== null) {
                if (! hash_equals((string) $existing->request_hash, $requestHash)) {
                    throw new GatewayException('IDEMPOTENCY_KEY_REUSED', 409);
                }
                if ((string) $existing->state !== 'completed' || $existing->response_body === null) {
                    throw new GatewayException('IDEMPOTENCY_OPERATION_IN_PROGRESS', 409);
                }
                $body = json_decode((string) $existing->response_body, true, 32, JSON_THROW_ON_ERROR);
                if (! is_array($body)) {
                    throw new GatewayException('IDEMPOTENCY_RECORD_INVALID', 503);
                }

                return new IdempotencyResult($body, (int) $existing->response_status, true);
            }

            $now = now()->utc();
            DB::table('demo_gateway_idempotency')->insert([
                'operation_scope' => $scope,
                'idempotency_key' => $key,
                'request_hash' => $requestHash,
                'state' => 'processing',
                'expires_at' => $now->copy()->addHours(
                    max(1, (int) config('demo_command_center.idempotency_retention_hours', 168)),
                ),
                'created_at' => $now,
                'updated_at' => $now,
            ]);

            $result = $mutation();
            DB::table('demo_gateway_idempotency')
                ->where('operation_scope', $scope)
                ->where('idempotency_key', $key)
                ->update([
                    'state' => 'completed',
                    'response_status' => $result['status'],
                    'response_body' => json_encode($result['body'], JSON_THROW_ON_ERROR),
                    'updated_at' => now()->utc(),
                ]);

            return new IdempotencyResult($result['body'], $result['status'], false);
        }, 3);
    }
}
