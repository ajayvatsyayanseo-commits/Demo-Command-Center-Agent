<?php

declare(strict_types=1);

namespace NxTutors\DemoCommandCenterAdapter\Http\Middleware;

use Closure;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use NxTutors\DemoCommandCenterAdapter\Support\GatewayResponse;
use NxTutors\DemoCommandCenterAdapter\Support\GatewayException;
use Symfony\Component\HttpFoundation\Response;
use Throwable;

final class AuditGatewayRequest
{
    public function handle(Request $request, Closure $next): Response
    {
        if (! $request->attributes->has('dcc.request_id')) {
            $request->attributes->set('dcc.request_id', (string) Str::uuid());
        }
        $started = hrtime(true);

        try {
            $response = $next($request);
        } catch (Throwable $exception) {
            if ($exception instanceof GatewayException) {
                $response = GatewayResponse::error(
                    $request,
                    $exception->errorCode,
                    $exception->status,
                    $exception->details,
                );
            } else {
                $response = GatewayResponse::error($request, 'INTERNAL_ERROR', 500);
                report($exception);
            }
        }

        try {
            $ipKey = (string) config('demo_command_center.audit_ip_hash_key', '');
            $ipHash = $ipKey === '' ? null : hash_hmac('sha256', (string) $request->ip(), $ipKey);
            DB::table('demo_gateway_audit_events')->insert([
                'request_id' => (string) $request->attributes->get('dcc.request_id'),
                'key_id' => substr((string) $request->attributes->get('dcc.key_id', 'unverified'), 0, 64),
                'method' => $request->getMethod(),
                'route_name' => substr((string) ($request->route()?->getName() ?? 'unknown'), 0, 160),
                'path' => substr($request->getPathInfo(), 0, 255),
                'status_code' => $response->getStatusCode(),
                'outcome' => $response->isSuccessful() ? 'allowed' : 'denied',
                'ip_hash' => $ipHash,
                'duration_ms' => (int) ((hrtime(true) - $started) / 1_000_000),
                'created_at' => now()->utc(),
            ]);
        } catch (Throwable $exception) {
            report($exception);
            if (config('demo_command_center.audit_required', true)) {
                return GatewayResponse::error($request, 'AUDIT_UNAVAILABLE', 503);
            }
        }

        return $response;
    }
}
