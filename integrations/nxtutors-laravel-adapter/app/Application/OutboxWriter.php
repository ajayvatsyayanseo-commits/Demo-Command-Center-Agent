<?php

declare(strict_types=1);

namespace NxTutors\DemoCommandCenterAdapter\Application;

use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;

final class OutboxWriter
{
    /** @param array<string, mixed> $payload */
    public function append(
        string $eventType,
        string $idempotencyKey,
        string $correlationId,
        array $payload,
    ): string {
        $eventId = (string) Str::uuid();
        $now = now()->utc();
        DB::table('demo_integration_outbox')->insert([
            'event_id' => $eventId,
            'event_type' => $eventType,
            'schema_version' => '1.0',
            'idempotency_key' => $idempotencyKey,
            'correlation_id' => $correlationId,
            'payload' => json_encode($payload, JSON_THROW_ON_ERROR),
            'occurred_at' => $now,
            'available_at' => $now,
            'attempts' => 0,
            'created_at' => $now,
            'updated_at' => $now,
        ]);

        return $eventId;
    }
}
