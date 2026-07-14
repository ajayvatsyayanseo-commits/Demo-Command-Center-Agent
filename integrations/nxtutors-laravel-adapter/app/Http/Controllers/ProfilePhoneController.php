<?php

declare(strict_types=1);

namespace NxTutors\DemoCommandCenterAdapter\Http\Controllers;

use Illuminate\Http\JsonResponse;
use NxTutors\DemoCommandCenterAdapter\Http\Requests\PhoneResolveRequest;
use NxTutors\DemoCommandCenterAdapter\Legacy\IdentityRepository;
use NxTutors\DemoCommandCenterAdapter\Support\GatewayException;
use NxTutors\DemoCommandCenterAdapter\Support\GatewayResponse;

final class ProfilePhoneController
{
    public function __invoke(
        PhoneResolveRequest $request,
        string $register,
        IdentityRepository $identities,
    ): JsonResponse {
        $contact = $identities->phoneRecipient(
            $register,
            (string) $request->validated('purpose'),
            (string) $request->validated('demo_ref'),
        );
        if ($contact === null) {
            throw new GatewayException('PROFILE_PHONE_NOT_FOUND', 404);
        }

        return GatewayResponse::success($request, $contact);
    }
}
