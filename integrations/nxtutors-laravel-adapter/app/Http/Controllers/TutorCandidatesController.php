<?php

declare(strict_types=1);

namespace NxTutors\DemoCommandCenterAdapter\Http\Controllers;

use Illuminate\Http\JsonResponse;
use NxTutors\DemoCommandCenterAdapter\Http\Requests\TutorSearchRequest;
use NxTutors\DemoCommandCenterAdapter\Legacy\TutorProjectionRepository;
use NxTutors\DemoCommandCenterAdapter\Support\GatewayResponse;

final class TutorCandidatesController
{
    public function __invoke(TutorSearchRequest $request, TutorProjectionRepository $tutors): JsonResponse
    {
        return GatewayResponse::success($request, $tutors->candidates($request->validated()));
    }
}
