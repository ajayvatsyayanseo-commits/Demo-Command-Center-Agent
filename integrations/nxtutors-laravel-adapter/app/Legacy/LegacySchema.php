<?php

declare(strict_types=1);

namespace NxTutors\DemoCommandCenterAdapter\Legacy;

use Illuminate\Support\Facades\Schema;
use RuntimeException;

final class LegacySchema
{
    /** @var array<string, list<string>> */
    private array $columns = [];

    public function table(string $logicalName): string
    {
        $table = (string) config("demo_command_center.tables.{$logicalName}", '');
        if ($table === '' || preg_match('/^[A-Za-z_][A-Za-z0-9_]*$/', $table) !== 1) {
            throw new RuntimeException("Invalid legacy table configuration: {$logicalName}");
        }

        return $table;
    }

    public function exists(string $logicalName): bool
    {
        return Schema::hasTable($this->table($logicalName));
    }

    /** @return list<string> */
    public function columns(string $logicalName): array
    {
        if (! isset($this->columns[$logicalName])) {
            $table = $this->table($logicalName);
            $this->columns[$logicalName] = Schema::hasTable($table)
                ? array_values(Schema::getColumnListing($table))
                : [];
        }

        return $this->columns[$logicalName];
    }

    /** @param list<string> $candidates */
    public function firstColumn(string $logicalName, array $candidates): ?string
    {
        $available = $this->columns($logicalName);
        foreach ($candidates as $candidate) {
            if (in_array($candidate, $available, true)) {
                return $candidate;
            }
        }

        return null;
    }

    /** @param list<string> $allowlist @return list<string> */
    public function safeColumns(string $logicalName, array $allowlist): array
    {
        return array_values(array_intersect($allowlist, $this->columns($logicalName)));
    }
}
