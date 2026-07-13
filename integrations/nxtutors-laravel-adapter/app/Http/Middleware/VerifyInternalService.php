<?php

declare(strict_types=1);

namespace NxTutors\DemoCommandCenterAdapter\Http\Middleware;

use Closure;
use Illuminate\Database\QueryException;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use NxTutors\DemoCommandCenterAdapter\Security\HmacRequestAuthenticator;
use NxTutors\DemoCommandCenterAdapter\Support\GatewayResponse;
use Symfony\Component\HttpFoundation\Response;

final class VerifyInternalService
{
    public function __construct(private readonly HmacRequestAuthenticator $authenticator) {}

    public function handle(Request $request, Closure $next): Response
    {
        $requestId = $request->headers->get('X-Request-ID');
        if (! is_string($requestId) || ! Str::isUuid($requestId)) {
            $requestId = (string) Str::uuid();
        }
        $request->attributes->set('dcc.request_id', $requestId);

        if (! config('demo_command_center.enabled', false)) {
            return GatewayResponse::error($request, 'GATEWAY_DISABLED', 404);
        }

        $maxBytes = max(1, (int) config('demo_command_center.max_body_bytes', 65536));
        $contentLength = $request->headers->get('Content-Length');
        if (is_string($contentLength) && ctype_digit($contentLength) && (int) $contentLength > $maxBytes) {
            return GatewayResponse::error($request, 'REQUEST_TOO_LARGE', 413);
        }
        if (strlen($request->getContent()) > $maxBytes) {
            return GatewayResponse::error($request, 'REQUEST_TOO_LARGE', 413);
        }
        if (in_array($request->getMethod(), ['POST', 'PUT', 'PATCH'], true)
            && ! $request->isJson()) {
            return GatewayResponse::error($request, 'UNSUPPORTED_MEDIA_TYPE', 415);
        }

        $result = $this->authenticator->authenticate($request);
        if (! $result->valid) {
            return GatewayResponse::error($request, $result->errorCode, $result->status);
        }

        $request->attributes->set('dcc.key_id', $result->keyId);
        $request->attributes->set('dcc.scopes', $result->scopes);
        $request->attributes->set('dcc.source', $result->source);

        try {
            DB::table('demo_gateway_replay_nonces')->insert([
                'key_id' => $result->keyId,
                'nonce' => $result->nonce,
                'request_id' => $requestId,
                'expires_at' => now()->utc()->addSeconds(
                    max(1, (int) config('demo_command_center.replay_window_seconds', 300)),
                ),
                'created_at' => now()->utc(),
            ]);
        } catch (QueryException) {
            return GatewayResponse::error($request, 'AUTH_REPLAY_DETECTED', 409);
        }

        $response = $next($request);
        $response->headers->set('X-Request-ID', $requestId);
        $response->headers->set('Cache-Control', 'no-store');
        $response->headers->set('X-Content-Type-Options', 'nosniff');

        return $response;
    }
}
