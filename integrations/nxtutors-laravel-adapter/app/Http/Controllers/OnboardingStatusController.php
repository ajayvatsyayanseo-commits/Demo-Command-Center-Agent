<?php

declare(strict_types=1);

namespace NxTutors\DemoCommandCenterAdapter\Http\Controllers;

use Illuminate\Http\JsonResponse;
use NxTutors\DemoCommandCenterAdapter\Application\DemoProjectionService;
use NxTutors\DemoCommandCenterAdapter\Http\Requests\OnboardingStatusRequest;
use NxTutors\DemoCommandCenterAdapter\Support\GatewayResponse;

final class OnboardingStatusController
{
    use ReadsIdempotencyKey;

    public function __invoke(OnboardingStatusRequest $request, string $demo, DemoProjectionService $service): JsonResponse
    {
        $result = $service->onboarding($demo, $this->idempotencyKey($request), $request->validated());
        $response = GatewayResponse::success($request, $result->body, $result->status);
        $response->headers->set('X-Idempotency-Replayed', $result->replayed ? 'true' : 'false');

        return $response;
    }
}
