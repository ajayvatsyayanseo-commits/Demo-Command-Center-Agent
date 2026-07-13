<?php

declare(strict_types=1);

namespace NxTutors\DemoCommandCenterAdapter\Http\Middleware;

use Closure;
use Illuminate\Http\Request;
use NxTutors\DemoCommandCenterAdapter\Support\GatewayResponse;
use Symfony\Component\HttpFoundation\Response;

final class RequireScope
{
    public function handle(Request $request, Closure $next, string $requiredScope): Response
    {
        $scopes = $request->attributes->get('dcc.scopes', []);
        if (! is_array($scopes) || ! in_array($requiredScope, $scopes, true)) {
            return GatewayResponse::error($request, 'AUTH_SCOPE_REQUIRED', 403, ['required_scope' => $requiredScope]);
        }

        return $next($request);
    }
}
