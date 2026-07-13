<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration {
    public function up(): void
    {
        Schema::create('demo_gateway_replay_nonces', static function (Blueprint $table): void {
            $table->id();
            $table->string('key_id', 64);
            $table->string('nonce', 128);
            $table->uuid('request_id');
            $table->timestampTz('expires_at');
            $table->timestampTz('created_at');
            $table->unique(['key_id', 'nonce'], 'demo_gateway_nonce_unique');
            $table->index('expires_at');
        });

        Schema::create('demo_gateway_idempotency', static function (Blueprint $table): void {
            $table->id();
            $table->string('operation_scope', 160);
            $table->string('idempotency_key', 255);
            $table->string('request_hash', 64);
            $table->string('state', 24);
            $table->unsignedSmallInteger('response_status')->nullable();
            $table->json('response_body')->nullable();
            $table->timestampTz('expires_at');
            $table->timestampsTz();
            $table->unique(['operation_scope', 'idempotency_key'], 'demo_gateway_idempotency_unique');
            $table->index('expires_at');
        });

        Schema::create('demo_website_projections', static function (Blueprint $table): void {
            $table->id();
            $table->string('demo_ref', 100)->unique();
            $table->unsignedBigInteger('demo_lead_id')->nullable()->unique();
            $table->string('website_user_ref', 255)->nullable()->index();
            $table->string('lifecycle_state', 64);
            $table->unsignedInteger('projection_version')->default(1);
            $table->string('onboarding_status', 32)->nullable();
            $table->string('onboarding_ref', 160)->nullable();
            $table->uuid('correlation_id');
            $table->timestampTz('state_occurred_at');
            $table->timestampsTz();
        });

        Schema::create('demo_subscription_activations', static function (Blueprint $table): void {
            $table->id();
            $table->string('idempotency_key', 255)->unique();
            $table->string('request_hash', 64);
            $table->string('demo_ref', 100)->unique();
            $table->string('website_user_ref', 255);
            $table->unsignedBigInteger('plan_id');
            $table->string('plan_version', 64);
            $table->unsignedBigInteger('amount_minor');
            $table->char('currency', 3);
            $table->string('provider_order_ref', 255)->unique();
            $table->string('payment_evidence_ref', 255)->unique();
            $table->timestampTz('payment_verified_at');
            $table->string('subscription_ref', 255);
            $table->string('status', 32);
            $table->timestampsTz();
        });

        Schema::create('demo_integration_outbox', static function (Blueprint $table): void {
            $table->id();
            $table->uuid('event_id')->unique();
            $table->string('event_type', 160);
            $table->string('schema_version', 20);
            $table->string('idempotency_key', 255)->unique();
            $table->uuid('correlation_id');
            $table->json('payload');
            $table->timestampTz('occurred_at');
            $table->timestampTz('available_at');
            $table->timestampTz('published_at')->nullable();
            $table->timestampTz('lease_expires_at')->nullable();
            $table->unsignedInteger('attempts')->default(0);
            $table->string('last_error_code', 100)->nullable();
            $table->timestampsTz();
            $table->index(['published_at', 'available_at']);
        });

        Schema::create('demo_gateway_audit_events', static function (Blueprint $table): void {
            $table->id();
            $table->uuid('request_id')->index();
            $table->string('key_id', 64);
            $table->string('method', 10);
            $table->string('route_name', 160);
            $table->string('path', 255);
            $table->unsignedSmallInteger('status_code');
            $table->string('outcome', 32);
            $table->string('ip_hash', 64)->nullable();
            $table->unsignedInteger('duration_ms');
            $table->timestampTz('created_at')->index();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('demo_gateway_audit_events');
        Schema::dropIfExists('demo_integration_outbox');
        Schema::dropIfExists('demo_subscription_activations');
        Schema::dropIfExists('demo_website_projections');
        Schema::dropIfExists('demo_gateway_idempotency');
        Schema::dropIfExists('demo_gateway_replay_nonces');
    }
};
