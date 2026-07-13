<?php

declare(strict_types=1);

namespace NxTutors\DemoCommandCenterAdapter\Tests\Feature;

use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use NxTutors\DemoCommandCenterAdapter\Tests\TestCase;

final class DemoProjectionTest extends TestCase
{
    public function testProjectionMutationIsVersionedIdempotentAndWritesOutbox(): void
    {
        $payload = [
            'expected_version' => 0,
            'demo_lead_ref' => 101,
            'website_user_ref' => 'student-1',
            'lifecycle_state' => 'intake',
            'occurred_at' => now()->utc()->toIso8601String(),
            'correlation_id' => (string) Str::uuid(),
        ];
        $path = '/internal/api/v1/demo-command-center/demos/demo-projection-0001/projection';
        $first = $this->signedRequest('PUT', $path, ['demo:projection:write'], $payload, 'projection-operation-0001');
        $second = $this->signedRequest('PUT', $path, ['demo:projection:write'], $payload, 'projection-operation-0001');

        self::assertSame(201, $first->getStatusCode(), (string) $first->getContent());
        self::assertSame(201, $second->getStatusCode(), (string) $second->getContent());
        self::assertSame('true', $second->headers->get('X-Idempotency-Replayed'));
        self::assertSame(1, DB::table('demo_website_projections')->count());
        self::assertSame(1, DB::table('demo_integration_outbox')->count());
    }

    public function testIdempotencyKeyCannotBeReusedWithDifferentProjection(): void
    {
        $payload = [
            'expected_version' => 0,
            'lifecycle_state' => 'intake',
            'occurred_at' => now()->utc()->toIso8601String(),
            'correlation_id' => (string) Str::uuid(),
        ];
        $path = '/internal/api/v1/demo-command-center/demos/demo-projection-0002/projection';
        $first = $this->signedRequest('PUT', $path, ['demo:projection:write'], $payload, 'projection-operation-0002');
        $payload['lifecycle_state'] = 'scheduled';
        $second = $this->signedRequest('PUT', $path, ['demo:projection:write'], $payload, 'projection-operation-0002');

        self::assertSame(201, $first->getStatusCode());
        self::assertSame(409, $second->getStatusCode());
        self::assertStringContainsString('IDEMPOTENCY_KEY_REUSED', (string) $second->getContent());
    }

    public function testOptimisticVersionConflictDoesNotWriteASecondOutboxEvent(): void
    {
        $correlation = (string) Str::uuid();
        $path = '/internal/api/v1/demo-command-center/demos/demo-projection-0003/projection';
        $base = [
            'expected_version' => 0,
            'lifecycle_state' => 'intake',
            'occurred_at' => now()->utc()->toIso8601String(),
            'correlation_id' => $correlation,
        ];
        $this->signedRequest('PUT', $path, ['demo:projection:write'], $base, 'projection-operation-0003-a');
        $conflict = $this->signedRequest('PUT', $path, ['demo:projection:write'], $base, 'projection-operation-0003-b');

        self::assertSame(409, $conflict->getStatusCode());
        self::assertSame(1, DB::table('demo_integration_outbox')->count());
    }

    public function testOnboardingStatusIsIdempotentlyProjected(): void
    {
        $correlation = (string) Str::uuid();
        $projectionPath = '/internal/api/v1/demo-command-center/demos/demo-projection-0004/projection';
        $this->signedRequest('PUT', $projectionPath, ['demo:projection:write'], [
            'expected_version' => 0,
            'lifecycle_state' => 'paid',
            'occurred_at' => now()->utc()->toIso8601String(),
            'correlation_id' => $correlation,
        ], 'projection-operation-0004');
        $path = '/internal/api/v1/demo-command-center/demos/demo-projection-0004/onboarding-status';
        $payload = ['status' => 'accepted', 'onboarding_ref' => 'onboarding-0004', 'correlation_id' => $correlation];
        $first = $this->signedRequest('POST', $path, ['demo:onboarding:write'], $payload, 'onboarding-operation-0004');
        $second = $this->signedRequest('POST', $path, ['demo:onboarding:write'], $payload, 'onboarding-operation-0004');

        self::assertSame(200, $first->getStatusCode(), (string) $first->getContent());
        self::assertSame(200, $second->getStatusCode());
        self::assertSame('accepted', DB::table('demo_website_projections')->value('onboarding_status'));
        self::assertSame(2, DB::table('demo_integration_outbox')->count());
    }
}
