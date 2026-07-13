<?php

declare(strict_types=1);

namespace NxTutors\DemoCommandCenterAdapter\Http\Controllers;

use Illuminate\Http\JsonResponse;
use NxTutors\DemoCommandCenterAdapter\Http\Requests\SubscriptionStateRequest;
use NxTutors\DemoCommandCenterAdapter\Legacy\SubscriptionStateRepository;
use NxTutors\DemoCommandCenterAdapter\Support\GatewayException;
use NxTutors\DemoCommandCenterAdapter\Support\GatewayResponse;

final class SubscriptionStateController
{
    public function __invoke(SubscriptionStateRequest $request, SubscriptionStateRepository $subscriptions): JsonResponse
    {
        $state = $subscriptions->state((string) $request->validated('website_user_ref'));
        if ($state === null) {
            throw new GatewayException('WEBSITE_USER_NOT_FOUND', 404);
        }

        return GatewayResponse::success($request, $state);
    }
}
