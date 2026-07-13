<?php

declare(strict_types=1);

namespace NxTutors\DemoCommandCenterAdapter;

use Illuminate\Cache\RateLimiting\Limit;
use Illuminate\Http\Request;
use Illuminate\Routing\Router;
use Illuminate\Support\Facades\RateLimiter;
use Illuminate\Support\ServiceProvider;
use NxTutors\DemoCommandCenterAdapter\Http\Middleware\AuditGatewayRequest;
use NxTutors\DemoCommandCenterAdapter\Http\Middleware\RequireScope;
use NxTutors\DemoCommandCenterAdapter\Http\Middleware\VerifyInternalService;

final class DemoCommandCenterAdapterServiceProvider extends ServiceProvider
{
    public function register(): void
    {
        $this->mergeConfigFrom(__DIR__ . '/../config/demo_command_center.php', 'demo_command_center');
    }

    public function boot(Router $router): void
    {
        $router->aliasMiddleware('demo-command-center.audit', AuditGatewayRequest::class);
        $router->aliasMiddleware('demo-command-center.auth', VerifyInternalService::class);
        $router->aliasMiddleware('demo-command-center.scope', RequireScope::class);

        RateLimiter::for('demo-command-center-internal', static function (Request $request): Limit {
            $keyId = (string) $request->attributes->get('dcc.key_id', 'unauthenticated');
            $operation = (string) ($request->route()?->getName() ?? 'unknown');
            $limit = max(1, (int) config('demo_command_center.rate_limit_per_minute', 120));

            return Limit::perMinute($limit)->by(hash('sha256', $keyId . '|' . $operation));
        });

        $this->loadRoutesFrom(__DIR__ . '/../routes/api.php');
        $this->loadMigrationsFrom(__DIR__ . '/../database/migrations');

        $this->publishes([
            __DIR__ . '/../config/demo_command_center.php' => config_path('demo_command_center.php'),
        ], 'demo-command-center-config');
        $this->publishesMigrations([
            __DIR__ . '/../database/migrations' => database_path('migrations'),
        ], 'demo-command-center-migrations');
    }
}
