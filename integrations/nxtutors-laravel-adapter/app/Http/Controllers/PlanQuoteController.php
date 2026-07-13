<?php

declare(strict_types=1);

namespace NxTutors\DemoCommandCenterAdapter\Http\Controllers;

use Illuminate\Http\JsonResponse;
use NxTutors\DemoCommandCenterAdapter\Http\Requests\PlanQuoteRequest;
use NxTutors\DemoCommandCenterAdapter\Legacy\PlanRepository;
use NxTutors\DemoCommandCenterAdapter\Support\GatewayException;
use NxTutors\DemoCommandCenterAdapter\Support\GatewayResponse;

final class PlanQuoteController
{
    public function __invoke(PlanQuoteRequest $request, string $plan, PlanRepository $plans): JsonResponse
    {
        if (preg_match('/^[1-9][0-9]{0,18}$/', $plan) !== 1) {
            throw new GatewayException('VALIDATION_FAILED', 422);
        }
        $quote = $plans->quote($plan, (string) $request->validated('user_ref'));
        if ($quote === null) {
            throw new GatewayException('PLAN_QUOTE_NOT_FOUND', 404);
        }

        return GatewayResponse::success($request, $quote);
    }
}
