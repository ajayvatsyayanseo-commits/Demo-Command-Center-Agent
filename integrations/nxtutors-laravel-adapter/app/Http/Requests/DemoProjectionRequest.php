<?php

declare(strict_types=1);

namespace NxTutors\DemoCommandCenterAdapter\Http\Requests;

final class DemoProjectionRequest extends StrictGatewayRequest
{
    /** @return array<string, list<string>> */
    public function rules(): array
    {
        return [
            'expected_version' => ['required', 'integer', 'min:0'],
            'demo_lead_ref' => ['sometimes', 'nullable', 'integer', 'min:1'],
            'website_user_ref' => ['sometimes', 'nullable', 'string', 'max:255'],
            'lifecycle_state' => ['required', 'string', 'max:64'],
            'occurred_at' => ['required', 'date'],
            'correlation_id' => ['required', 'uuid'],
        ];
    }
}
