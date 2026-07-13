<?php

declare(strict_types=1);

namespace NxTutors\DemoCommandCenterAdapter\Tests\Feature;

use Illuminate\Support\Facades\DB;
use NxTutors\DemoCommandCenterAdapter\Tests\TestCase;

final class AuthenticationTest extends TestCase
{
    public function testGatewayFailsClosedWhenDisabled(): void
    {
        config(['demo_command_center.enabled' => false]);
        $response = $this->signedRequest('GET', '/internal/api/v1/demo-command-center/plans', ['demo:plans:read']);
        self::assertSame(404, $response->getStatusCode());
        self::assertStringContainsString('GATEWAY_DISABLED', (string) $response->getContent());
    }

    public function testValidHmacAndScopeAreAcceptedAndAudited(): void
    {
        $response = $this->signedRequest(
            'GET',
            '/internal/api/v1/demo-command-center/identities/resolve?user_ref=student-1',
            ['demo:identity:read'],
        );
        self::assertSame(200, $response->getStatusCode(), (string) $response->getContent());
        self::assertSame('resolved', json_decode((string) $response->getContent(), true)['data']['status']);
        self::assertSame(1, DB::table('demo_gateway_audit_events')->count());
    }

    public function testInvalidSignatureIsRejected(): void
    {
        $response = $this->signedRequest(
            'GET',
            '/internal/api/v1/demo-command-center/plans',
            ['demo:plans:read'],
            extraHeaders: ['HTTP_X_NXTUTORS_SIGNATURE' => 'v1=' . str_repeat('0', 64)],
        );
        self::assertSame(401, $response->getStatusCode());
    }

    public function testExpiredTimestampIsRejected(): void
    {
        $response = $this->signedRequest(
            'GET',
            '/internal/api/v1/demo-command-center/plans',
            ['demo:plans:read'],
            timestamp: now()->subHour()->timestamp,
        );
        self::assertSame(401, $response->getStatusCode());
        self::assertStringContainsString('AUTH_TIMESTAMP_EXPIRED', (string) $response->getContent());
    }

    public function testNonceReplayIsRejectedDurably(): void
    {
        $nonce = 'nonce-replay-value-0000000001';
        $first = $this->signedRequest('GET', '/internal/api/v1/demo-command-center/plans', ['demo:plans:read'], nonce: $nonce);
        $second = $this->signedRequest('GET', '/internal/api/v1/demo-command-center/plans', ['demo:plans:read'], nonce: $nonce);
        self::assertSame(200, $first->getStatusCode());
        self::assertSame(409, $second->getStatusCode());
        self::assertStringContainsString('AUTH_REPLAY_DETECTED', (string) $second->getContent());
    }

    public function testMissingRequiredScopeIsRejected(): void
    {
        $response = $this->signedRequest('GET', '/internal/api/v1/demo-command-center/plans', ['demo:tutors:read']);
        self::assertSame(403, $response->getStatusCode());
        self::assertStringContainsString('AUTH_SCOPE_REQUIRED', (string) $response->getContent());
    }

    public function testUnknownQueryFieldIsRejected(): void
    {
        $response = $this->signedRequest(
            'GET',
            '/internal/api/v1/demo-command-center/identities/resolve?user_ref=student-1&unexpected=true',
            ['demo:identity:read'],
        );
        self::assertSame(422, $response->getStatusCode(), (string) $response->getContent());
        self::assertStringContainsString('unknown_fields', (string) $response->getContent());
    }
}
