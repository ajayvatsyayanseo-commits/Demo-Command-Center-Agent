<?php

declare(strict_types=1);

namespace NxTutors\DemoCommandCenterAdapter\Application;

use Carbon\CarbonImmutable;
use Illuminate\Support\Facades\DB;
use NxTutors\DemoCommandCenterAdapter\Legacy\IdentityRepository;
use NxTutors\DemoCommandCenterAdapter\Legacy\LegacySchema;
use NxTutors\DemoCommandCenterAdapter\Legacy\PlanRepository;
use NxTutors\DemoCommandCenterAdapter\Support\GatewayException;
use NxTutors\DemoCommandCenterAdapter\Support\RequestHash;

final class SubscriptionActivationService
{
    public function __construct(
        private readonly IdempotentMutation $idempotency,
        private readonly OutboxWriter $outbox,
        private readonly PlanRepository $plans,
        private readonly IdentityRepository $identities,
        private readonly LegacySchema $schema,
    ) {}

    /** @param array<string, mixed> $payload */
    public function activate(string $key, array $payload): IdempotencyResult
    {
        $hash = RequestHash::of($payload);

        return $this->idempotency->execute('subscription_activation', $key, $hash, function () use ($key, $hash, $payload): array {
            $existing = DB::table('demo_subscription_activations')
                ->where('provider_order_ref', $payload['provider_order_ref'])
                ->orWhere('demo_ref', $payload['demo_ref'])
                ->lockForUpdate()
                ->first();
            if ($existing !== null) {
                $bindings = [
                    'demo_ref' => (string) $existing->demo_ref,
                    'website_user_ref' => (string) $existing->website_user_ref,
                    'plan_id' => (string) $existing->plan_id,
                    'provider_order_ref' => (string) $existing->provider_order_ref,
                    'payment_evidence_ref' => (string) $existing->payment_evidence_ref,
                    'amount_minor' => (int) $existing->amount_minor,
                    'currency' => (string) $existing->currency,
                ];
                $requested = array_intersect_key($payload, $bindings);
                if ($bindings !== $requested) {
                    throw new GatewayException('PAYMENT_ACTIVATION_BINDING_CONFLICT', 409);
                }

                return ['status' => 200, 'body' => [
                    'activation_ref' => (string) $existing->id,
                    'subscription_ref' => (string) $existing->subscription_ref,
                    'status' => (string) $existing->status,
                    'already_applied' => true,
                ]];
            }

            $quote = $this->plans->quote((string) $payload['plan_id'], (string) $payload['website_user_ref']);
            if ($quote === null || ! $quote['eligible']) {
                throw new GatewayException('PLAN_NOT_ELIGIBLE', 409);
            }
            if ((int) $quote['amount_minor'] !== (int) $payload['amount_minor']
                || ! hash_equals((string) $quote['currency'], (string) $payload['currency'])
                || ! hash_equals((string) $quote['plan_version'], (string) $payload['plan_version'])) {
                throw new GatewayException('PAYMENT_PLAN_BINDING_MISMATCH', 409);
            }
            $identity = $this->identities->internalRecord((string) $payload['website_user_ref']);
            if ($identity === null) {
                throw new GatewayException('WEBSITE_USER_NOT_FOUND', 404);
            }

            $subscriptionRef = $this->applyLegacySubscription($identity, $quote, $payload);
            $now = now()->utc();
            $activationId = DB::table('demo_subscription_activations')->insertGetId([
                'idempotency_key' => $key,
                'request_hash' => $hash,
                'demo_ref' => $payload['demo_ref'],
                'website_user_ref' => $payload['website_user_ref'],
                'plan_id' => (int) $payload['plan_id'],
                'plan_version' => $payload['plan_version'],
                'amount_minor' => $payload['amount_minor'],
                'currency' => $payload['currency'],
                'provider_order_ref' => $payload['provider_order_ref'],
                'payment_evidence_ref' => $payload['payment_evidence_ref'],
                'payment_verified_at' => $payload['payment_verified_at'],
                'subscription_ref' => $subscriptionRef,
                'status' => 'applied',
                'created_at' => $now,
                'updated_at' => $now,
            ]);
            $eventId = $this->outbox->append(
                'website.subscription.activated.v1',
                'subscription-activation|' . hash('sha256', $key),
                (string) $payload['correlation_id'],
                [
                    'activation_ref' => (string) $activationId,
                    'demo_ref' => $payload['demo_ref'],
                    'website_user_ref' => $payload['website_user_ref'],
                    'plan_id' => (string) $payload['plan_id'],
                    'subscription_ref' => $subscriptionRef,
                    'provider_order_ref' => $payload['provider_order_ref'],
                    'status' => 'applied',
                ],
            );

            return ['status' => 201, 'body' => [
                'activation_ref' => (string) $activationId,
                'subscription_ref' => $subscriptionRef,
                'status' => 'applied',
                'already_applied' => false,
                'outbox_event_id' => $eventId,
            ]];
        });
    }

    /** @param array<string, mixed> $identity @param array<string, mixed> $quote @param array<string, mixed> $payload */
    private function applyLegacySubscription(array $identity, array $quote, array $payload): string
    {
        if (! $this->schema->exists('subscriptions')) {
            throw new GatewayException('SUBSCRIPTION_STORE_UNAVAILABLE', 503);
        }
        $columns = $this->schema->columns('subscriptions');
        $userColumn = $this->schema->firstColumn('subscriptions', ['user_id', 'register_id']);
        $planColumn = $this->schema->firstColumn('subscriptions', ['subscription_plan_id', 'plan_id']);
        if ($userColumn === null || $planColumn === null) {
            throw new GatewayException('SUBSCRIPTION_SCHEMA_UNSUPPORTED', 503);
        }
        $activeStatus = (string) config('demo_command_center.activation.active_status', '');
        $paidStatus = (string) config('demo_command_center.activation.paid_status', '');
        $subscriptionType = (string) config('demo_command_center.activation.subscription_type', '');
        if ($activeStatus === '' || (in_array('payment_status', $columns, true) && $paidStatus === '')) {
            throw new GatewayException('SUBSCRIPTION_POLICY_UNCONFIGURED', 503);
        }

        $userValue = $userColumn === 'register_id'
            ? (string) $identity['id']
            : (string) (($identity['user_id'] ?? '') !== '' ? $identity['user_id'] : $identity['id']);
        $match = [$userColumn => $userValue, $planColumn => (int) $payload['plan_id']];
        $values = [];
        if (in_array('status', $columns, true)) {
            $values['status'] = $activeStatus;
        }
        if (in_array('payment_status', $columns, true)) {
            $values['payment_status'] = $paidStatus;
        }
        foreach (['type', 'subscription_type'] as $typeColumn) {
            if (in_array($typeColumn, $columns, true) && $subscriptionType !== '') {
                $values[$typeColumn] = $subscriptionType;
            }
        }
        foreach (['provider_order_ref', 'order_id'] as $orderColumn) {
            if (in_array($orderColumn, $columns, true)) {
                $values[$orderColumn] = $payload['provider_order_ref'];
                break;
            }
        }
        $startedAt = CarbonImmutable::now('UTC');
        foreach (['start_date', 'starts_at'] as $startColumn) {
            if (in_array($startColumn, $columns, true)) {
                $values[$startColumn] = $startedAt;
                break;
            }
        }
        if (is_int($quote['duration_days']) && $quote['duration_days'] > 0) {
            foreach (['end_date', 'expires_at'] as $endColumn) {
                if (in_array($endColumn, $columns, true)) {
                    $values[$endColumn] = $startedAt->addDays($quote['duration_days']);
                    break;
                }
            }
        }
        if (in_array('updated_at', $columns, true)) {
            $values['updated_at'] = $startedAt;
        }
        if (in_array('created_at', $columns, true)) {
            $values['created_at'] = $startedAt;
        }
        if ($values === []) {
            throw new GatewayException('SUBSCRIPTION_SCHEMA_UNSUPPORTED', 503);
        }

        DB::table($this->schema->table('subscriptions'))->updateOrInsert($match, $values);
        $record = DB::table($this->schema->table('subscriptions'))->where($match)->first();
        if ($record === null) {
            throw new GatewayException('SUBSCRIPTION_ACTIVATION_FAILED', 503);
        }

        return isset($record->id)
            ? (string) $record->id
            : hash('sha256', $userValue . '|' . (string) $payload['plan_id']);
    }
}
