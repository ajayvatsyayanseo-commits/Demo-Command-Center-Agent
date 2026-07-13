<?php

declare(strict_types=1);

namespace NxTutors\DemoCommandCenterAdapter\Application;

use Illuminate\Support\Facades\DB;
use NxTutors\DemoCommandCenterAdapter\Support\GatewayException;
use NxTutors\DemoCommandCenterAdapter\Support\RequestHash;

final class DemoProjectionService
{
    private const STATES = [
        'intake', 'requirements_complete', 'tutor_shortlisted', 'slot_proposed', 'slot_held',
        'awaiting_confirmation', 'scheduled', 'reschedule_pending', 'cancelled', 'completed',
        'no_show', 'conversion_pending', 'payment_pending', 'paid', 'onboarding_handoff',
        'onboarding_complete', 'human_handoff', 'failed',
    ];

    public function __construct(
        private readonly IdempotentMutation $idempotency,
        private readonly OutboxWriter $outbox,
    ) {}

    /** @param array<string, mixed> $payload */
    public function update(string $demoRef, string $key, array $payload): IdempotencyResult
    {
        if (! in_array($payload['lifecycle_state'], self::STATES, true)) {
            throw new GatewayException('LIFECYCLE_STATE_INVALID', 422);
        }
        $hash = RequestHash::of(['demo_ref' => $demoRef] + $payload);

        return $this->idempotency->execute("demo_projection:{$demoRef}", $key, $hash, function () use ($demoRef, $key, $payload): array {
            $existing = DB::table('demo_website_projections')->where('demo_ref', $demoRef)->lockForUpdate()->first();
            $expected = (int) $payload['expected_version'];
            if ($existing === null && $expected !== 0) {
                throw new GatewayException('PROJECTION_VERSION_CONFLICT', 409, ['current_version' => 0]);
            }
            if ($existing !== null && (int) $existing->projection_version !== $expected) {
                throw new GatewayException('PROJECTION_VERSION_CONFLICT', 409, [
                    'current_version' => (int) $existing->projection_version,
                ]);
            }
            $version = $expected + 1;
            $now = now()->utc();
            $values = [
                'demo_ref' => $demoRef,
                'demo_lead_id' => $payload['demo_lead_ref'] ?? null,
                'website_user_ref' => $payload['website_user_ref'] ?? null,
                'lifecycle_state' => $payload['lifecycle_state'],
                'projection_version' => $version,
                'correlation_id' => $payload['correlation_id'],
                'state_occurred_at' => $payload['occurred_at'],
                'updated_at' => $now,
            ];
            if ($existing === null) {
                $values['created_at'] = $now;
                DB::table('demo_website_projections')->insert($values);
            } else {
                DB::table('demo_website_projections')->where('demo_ref', $demoRef)->update($values);
            }
            $eventId = $this->outbox->append(
                'website.demo_projection.updated.v1',
                'demo-projection|' . hash('sha256', $key),
                (string) $payload['correlation_id'],
                [
                    'demo_ref' => $demoRef,
                    'website_user_ref' => $payload['website_user_ref'] ?? null,
                    'lifecycle_state' => $payload['lifecycle_state'],
                    'projection_version' => $version,
                ],
            );

            return ['status' => $existing === null ? 201 : 200, 'body' => [
                'demo_ref' => $demoRef,
                'projection_version' => $version,
                'lifecycle_state' => $payload['lifecycle_state'],
                'outbox_event_id' => $eventId,
            ]];
        });
    }

    /** @param array<string, mixed> $payload */
    public function onboarding(string $demoRef, string $key, array $payload): IdempotencyResult
    {
        $hash = RequestHash::of(['demo_ref' => $demoRef] + $payload);

        return $this->idempotency->execute("onboarding_projection:{$demoRef}", $key, $hash, function () use ($demoRef, $key, $payload): array {
            $projection = DB::table('demo_website_projections')->where('demo_ref', $demoRef)->lockForUpdate()->first();
            if ($projection === null) {
                throw new GatewayException('DEMO_PROJECTION_NOT_FOUND', 404);
            }
            DB::table('demo_website_projections')->where('demo_ref', $demoRef)->update([
                'onboarding_status' => $payload['status'],
                'onboarding_ref' => $payload['onboarding_ref'] ?? null,
                'updated_at' => now()->utc(),
            ]);
            $eventId = $this->outbox->append(
                'website.onboarding_status.recorded.v1',
                'onboarding-status|' . hash('sha256', $key),
                (string) $payload['correlation_id'],
                [
                    'demo_ref' => $demoRef,
                    'status' => $payload['status'],
                    'onboarding_ref' => $payload['onboarding_ref'] ?? null,
                ],
            );

            return ['status' => 200, 'body' => [
                'demo_ref' => $demoRef,
                'onboarding_status' => $payload['status'],
                'outbox_event_id' => $eventId,
            ]];
        });
    }
}
