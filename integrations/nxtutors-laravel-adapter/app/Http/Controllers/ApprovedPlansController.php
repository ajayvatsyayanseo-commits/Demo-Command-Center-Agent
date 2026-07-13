<?php

declare(strict_types=1);

namespace NxTutors\DemoCommandCenterAdapter\Http\Controllers;

use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use NxTutors\DemoCommandCenterAdapter\Legacy\PlanRepository;
use NxTutors\DemoCommandCenterAdapter\Support\GatewayResponse;

final class ApprovedPlansController
{
    public function __invoke(Request $request, PlanRepository $plans): JsonResponse
    {
        return GatewayResponse::success($request, ['items' => $plans->approvedPlans()]);
    }
}
