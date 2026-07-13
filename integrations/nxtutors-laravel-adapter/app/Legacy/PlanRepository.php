<?php

declare(strict_types=1);

namespace NxTutors\DemoCommandCenterAdapter\Legacy;

use Illuminate\Support\Facades\DB;

final class PlanRepository
{
    private const COLUMNS = [
        'id', 'name', 'title', 'price', 'amount', 'amount_minor', 'currency', 'duration',
        'duration_days', 'status', 'is_active', 'description', 'updated_at',
    ];

    public function __construct(
        private readonly LegacySchema $schema,
        private readonly IdentityRepository $identities,
    ) {}

    /** @return list<array<string, mixed>> */
    public function approvedPlans(): array
    {
        if (! $this->schema->exists('plans')) {
            return [];
        }
        $columns = $this->schema->safeColumns('plans', self::COLUMNS);
        if (! in_array('id', $columns, true)) {
            return [];
        }
        $rows = DB::table($this->schema->table('plans'))->select($columns)->orderBy('id')->limit(200)->get();
        $plans = [];
        foreach ($rows as $row) {
            $projected = $this->project((array) $row);
            if ($projected !== null && $projected['eligible']) {
                $plans[] = $projected;
            }
        }

        return $plans;
    }

    /** @return array<string, mixed>|null */
    public function quote(string $planId, string $userRef): ?array
    {
        if ($this->identities->internalRecord($userRef) === null || ! $this->schema->exists('plans')) {
            return null;
        }
        $columns = $this->schema->safeColumns('plans', self::COLUMNS);
        $row = DB::table($this->schema->table('plans'))->select($columns)->where('id', $planId)->first();
        if ($row === null) {
            return null;
        }
        $plan = $this->project((array) $row);
        if ($plan === null) {
            return null;
        }
        $plan['user_ref'] = $userRef;
        $plan['expires_at'] = now()->utc()->addMinutes(5)->toIso8601String();

        return $plan;
    }

    /** @param array<string, mixed> $row @return array<string, mixed>|null */
    private function project(array $row): ?array
    {
        $currency = strtoupper((string) ($row['currency'] ?? config('demo_command_center.default_currency', '')));
        if (preg_match('/^[A-Z]{3}$/', $currency) !== 1) {
            return null;
        }
        $amountMinor = isset($row['amount_minor']) && ctype_digit((string) $row['amount_minor'])
            ? (int) $row['amount_minor']
            : $this->decimalToMinor((string) ($row['price'] ?? $row['amount'] ?? ''));
        if ($amountMinor === null || $amountMinor < 0) {
            return null;
        }
        $eligible = true;
        if (array_key_exists('is_active', $row)) {
            $eligible = in_array(strtolower((string) $row['is_active']), ['1', 't', 'true', 'active'], true);
        } elseif (array_key_exists('status', $row)) {
            $eligible = in_array(strtolower((string) $row['status']), ['1', 't', 'true', 'active', 'approved', 'published'], true);
        }
        $source = [
            'plan_id' => (string) $row['id'],
            'name' => isset($row['name']) ? (string) $row['name'] : (isset($row['title']) ? (string) $row['title'] : null),
            'amount_minor' => $amountMinor,
            'currency' => $currency,
            'duration_days' => $this->durationDays($row),
            'eligible' => $eligible,
            'updated_at' => isset($row['updated_at']) ? (string) $row['updated_at'] : null,
        ];
        $source['plan_version'] = hash('sha256', json_encode($source, JSON_THROW_ON_ERROR));

        return $source;
    }

    private function decimalToMinor(string $value): ?int
    {
        $value = trim($value);
        if (preg_match('/^(\d+)(?:\.(\d{1,2}))?$/', $value, $matches) !== 1) {
            return null;
        }
        $fraction = str_pad($matches[2] ?? '', 2, '0');

        return ((int) $matches[1] * 100) + (int) $fraction;
    }

    /** @param array<string, mixed> $row */
    private function durationDays(array $row): ?int
    {
        foreach (['duration_days', 'duration'] as $column) {
            if (isset($row[$column]) && ctype_digit((string) $row[$column])) {
                return (int) $row[$column];
            }
        }

        return null;
    }
}
