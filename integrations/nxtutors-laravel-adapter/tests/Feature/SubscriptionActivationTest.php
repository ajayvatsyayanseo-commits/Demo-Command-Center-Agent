<?php

declare(strict_types=1);

namespace NxTutors\DemoCommandCenterAdapter\Tests\Feature;

use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use NxTutors\DemoCommandCenterAdapter\Tests\TestCase;

final class SubscriptionActivationTest extends TestCase
{
    public function testVerifiedBindingActivatesExactlyOnceAndWritesOneOutboxEvent(): void
    {
        $payload = $this->activationPayload();
        $path = '/internal/api/v1/demo-command-center/subscriptions/activations';
        $first = $this->signedRequest('POST', $path, ['demo:subscription:write'], $payload, 'activation-operation-0001');
        $second = $this->signedRequest('POST', $path, ['demo:subscription:write'], $payload, 'activation-operation-0001');

        self::assertSame(201, $first->getStatusCode(), (string) $first->getContent());
        self::assertSame(201, $second->getStatusCode(), (string) $second->getContent());
        self::assertSame('true', $second->headers->get('X-Idempotency-Replayed'));
        self::assertSame(1, DB::table('user_subscriptions')->count());
        self::assertSame(1, DB::table('demo_subscription_activations')->count());
        self::assertSame(1, DB::table('demo_integration_outbox')->count());
        self::assertSame('paid', DB::table('user_subscriptions')->value('payment_status'));
    }

    public function testAmountMismatchFailsClosedWithoutMutation(): void
    {
        $payload = $this->activationPayload();
        ++$payload['amount_minor'];
        $response = $this->signedRequest(
            'POST',
            '/internal/api/v1/demo-command-center/subscriptions/activations',
            ['demo:subscription:write'],
            $payload,
            'activation-operation-0002',
        );

        self::assertSame(409, $response->getStatusCode(), (string) $response->getContent());
        self::assertStringContainsString('PAYMENT_PLAN_BINDING_MISMATCH', (string) $response->getContent());
        self::assertSame(0, DB::table('user_subscriptions')->count());
        self::assertSame(0, DB::table('demo_subscription_activations')->count());
    }

    public function testProviderOrderCannotActivateASecondDemo(): void
    {
        $firstPayload = $this->activationPayload();
        $first = $this->signedRequest(
            'POST',
            '/internal/api/v1/demo-command-center/subscriptions/activations',
            ['demo:subscription:write'],
            $firstPayload,
            'activation-operation-0003-a',
        );
        $secondPayload = $firstPayload;
        $secondPayload['demo_ref'] = 'demo-paid-0002';
        $second = $this->signedRequest(
            'POST',
            '/internal/api/v1/demo-command-center/subscriptions/activations',
            ['demo:subscription:write'],
            $secondPayload,
            'activation-operation-0003-b',
        );

        self::assertSame(201, $first->getStatusCode(), (string) $first->getContent());
        self::assertSame(409, $second->getStatusCode(), (string) $second->getContent());
        self::assertSame(1, DB::table('user_subscriptions')->count());
        self::assertSame(1, DB::table('demo_subscription_activations')->count());
    }

    public function testActivationFailsClosedWhenWebsiteStatusPolicyIsUnconfigured(): void
    {
        config(['demo_command_center.activation.active_status' => '']);
        $response = $this->signedRequest(
            'POST',
            '/internal/api/v1/demo-command-center/subscriptions/activations',
            ['demo:subscription:write'],
            $this->activationPayload(),
            'activation-operation-0004',
        );
        self::assertSame(503, $response->getStatusCode(), (string) $response->getContent());
        self::assertSame(0, DB::table('user_subscriptions')->count());
    }

    /** @return array<string, mixed> */
    private function activationPayload(): array
    {
        $quote = $this->signedRequest(
            'GET',
            '/internal/api/v1/demo-command-center/plans/10/quote?user_ref=student-1',
            ['demo:plans:read'],
        );
        self::assertSame(200, $quote->getStatusCode(), (string) $quote->getContent());
        $plan = json_decode((string) $quote->getContent(), true, 32, JSON_THROW_ON_ERROR)['data'];

        return [
            'demo_ref' => 'demo-paid-0001',
            'website_user_ref' => 'student-1',
            'plan_id' => 10,
            'plan_version' => $plan['plan_version'],
            'amount_minor' => $plan['amount_minor'],
            'currency' => $plan['currency'],
            'provider_order_ref' => 'cashfree-order-0001',
            'payment_evidence_ref' => 'cashfree-evidence-0001',
            'payment_verified_at' => now()->utc()->toIso8601String(),
            'correlation_id' => (string) Str::uuid(),
        ];
    }
}
