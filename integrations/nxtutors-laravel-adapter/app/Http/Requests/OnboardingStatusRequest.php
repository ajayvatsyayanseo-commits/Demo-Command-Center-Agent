<?php

declare(strict_types=1);

namespace NxTutors\DemoCommandCenterAdapter\Http\Requests;

final class OnboardingStatusRequest extends StrictGatewayRequest
{
    /** @return array<string, list<string>> */
    public function rules(): array
    {
        return [
            'status' => ['required', 'in:pending,accepted,in_progress,completed,failed,human_review'],
            'onboarding_ref' => ['sometimes', 'nullable', 'string', 'max:160'],
            'correlation_id' => ['required', 'uuid'],
        ];
    }
}
