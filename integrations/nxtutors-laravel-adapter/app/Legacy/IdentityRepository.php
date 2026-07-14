<?php

declare(strict_types=1);

namespace NxTutors\DemoCommandCenterAdapter\Legacy;

use Illuminate\Support\Facades\DB;
use RuntimeException;

final class IdentityRepository
{
    private const SAFE_IDENTITY_COLUMNS = [
        'id', 'user_id', 'name', 'status', 'user_type', 'join_as', 'for_class',
        'class_type', 'budget', 'city', 'district', 'state', 'pincode',
    ];

    public function __construct(private readonly LegacySchema $schema) {}

    /** @param array<string, string> $identifier @return array{status: string, matches: list<array<string, mixed>>} */
    public function resolve(array $identifier): array
    {
        if (! $this->schema->exists('register')) {
            throw new RuntimeException('Legacy register table is unavailable');
        }
        $table = $this->schema->table('register');
        $columns = $this->schema->safeColumns('register', self::SAFE_IDENTITY_COLUMNS);
        $key = array_key_first($identifier);
        $column = match ($key) {
            'register_ref' => 'id',
            'user_ref' => 'user_id',
            'email' => 'email',
            'phone' => 'phone',
            default => null,
        };
        if ($column === null || ! in_array($column, $this->schema->columns('register'), true)) {
            return ['status' => 'not_found', 'matches' => []];
        }

        $rows = DB::table($table)->select($columns)->where($column, $identifier[$key])->limit(2)->get();
        $matches = [];
        foreach ($rows as $row) {
            $matches[] = $this->project((array) $row);
        }

        return [
            'status' => count($matches) === 0 ? 'not_found' : (count($matches) === 1 ? 'resolved' : 'ambiguous'),
            'matches' => $matches,
        ];
    }

    /** @return array<string, mixed>|null */
    public function minimumProfile(string $registerRef): ?array
    {
        $result = $this->resolve(['register_ref' => $registerRef]);

        return $result['status'] === 'resolved' ? $result['matches'][0] : null;
    }

    /** @return array<string, mixed>|null */
    public function phoneRecipient(string $registerRef, string $purpose, string $demoRef): ?array
    {
        if (! $this->schema->exists('register') || ! in_array('phone', $this->schema->columns('register'), true)) {
            throw new RuntimeException('Legacy register phone source is unavailable');
        }
        $row = DB::table($this->schema->table('register'))
            ->select($this->schema->safeColumns('register', ['id', 'user_id', 'phone', 'status']))
            ->where('id', $registerRef)
            ->first();
        if ($row === null || ! is_string($row->phone)) {
            return null;
        }
        $normalized = self::normalizePhone($row->phone);
        if ($normalized === null) {
            return null;
        }
        $register = (string) $row->id;
        $recipientRef = "register:{$register}:phone";
        $projection = [
            'register_ref' => $register,
            'user_ref' => isset($row->user_id) ? (string) $row->user_id : null,
            'recipient_ref' => $recipientRef,
            'phone_reference' => $recipientRef,
            'channel' => 'whatsapp',
            'purpose' => $purpose,
            'demo_ref' => $demoRef,
            'masked_phone' => self::maskPhone($normalized),
        ];
        $projection['source_version'] = hash('sha256', json_encode($projection, JSON_THROW_ON_ERROR));

        return $projection;
    }

    /** @return array<string, mixed>|null */
    public function internalRecord(string $reference): ?array
    {
        $byId = ctype_digit($reference) ? $this->resolve(['register_ref' => $reference]) : ['status' => 'not_found'];
        $result = $byId['status'] === 'resolved' ? $byId : $this->resolve(['user_ref' => $reference]);
        if ($result['status'] !== 'resolved') {
            return null;
        }

        $table = $this->schema->table('register');
        $available = $this->schema->safeColumns('register', array_merge(self::SAFE_IDENTITY_COLUMNS, ['email']));
        $match = $result['matches'][0];

        $record = DB::table($table)->select($available)->where('id', $match['register_ref'])->first();

        return $record === null ? null : (array) $record;
    }

    /** @param array<string, mixed> $row @return array<string, mixed> */
    private function project(array $row): array
    {
        $projected = [
            'register_ref' => (string) ($row['id'] ?? ''),
            'user_ref' => isset($row['user_id']) ? (string) $row['user_id'] : null,
            'display_name' => isset($row['name']) ? (string) $row['name'] : null,
            'account_status' => isset($row['status']) ? (string) $row['status'] : null,
            'user_type' => isset($row['user_type']) ? (string) $row['user_type'] : null,
            'join_as' => isset($row['join_as']) ? (string) $row['join_as'] : null,
            'learner_class' => isset($row['for_class']) ? (string) $row['for_class'] : null,
            'class_mode' => isset($row['class_type']) ? (string) $row['class_type'] : null,
            'budget' => isset($row['budget']) ? (string) $row['budget'] : null,
            'location' => [
                'city' => isset($row['city']) ? (string) $row['city'] : null,
                'district' => isset($row['district']) ? (string) $row['district'] : null,
                'state' => isset($row['state']) ? (string) $row['state'] : null,
                'pincode' => isset($row['pincode']) ? (string) $row['pincode'] : null,
            ],
        ];
        $projected['source_version'] = hash('sha256', json_encode($projected, JSON_THROW_ON_ERROR));

        return $projected;
    }

    private static function normalizePhone(string $phone): ?string
    {
        $normalized = preg_replace('/[^\d+]/', '', trim($phone));
        if (! is_string($normalized) || preg_match('/^\+?[1-9][0-9]{7,14}$/', $normalized) !== 1) {
            return null;
        }

        return $normalized;
    }

    private static function maskPhone(string $phone): string
    {
        $suffix = substr($phone, -4);

        return str_repeat('*', max(0, strlen($phone) - 4)) . $suffix;
    }
}
