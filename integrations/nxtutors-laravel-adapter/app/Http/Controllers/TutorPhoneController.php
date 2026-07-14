<?php

declare(strict_types=1);

namespace NxTutors\DemoCommandCenterAdapter\Http\Controllers;

use Illuminate\Http\JsonResponse;
use NxTutors\DemoCommandCenterAdapter\Http\Requests\PhoneResolveRequest;
use NxTutors\DemoCommandCenterAdapter\Legacy\TutorProjectionRepository;
use NxTutors\DemoCommandCenterAdapter\Support\GatewayException;
use NxTutors\DemoCommandCenterAdapter\Support\GatewayResponse;

final class TutorPhoneController
{
    public function __invoke(
        PhoneResolveRequest $request,
        string $tutor,
        TutorProjectionRepository $tutors,
    ): JsonResponse {
        $contact = $tutors->phoneRecipient(
            $tutor,
            (string) $request->validated('purpose'),
            (string) $request->validated('demo_ref'),
        );
        if ($contact === null) {
            throw new GatewayException('TUTOR_PHONE_NOT_FOUND', 404);
        }

        return GatewayResponse::success($request, $contact);
    }
}
