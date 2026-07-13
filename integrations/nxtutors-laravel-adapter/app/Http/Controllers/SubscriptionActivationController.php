<?php

declare(strict_types=1);

namespace NxTutors\DemoCommandCenterAdapter\Http\Controllers;

use Illuminate\Http\JsonResponse;
use NxTutors\DemoCommandCenterAdapter\Application\SubscriptionActivationService;
use NxTutors\DemoCommandCenterAdapter\Http\Requests\ActivationRequest;
use NxTutors\DemoCommandCenterAdapter\Support\GatewayResponse;

final class SubscriptionActivationController
{
    use ReadsIdempotencyKey;

    public function __invoke(ActivationRequest $request, SubscriptionActivationService $service): JsonResponse
    {
        $result = $service->activate($this->idempotencyKey($request), $request->validated());
        $response = GatewayResponse::success($request, $result->body, $result->status);
        $response->headers->set('X-Idempotency-Replayed', $result->replayed ? 'true' : 'false');

        return $response;
    }
}
