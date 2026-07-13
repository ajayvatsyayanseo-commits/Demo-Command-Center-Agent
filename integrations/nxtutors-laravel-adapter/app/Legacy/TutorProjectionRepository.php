<?php

declare(strict_types=1);

namespace NxTutors\DemoCommandCenterAdapter\Legacy;

use Illuminate\Database\Query\Builder;
use Illuminate\Support\Collection;
use Illuminate\Support\Facades\DB;

final class TutorProjectionRepository
{
    private const REGISTER_COLUMNS = [
        'id', 'user_id', 'name', 'status', 'user_type', 'join_as', 'city', 'district',
        'state', 'pincode', 'class_type', 'experience', 'education', 'other_education',
        'profile', 'profile_desc', 'pro_desc',
    ];

    private const COURSE_COLUMNS = [
        'id', 'teacher_id', 'tutor_id', 'user_id', 'register_id', 'category_id',
        'course_category_id', 'board_id', 'board', 'class_id', 'class', 'class_name',
        'subject_id', 'subject_ids', 'subject', 'subjects', 'course_id', 'course',
        'mode', 'class_type', 'status', 'updated_at',
    ];

    private const REVIEW_COLUMNS = [
        'id', 'teacher_id', 'tutor_id', 'user_id', 'register_id', 'rating', 'expertise',
        'patience', 'reliability', 'communication', 'review', 'comment', 'description',
        'is_approved', 'approved', 'review_status', 'status', 'created_at', 'updated_at',
    ];

    public function __construct(private readonly LegacySchema $schema) {}

    /**
     * @param array<string, mixed> $filters
     * @return array{items: list<array<string, mixed>>, page: int, per_page: int, has_more: bool, source_tables: list<string>}
     */
    public function candidates(array $filters): array
    {
        if (! $this->schema->exists('register')) {
            return ['items' => [], 'page' => 1, 'per_page' => 20, 'has_more' => false, 'source_tables' => []];
        }
        $page = (int) ($filters['page'] ?? 1);
        $perPage = (int) ($filters['per_page'] ?? 20);
        $table = $this->schema->table('register');
        $columns = $this->schema->safeColumns('register', self::REGISTER_COLUMNS);
        $query = DB::table($table)->select($columns);
        $roleColumns = array_values(array_intersect(['join_as', 'user_type'], $this->schema->columns('register')));
        if ($roleColumns === []) {
            return ['items' => [], 'page' => $page, 'per_page' => $perPage, 'has_more' => false, 'source_tables' => []];
        }
        $query->where(static function (Builder $roleQuery) use ($roleColumns): void {
            foreach ($roleColumns as $index => $column) {
                $method = $index === 0 ? 'whereIn' : 'orWhereIn';
                $roleQuery->{$method}($column, ['teacher', 'tutor', 'Teacher', 'Tutor', 'TEACHER', 'TUTOR']);
            }
        });
        if (in_array('status', $columns, true)) {
            $query->whereIn('status', ['t', '1', 'active', 'approved']);
        }
        foreach (['city', 'district', 'state', 'class_type'] as $field) {
            if (isset($filters[$field]) && in_array($field, $columns, true)) {
                $query->where($field, (string) $filters[$field]);
            }
        }

        $registers = $query->orderBy('id')->limit(501)->get();
        $courseRows = $this->courseRows($registers);
        $reviewRows = $this->reviewRows($registers);
        $sourceTables = [];
        foreach (['course_management', 'teacher_courses'] as $source) {
            if ($this->schema->exists($source)) {
                $sourceTables[] = $this->schema->table($source);
            }
        }

        $items = [];
        foreach ($registers as $register) {
            $row = (array) $register;
            $courses = $this->coursesFor($row, $courseRows);
            if (! $this->matchesCourseFilters($courses, $filters)) {
                continue;
            }
            $items[] = $this->projectTutor($row, $courses, $this->reviewSummary($row, $reviewRows));
        }

        $offset = ($page - 1) * $perPage;
        $pageItems = array_slice($items, $offset, $perPage + 1);
        $hasMore = count($pageItems) > $perPage;

        return [
            'items' => array_values(array_slice($pageItems, 0, $perPage)),
            'page' => $page,
            'per_page' => $perPage,
            'has_more' => $hasMore,
            'source_tables' => $sourceTables,
        ];
    }

    /** @return array<string, mixed>|null */
    public function tutor(string $registerRef): ?array
    {
        $result = $this->candidates(['per_page' => 100]);
        foreach ($result['items'] as $candidate) {
            if (hash_equals((string) $candidate['tutor_ref'], $registerRef)) {
                return $candidate;
            }
        }

        return null;
    }

    /** @return array{tutor_ref: string, email: string, email_reference: string}|null */
    public function contact(string $registerRef): ?array
    {
        if ($this->tutor($registerRef) === null || ! in_array('email', $this->schema->columns('register'), true)) {
            return null;
        }
        $row = DB::table($this->schema->table('register'))->select(['id', 'email'])->where('id', $registerRef)->first();
        if ($row === null || ! is_string($row->email) || filter_var($row->email, FILTER_VALIDATE_EMAIL) === false) {
            return null;
        }

        return [
            'tutor_ref' => (string) $row->id,
            'email' => $row->email,
            'email_reference' => 'register:' . (string) $row->id . ':email',
        ];
    }

    /** @return array{subjects: list<string>, classes: list<string>, boards: list<string>, modes: list<string>, locations: list<string>} */
    public function catalog(): array
    {
        $result = $this->candidates(['per_page' => 100]);
        $catalog = ['subjects' => [], 'classes' => [], 'boards' => [], 'modes' => [], 'locations' => []];
        foreach ($result['items'] as $item) {
            foreach ($item['courses'] as $course) {
                foreach (['subjects', 'classes', 'boards', 'modes'] as $field) {
                    $catalog[$field] = array_merge($catalog[$field], $course[$field]);
                }
            }
            foreach (['city', 'district', 'state'] as $field) {
                if (is_string($item['location'][$field]) && $item['location'][$field] !== '') {
                    $catalog['locations'][] = $item['location'][$field];
                }
            }
        }
        foreach ($catalog as &$values) {
            $values = array_values(array_unique($values));
            sort($values, SORT_NATURAL | SORT_FLAG_CASE);
        }

        return $catalog;
    }

    /** @return list<array<string, mixed>> */
    public function approvedSocialProof(int $limit): array
    {
        $result = $this->candidates(['per_page' => 100]);
        $proof = [];
        foreach ($result['items'] as $item) {
            foreach ($item['review_summary']['approved_quotes'] as $quote) {
                $proof[] = [
                    'tutor_ref' => $item['tutor_ref'],
                    'quote' => $quote,
                    'rating' => $item['review_summary']['average_rating'],
                ];
                if (count($proof) >= $limit) {
                    return $proof;
                }
            }
        }

        return $proof;
    }

    /** @param Collection<int, object> $registers @return list<array<string, mixed>> */
    private function courseRows(Collection $registers): array
    {
        $rows = [];
        foreach (['course_management', 'teacher_courses'] as $logical) {
            if (! $this->schema->exists($logical)) {
                continue;
            }
            foreach ($this->relatedRows($logical, self::COURSE_COLUMNS, $registers) as $row) {
                $row['_source'] = $this->schema->table($logical);
                $rows[] = $row;
            }
        }

        return $rows;
    }

    /** @param Collection<int, object> $registers @return list<array<string, mixed>> */
    private function reviewRows(Collection $registers): array
    {
        if (! $this->schema->exists('reviews')) {
            return [];
        }
        $approvalColumns = config('demo_command_center.review_approval_columns', []);
        $approvalColumn = is_array($approvalColumns)
            ? $this->schema->firstColumn('reviews', array_values(array_filter($approvalColumns, 'is_string')))
            : null;
        if ($approvalColumn === null) {
            return [];
        }
        $approvedValues = array_map('strval', (array) config('demo_command_center.review_approved_values', []));
        $rows = [];
        foreach ($this->relatedRows('reviews', self::REVIEW_COLUMNS, $registers, $approvalColumn, $approvedValues) as $row) {
            $rows[] = $row;
        }

        return $rows;
    }

    /**
     * @param list<string> $allowlist
     * @param Collection<int, object> $registers
     * @param list<string> $approvedValues
     * @return list<array<string, mixed>>
     */
    private function relatedRows(
        string $logical,
        array $allowlist,
        Collection $registers,
        ?string $approvalColumn = null,
        array $approvedValues = [],
    ): array {
        $relations = array_values(array_intersect(
            ['teacher_id', 'tutor_id', 'register_id', 'user_id'],
            $this->schema->columns($logical),
        ));
        if ($relations === []) {
            return [];
        }
        $ids = $registers->pluck('id')->map(static fn (mixed $value): string => (string) $value)->all();
        $userIds = $registers->pluck('user_id')->filter()->map(static fn (mixed $value): string => (string) $value)->all();
        $query = DB::table($this->schema->table($logical))->select($this->schema->safeColumns($logical, $allowlist));
        $query->where(static function (Builder $related) use ($relations, $ids, $userIds): void {
            foreach ($relations as $index => $column) {
                $values = $column === 'user_id' ? array_values(array_unique(array_merge($ids, $userIds))) : $ids;
                $method = $index === 0 ? 'whereIn' : 'orWhereIn';
                $related->{$method}($column, $values);
            }
        });
        if ($approvalColumn !== null) {
            $query->whereIn($approvalColumn, $approvedValues);
        }

        return array_map(static fn (object $row): array => (array) $row, $query->limit(2000)->get()->all());
    }

    /** @param array<string, mixed> $register @param list<array<string, mixed>> $rows @return list<array<string, mixed>> */
    private function coursesFor(array $register, array $rows): array
    {
        $courses = [];
        foreach ($rows as $row) {
            if (! $this->belongsTo($register, $row)) {
                continue;
            }
            $courses[] = [
                'source' => $row['_source'],
                'source_ref' => isset($row['id']) ? (string) $row['id'] : null,
                'boards' => $this->values($row, ['board', 'board_id', 'category_id', 'course_category_id']),
                'classes' => $this->values($row, ['class', 'class_name', 'class_id']),
                'subjects' => $this->values($row, ['subject', 'subjects', 'subject_id', 'subject_ids', 'course', 'course_id']),
                'modes' => $this->values($row, ['mode', 'class_type']),
                'source_version' => hash('sha256', json_encode($row, JSON_THROW_ON_ERROR)),
            ];
        }

        return $courses;
    }

    /** @param array<string, mixed> $register @param list<array<string, mixed>> $rows @return array<string, mixed> */
    private function reviewSummary(array $register, array $rows): array
    {
        $metrics = ['rating', 'expertise', 'patience', 'reliability', 'communication'];
        $totals = array_fill_keys($metrics, 0.0);
        $counts = array_fill_keys($metrics, 0);
        $quotes = [];
        $approved = 0;
        foreach ($rows as $row) {
            if (! $this->belongsTo($register, $row)) {
                continue;
            }
            ++$approved;
            foreach ($metrics as $metric) {
                if (isset($row[$metric]) && is_numeric($row[$metric])) {
                    $totals[$metric] += (float) $row[$metric];
                    ++$counts[$metric];
                }
            }
            foreach (['review', 'comment', 'description'] as $field) {
                if (isset($row[$field]) && is_string($row[$field]) && trim($row[$field]) !== '') {
                    $quotes[] = mb_substr(trim($row[$field]), 0, 500);
                    break;
                }
            }
        }
        $averages = [];
        foreach ($metrics as $metric) {
            $averages[$metric] = $counts[$metric] > 0 ? round($totals[$metric] / $counts[$metric], 2) : null;
        }

        return [
            'approval_policy' => 'explicit-approved-only',
            'approved_review_count' => $approved,
            'average_rating' => $averages['rating'],
            'quality_indicators' => array_diff_key($averages, ['rating' => true]),
            'approved_quotes' => array_values(array_unique($quotes)),
        ];
    }

    /** @param array<string, mixed> $register @param array<string, mixed> $related */
    private function belongsTo(array $register, array $related): bool
    {
        $id = (string) ($register['id'] ?? '');
        $userId = (string) ($register['user_id'] ?? '');
        foreach (['teacher_id', 'tutor_id', 'register_id'] as $column) {
            if (isset($related[$column]) && (string) $related[$column] === $id) {
                return true;
            }
        }

        return isset($related['user_id'])
            && in_array((string) $related['user_id'], array_filter([$id, $userId]), true);
    }

    /** @param array<string, mixed> $row @param list<string> $columns @return list<string> */
    private function values(array $row, array $columns): array
    {
        $values = [];
        foreach ($columns as $column) {
            if (! isset($row[$column]) || (! is_scalar($row[$column]))) {
                continue;
            }
            foreach (preg_split('/\s*,\s*/', trim((string) $row[$column])) ?: [] as $value) {
                if ($value !== '') {
                    $values[] = mb_substr($value, 0, 160);
                }
            }
        }

        return array_values(array_unique($values));
    }

    /** @param list<array<string, mixed>> $courses @param array<string, mixed> $filters */
    private function matchesCourseFilters(array $courses, array $filters): bool
    {
        foreach (['subject' => 'subjects', 'board' => 'boards', 'class' => 'classes', 'mode' => 'modes'] as $filter => $field) {
            if (! isset($filters[$filter])) {
                continue;
            }
            $needle = mb_strtolower((string) $filters[$filter]);
            $matched = false;
            foreach ($courses as $course) {
                foreach ($course[$field] as $value) {
                    if (mb_strtolower((string) $value) === $needle) {
                        $matched = true;
                    }
                }
            }
            if (! $matched) {
                return false;
            }
        }

        return true;
    }

    /** @param array<string, mixed> $row @param list<array<string, mixed>> $courses @param array<string, mixed> $review */
    private function projectTutor(array $row, array $courses, array $review): array
    {
        $profile = null;
        foreach (['profile_desc', 'pro_desc', 'profile'] as $field) {
            if (isset($row[$field]) && is_string($row[$field]) && trim($row[$field]) !== '') {
                $profile = mb_substr(trim($row[$field]), 0, 1000);
                break;
            }
        }
        $projection = [
            'tutor_ref' => (string) $row['id'],
            'display_name' => isset($row['name']) ? (string) $row['name'] : null,
            'profile_summary' => $profile,
            'experience' => isset($row['experience']) ? (string) $row['experience'] : null,
            'education' => isset($row['education']) ? (string) $row['education'] : null,
            'location' => [
                'city' => isset($row['city']) ? (string) $row['city'] : null,
                'district' => isset($row['district']) ? (string) $row['district'] : null,
                'state' => isset($row['state']) ? (string) $row['state'] : null,
                'pincode' => isset($row['pincode']) ? (string) $row['pincode'] : null,
            ],
            'courses' => $courses,
            'review_summary' => $review,
            'availability_status' => 'unknown',
        ];
        $projection['source_version'] = hash('sha256', json_encode($projection, JSON_THROW_ON_ERROR));

        return $projection;
    }
}
