<?php

declare(strict_types=1);

namespace NxTutors\DemoCommandCenterAdapter\Legacy;

use Illuminate\Support\Facades\DB;

final class SubscriptionStateRepository
{
    private const SUBSCRIPTION_COLUMNS = [
        'id', 'user_id', 'register_id', 'plan_id', 'subscription_plan_id', 'status',
        'payment_status', 'start_date', 'end_date', 'expires_at', 'type',
        'subscription_type', 'order_id', 'provider_order_ref', 'updated_at',
    ];

    private const ORDER_COLUMNS = [
        'id', 'user_id', 'register_id', 'plan_id', 'subscription_plan_id', 'status',
        'payment_status', 'order_id', 'provider_order_ref', 'created_at', 'updated_at',
    ];

    public function __construct(
        private readonly LegacySchema $schema,
        private readonly IdentityRepository $identities,
    ) {}

    /** @return array<string, mixed>|null */
    public function state(string $userRef): ?array
    {
        $identity = $this->identities->internalRecord($userRef);
        if ($identity === null) {
            return null;
        }
        $registerRef = (string) ($identity['id'] ?? '');
        $externalUserRef = (string) ($identity['user_id'] ?? '');

        return [
            'website_user_ref' => $userRef,
            'subscriptions' => $this->related('subscriptions', self::SUBSCRIPTION_COLUMNS, $registerRef, $externalUserRef),
            'orders' => $this->related('orders', self::ORDER_COLUMNS, $registerRef, $externalUserRef),
        ];
    }

    /** @param list<string> $allowlist @return list<array<string, mixed>> */
    private function related(string $logical, array $allowlist, string $registerRef, string $userRef): array
    {
        if (! $this->schema->exists($logical)) {
            return [];
        }
        $relations = array_values(array_intersect(['user_id', 'register_id'], $this->schema->columns($logical)));
        if ($relations === []) {
            return [];
        }
        $query = DB::table($this->schema->table($logical))->select($this->schema->safeColumns($logical, $allowlist));
        $query->where(static function ($related) use ($relations, $registerRef, $userRef): void {
            foreach ($relations as $index => $column) {
                $values = array_values(array_filter([$registerRef, $userRef], static fn (string $value): bool => $value !== ''));
                $method = $index === 0 ? 'whereIn' : 'orWhereIn';
                $related->{$method}($column, $values);
            }
        });

        return array_map(static function (object $row): array {
            $record = (array) $row;
            foreach (array_keys($record) as $column) {
                if (! in_array($column, self::SUBSCRIPTION_COLUMNS, true)
                    && ! in_array($column, self::ORDER_COLUMNS, true)) {
                    unset($record[$column]);
                }
            }

            return $record;
        }, $query->orderByDesc('id')->limit(50)->get()->all());
    }
}
