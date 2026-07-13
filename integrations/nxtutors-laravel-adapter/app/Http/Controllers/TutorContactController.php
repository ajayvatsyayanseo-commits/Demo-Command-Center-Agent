<?php

declare(strict_types=1);

namespace NxTutors\DemoCommandCenterAdapter\Http\Controllers;

use Illuminate\Http\JsonResponse;
use NxTutors\DemoCommandCenterAdapter\Http\Requests\ContactResolveRequest;
use NxTutors\DemoCommandCenterAdapter\Legacy\TutorProjectionRepository;
use NxTutors\DemoCommandCenterAdapter\Support\GatewayException;
use NxTutors\DemoCommandCenterAdapter\Support\GatewayResponse;

final class TutorContactController
{
    public function __invoke(
        ContactResolveRequest $request,
        string $tutor,
        TutorProjectionRepository $tutors,
    ): JsonResponse {
        $contact = $tutors->contact($tutor);
        if ($contact === null) {
            throw new GatewayException('TUTOR_CONTACT_NOT_FOUND', 404);
        }
        $contact['purpose'] = $request->validated('purpose');
        $contact['demo_ref'] = $request->validated('demo_ref');

        return GatewayResponse::success($request, $contact);
    }
}
