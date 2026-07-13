<?php

declare(strict_types=1);

namespace NxTutors\DemoCommandCenterAdapter\Http\Controllers;

use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use NxTutors\DemoCommandCenterAdapter\Legacy\TutorProjectionRepository;
use NxTutors\DemoCommandCenterAdapter\Support\GatewayException;
use NxTutors\DemoCommandCenterAdapter\Support\GatewayResponse;

final class TutorProfileController
{
    public function __invoke(Request $request, string $tutor, TutorProjectionRepository $tutors): JsonResponse
    {
        if (preg_match('/^[1-9][0-9]{0,18}$/', $tutor) !== 1) {
            throw new GatewayException('VALIDATION_FAILED', 422);
        }
        $projection = $tutors->tutor($tutor);
        if ($projection === null) {
            throw new GatewayException('TUTOR_NOT_FOUND', 404);
        }

        return GatewayResponse::success($request, $projection);
    }
}
