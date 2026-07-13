<?php

declare(strict_types=1);

namespace NxTutors\DemoCommandCenterAdapter\Http\Controllers;

use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use NxTutors\DemoCommandCenterAdapter\Legacy\IdentityRepository;
use NxTutors\DemoCommandCenterAdapter\Support\GatewayException;
use NxTutors\DemoCommandCenterAdapter\Support\GatewayResponse;

final class MinimumProfileController
{
    public function __invoke(Request $request, string $register, IdentityRepository $identities): JsonResponse
    {
        if (preg_match('/^[1-9][0-9]{0,18}$/', $register) !== 1) {
            throw new GatewayException('VALIDATION_FAILED', 422);
        }
        $profile = $identities->minimumProfile($register);
        if ($profile === null) {
            throw new GatewayException('PROFILE_NOT_FOUND', 404);
        }

        return GatewayResponse::success($request, $profile);
    }
}
