<?php

declare(strict_types=1);

namespace NxTutors\DemoCommandCenterAdapter\Tests;

use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;
use Illuminate\Support\Str;
use Illuminate\Testing\TestResponse;
use NxTutors\DemoCommandCenterAdapter\DemoCommandCenterAdapterServiceProvider;
use Orchestra\Testbench\TestCase as Orchestra;

abstract class TestCase extends Orchestra
{
    protected const SECRET = 'test-only-hmac-secret-with-at-least-32-bytes';

    /** @return list<class-string> */
    protected function getPackageProviders($app): array
    {
        return [DemoCommandCenterAdapterServiceProvider::class];
    }

    protected function defineEnvironment($app): void
    {
        $app['config']->set('database.default', 'testing');
        $app['config']->set('database.connections.testing', [
            'driver' => 'sqlite',
            'database' => ':memory:',
            'prefix' => '',
            'foreign_key_constraints' => true,
        ]);
        $scopes = [
            'demo:identity:read', 'demo:profiles:read', 'demo:tutors:read',
            'demo:profile-phone:read', 'demo:tutor-contact:read', 'demo:tutor-phone:read',
            'demo:reference:read', 'demo:regions:read', 'demo:social-proof:read',
            'demo:plans:read', 'demo:subscriptions:read', 'demo:subscription:write',
            'demo:projection:write', 'demo:onboarding:write',
        ];
        $app['config']->set('demo_command_center.enabled', true);
        $app['config']->set('demo_command_center.source', 'demo-command-center');
        $app['config']->set('demo_command_center.audience', 'nxtutors-website-gateway');
        $app['config']->set('demo_command_center.default_currency', 'INR');
        $app['config']->set('demo_command_center.rate_limit_per_minute', 1000);
        $app['config']->set('demo_command_center.audit_required', true);
        $app['config']->set('demo_command_center.activation.active_status', 'active');
        $app['config']->set('demo_command_center.activation.paid_status', 'paid');
        $app['config']->set('demo_command_center.activation.subscription_type', 'demo_conversion');
        $app['config']->set('demo_command_center.hmac_keys', [
            'test-key' => ['secret' => self::SECRET, 'scopes' => $scopes],
            'old-key' => [
                'secret' => 'rotating-test-key-secret-with-32-bytes-minimum',
                'scopes' => $scopes,
                'not_after' => 1,
            ],
        ]);
    }

    protected function setUp(): void
    {
        parent::setUp();
        $this->artisan('migrate', ['--database' => 'testing'])->run();
        $this->createLegacySchema();
        $this->seedLegacyData();
    }

    /**
     * @param list<string> $scopes
     * @param array<string, mixed>|null $payload
     * @param array<string, string> $extraHeaders
     */
    protected function signedRequest(
        string $method,
        string $target,
        array $scopes,
        ?array $payload = null,
        ?string $idempotencyKey = null,
        ?string $nonce = null,
        ?int $timestamp = null,
        array $extraHeaders = [],
    ): TestResponse {
        sort($scopes, SORT_STRING);
        $rawBody = $payload === null ? '' : json_encode(
            $payload,
            JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE,
        );
        $timestamp ??= now()->utc()->timestamp;
        $nonce ??= 'nonce-' . Str::lower((string) Str::ulid());
        $canonical = implode("\n", [
            strtoupper($method), $target, (string) $timestamp, $nonce, 'demo-command-center',
            'nxtutors-website-gateway', implode(' ', $scopes), hash('sha256', $rawBody),
        ]);
        $server = [
            'CONTENT_TYPE' => $payload === null ? '' : 'application/json',
            'HTTP_X_NXTUTORS_KEY_ID' => 'test-key',
            'HTTP_X_NXTUTORS_TIMESTAMP' => (string) $timestamp,
            'HTTP_X_NXTUTORS_NONCE' => $nonce,
            'HTTP_X_NXTUTORS_SOURCE' => 'demo-command-center',
            'HTTP_X_NXTUTORS_AUDIENCE' => 'nxtutors-website-gateway',
            'HTTP_X_NXTUTORS_SCOPES' => implode(' ', $scopes),
            'HTTP_X_NXTUTORS_SIGNATURE' => 'v1=' . hash_hmac('sha256', $canonical, self::SECRET),
            'HTTP_X_REQUEST_ID' => (string) Str::uuid(),
        ];
        if ($idempotencyKey !== null) {
            $server['HTTP_IDEMPOTENCY_KEY'] = $idempotencyKey;
        }
        foreach ($extraHeaders as $name => $value) {
            $server[$name] = $value;
        }

        return $this->call($method, $target, [], [], [], $server, $rawBody);
    }

    private function createLegacySchema(): void
    {
        Schema::create('register', static function (Blueprint $table): void {
            $table->increments('id');
            $table->string('user_id')->nullable();
            $table->string('name')->nullable();
            $table->string('email')->nullable();
            $table->string('phone')->nullable();
            $table->string('password')->nullable();
            $table->string('c_password')->nullable();
            $table->string('otp')->nullable();
            $table->string('document_number')->nullable();
            $table->string('status');
            $table->string('user_type')->nullable();
            $table->string('join_as')->nullable();
            $table->string('for_class')->nullable();
            $table->string('class_type')->nullable();
            $table->string('budget')->nullable();
            $table->string('city')->nullable();
            $table->string('district')->nullable();
            $table->string('state')->nullable();
            $table->string('pincode')->nullable();
            $table->string('experience')->nullable();
            $table->string('education')->nullable();
            $table->text('profile_desc')->nullable();
        });
        Schema::create('teacher_course_managment', static function (Blueprint $table): void {
            $table->increments('id');
            $table->unsignedInteger('teacher_id');
            $table->string('board_id')->nullable();
            $table->string('class_id')->nullable();
            $table->string('subject_ids')->nullable();
            $table->string('status')->nullable();
        });
        Schema::create('teacher_courses', static function (Blueprint $table): void {
            $table->increments('id');
            $table->string('user_id');
            $table->string('board')->nullable();
            $table->string('class')->nullable();
            $table->string('subject')->nullable();
            $table->string('mode')->nullable();
            $table->string('status')->nullable();
        });
        Schema::create('teacher_review', static function (Blueprint $table): void {
            $table->increments('id');
            $table->unsignedInteger('teacher_id');
            $table->decimal('rating', 3, 2)->nullable();
            $table->decimal('expertise', 3, 2)->nullable();
            $table->decimal('patience', 3, 2)->nullable();
            $table->decimal('reliability', 3, 2)->nullable();
            $table->decimal('communication', 3, 2)->nullable();
            $table->text('review')->nullable();
            $table->boolean('is_approved');
            $table->string('status')->nullable();
        });
        Schema::create('subscription_plans', static function (Blueprint $table): void {
            $table->increments('id');
            $table->string('name');
            $table->decimal('price', 12, 2);
            $table->char('currency', 3);
            $table->unsignedInteger('duration_days');
            $table->string('status');
            $table->timestamps();
        });
        Schema::create('user_subscriptions', static function (Blueprint $table): void {
            $table->increments('id');
            $table->string('user_id');
            $table->unsignedInteger('subscription_plan_id');
            $table->string('status')->nullable();
            $table->string('payment_status')->nullable();
            $table->string('type')->nullable();
            $table->string('order_id')->nullable();
            $table->timestamp('start_date')->nullable();
            $table->timestamp('end_date')->nullable();
            $table->timestamps();
            $table->unique(['user_id', 'subscription_plan_id']);
        });
        Schema::create('order_managment', static function (Blueprint $table): void {
            $table->increments('id');
            $table->string('user_id');
            $table->unsignedInteger('plan_id')->nullable();
            $table->string('status')->nullable();
            $table->string('payment_status')->nullable();
            $table->string('order_id')->nullable();
            $table->timestamps();
        });
    }

    private function seedLegacyData(): void
    {
        DB::table('register')->insert(
            [
                'id' => 1, 'user_id' => 'student-1', 'name' => 'Example Learner',
                'email' => 'learner@example.invalid', 'phone' => '+919000000001',
                'password' => 'PASSWORD_MUST_NEVER_LEAK', 'c_password' => 'CONFIRM_MUST_NEVER_LEAK',
                'otp' => 'OTP_MUST_NEVER_LEAK', 'document_number' => 'DOCUMENT_MUST_NEVER_LEAK',
                'status' => 't', 'user_type' => 'student', 'join_as' => 'student',
                'for_class' => '8', 'class_type' => 'online', 'budget' => 'configured-range',
                'city' => 'New Delhi', 'district' => 'Central', 'state' => 'Delhi', 'pincode' => '110001',
            ],
        );
        DB::table('register')->insert(
            [
                'id' => 2, 'user_id' => 'teacher-1', 'name' => 'Example Tutor',
                'email' => 'tutor@example.invalid', 'phone' => '+919000000002',
                'password' => 'TUTOR_PASSWORD_MUST_NEVER_LEAK', 'c_password' => 'TUTOR_CONFIRM_MUST_NEVER_LEAK',
                'otp' => 'TUTOR_OTP_MUST_NEVER_LEAK', 'document_number' => 'TUTOR_DOCUMENT_MUST_NEVER_LEAK',
                'status' => 't', 'user_type' => 'teacher', 'join_as' => 'teacher',
                'class_type' => 'online', 'city' => 'New Delhi', 'district' => 'Central',
                'state' => 'Delhi', 'pincode' => '110001', 'experience' => '5 years',
                'education' => 'Postgraduate', 'profile_desc' => 'Approved mathematics tutor profile.',
            ],
        );
        DB::table('teacher_course_managment')->insert([
            'teacher_id' => 2, 'board_id' => 'CBSE', 'class_id' => '8',
            'subject_ids' => 'Math,Science', 'status' => 'active',
        ]);
        DB::table('teacher_courses')->insert([
            'user_id' => 'teacher-1', 'board' => 'CBSE', 'class' => '8',
            'subject' => 'Math', 'mode' => 'online', 'status' => 'active',
        ]);
        DB::table('teacher_review')->insert([
            [
                'teacher_id' => 2, 'rating' => 4.8, 'expertise' => 4.9, 'patience' => 4.7,
                'reliability' => 4.8, 'communication' => 4.6,
                'review' => 'Clear explanations and reliable sessions.', 'is_approved' => true, 'status' => 'approved',
            ],
            [
                'teacher_id' => 2, 'rating' => 1.0, 'expertise' => 1.0, 'patience' => 1.0,
                'reliability' => 1.0, 'communication' => 1.0,
                'review' => 'UNAPPROVED_REVIEW_MUST_NEVER_LEAK', 'is_approved' => false, 'status' => 'pending',
            ],
        ]);
        DB::table('subscription_plans')->insert([
            'id' => 10, 'name' => 'Example Plan', 'price' => '1250.50', 'currency' => 'INR',
            'duration_days' => 30, 'status' => 'active', 'created_at' => now(), 'updated_at' => now(),
        ]);
    }
}
