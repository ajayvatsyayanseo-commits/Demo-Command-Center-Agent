<?php

declare(strict_types=1);

$decodedKeys = json_decode((string) env('DEMO_COMMAND_CENTER_HMAC_KEYS_JSON', '{}'), true);

return [
    'enabled' => filter_var(env('DEMO_COMMAND_CENTER_GATEWAY_ENABLED', false), FILTER_VALIDATE_BOOL),
    'hmac_keys' => is_array($decodedKeys) ? $decodedKeys : [],
    'source' => (string) env('DEMO_COMMAND_CENTER_HMAC_SOURCE', 'demo-command-center'),
    'audience' => (string) env('DEMO_COMMAND_CENTER_HMAC_AUDIENCE', 'nxtutors-website-gateway'),
    'replay_window_seconds' => (int) env('DEMO_COMMAND_CENTER_REPLAY_WINDOW_SECONDS', 300),
    'max_clock_skew_seconds' => (int) env('DEMO_COMMAND_CENTER_MAX_CLOCK_SKEW_SECONDS', 30),
    'max_body_bytes' => (int) env('DEMO_COMMAND_CENTER_MAX_BODY_BYTES', 65536),
    'rate_limit_per_minute' => (int) env('DEMO_COMMAND_CENTER_RATE_LIMIT_PER_MINUTE', 120),
    'audit_required' => filter_var(env('DEMO_COMMAND_CENTER_AUDIT_REQUIRED', true), FILTER_VALIDATE_BOOL),
    'audit_ip_hash_key' => (string) env('DEMO_COMMAND_CENTER_AUDIT_IP_HASH_KEY', ''),
    'default_currency' => strtoupper((string) env('DEMO_COMMAND_CENTER_DEFAULT_CURRENCY', '')),
    'idempotency_retention_hours' => (int) env('DEMO_COMMAND_CENTER_IDEMPOTENCY_RETENTION_HOURS', 168),
    'tables' => [
        'register' => (string) env('DEMO_COMMAND_CENTER_TABLE_REGISTER', 'register'),
        'course_management' => (string) env('DEMO_COMMAND_CENTER_TABLE_COURSE_MANAGEMENT', 'teacher_course_managment'),
        'teacher_courses' => (string) env('DEMO_COMMAND_CENTER_TABLE_TEACHER_COURSES', 'teacher_courses'),
        'reviews' => (string) env('DEMO_COMMAND_CENTER_TABLE_REVIEWS', 'teacher_review'),
        'plans' => (string) env('DEMO_COMMAND_CENTER_TABLE_PLANS', 'subscription_plans'),
        'subscriptions' => (string) env('DEMO_COMMAND_CENTER_TABLE_SUBSCRIPTIONS', 'user_subscriptions'),
        'orders' => (string) env('DEMO_COMMAND_CENTER_TABLE_ORDERS', 'order_managment'),
        'demo_leads' => (string) env('DEMO_COMMAND_CENTER_TABLE_DEMO_LEADS', 'demo_leads'),
    ],
    'review_approval_columns' => ['is_approved', 'approved', 'review_status', 'status'],
    'review_approved_values' => ['1', 't', 'true', 'approved', 'active', 'published'],
    'region_mapping_version' => (string) env('DEMO_COMMAND_CENTER_REGION_MAPPING_VERSION', 'unconfigured'),
    'region_mappings' => [],
    'activation' => [
        'active_status' => (string) env('DEMO_COMMAND_CENTER_SUBSCRIPTION_ACTIVE_STATUS', ''),
        'paid_status' => (string) env('DEMO_COMMAND_CENTER_SUBSCRIPTION_PAID_STATUS', ''),
        'subscription_type' => (string) env('DEMO_COMMAND_CENTER_SUBSCRIPTION_TYPE', ''),
    ],
];
