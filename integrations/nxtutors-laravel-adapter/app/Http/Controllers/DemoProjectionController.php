<?php

declare(strict_types=1);

namespace NxTutors\DemoCommandCenterAdapter\Http\Controllers;

use Illuminate\Http\JsonResponse;
use NxTutors\DemoCommandCenterAdapter\Application\DemoProjectionService;
use NxTutors\DemoCommandCenterAdapter\Http\Requests\DemoProjectionRequest;
use NxTutors\DemoCommandCenterAdapter\Support\GatewayResponse;

final class DemoProjectionController
{
    use ReadsIdempotencyKey;

    public function __invoke(DemoProjectionRequest $request, string $demo, DemoProjectionService $service): JsonResponse
    {
        $result = $service->update($demo, $this->idempotencyKey($request), $request->validated());
        $response = GatewayResponse::success($request, $result->body, $result->status);
        $response->headers->set('X-Idempotency-Replayed', $result->replayed ? 'true' : 'false');

        return $response;
    }
}
