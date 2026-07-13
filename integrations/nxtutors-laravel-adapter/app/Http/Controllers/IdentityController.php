<?php

declare(strict_types=1);

namespace NxTutors\DemoCommandCenterAdapter\Http\Controllers;

use Illuminate\Http\JsonResponse;
use NxTutors\DemoCommandCenterAdapter\Http\Requests\IdentityResolveRequest;
use NxTutors\DemoCommandCenterAdapter\Legacy\IdentityRepository;
use NxTutors\DemoCommandCenterAdapter\Support\GatewayResponse;

final class IdentityController
{
    public function __invoke(IdentityResolveRequest $request, IdentityRepository $identities): JsonResponse
    {
        /** @var array<string, string> $identifier */
        $identifier = $request->validated();

        return GatewayResponse::success($request, $identities->resolve($identifier));
    }
}
