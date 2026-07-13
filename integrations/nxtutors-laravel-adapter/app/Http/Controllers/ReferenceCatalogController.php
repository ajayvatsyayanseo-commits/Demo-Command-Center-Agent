<?php

declare(strict_types=1);

namespace NxTutors\DemoCommandCenterAdapter\Http\Controllers;

use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use NxTutors\DemoCommandCenterAdapter\Legacy\TutorProjectionRepository;
use NxTutors\DemoCommandCenterAdapter\Support\GatewayResponse;

final class ReferenceCatalogController
{
    public function __invoke(Request $request, TutorProjectionRepository $tutors): JsonResponse
    {
        return GatewayResponse::success($request, $tutors->catalog());
    }
}
