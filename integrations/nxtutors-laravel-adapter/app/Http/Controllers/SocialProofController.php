<?php

declare(strict_types=1);

namespace NxTutors\DemoCommandCenterAdapter\Http\Controllers;

use Illuminate\Http\JsonResponse;
use NxTutors\DemoCommandCenterAdapter\Http\Requests\SocialProofRequest;
use NxTutors\DemoCommandCenterAdapter\Legacy\TutorProjectionRepository;
use NxTutors\DemoCommandCenterAdapter\Support\GatewayResponse;

final class SocialProofController
{
    public function __invoke(SocialProofRequest $request, TutorProjectionRepository $tutors): JsonResponse
    {
        return GatewayResponse::success($request, [
            'items' => $tutors->approvedSocialProof((int) ($request->validated('limit') ?? 10)),
            'approval_policy' => 'explicit-approved-only',
        ]);
    }
}
