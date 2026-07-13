<?php

declare(strict_types=1);

namespace NxTutors\DemoCommandCenterAdapter\Http\Requests;

final class ActivationRequest extends StrictGatewayRequest
{
    /** @return array<string, list<string>> */
    public function rules(): array
    {
        return [
            'demo_ref' => ['required', 'string', 'regex:/^[A-Za-z0-9][A-Za-z0-9._:-]{7,99}$/'],
            'website_user_ref' => ['required', 'string', 'min:1', 'max:255'],
            'plan_id' => ['required', 'integer', 'min:1'],
            'plan_version' => ['required', 'string', 'size:64', 'regex:/^[a-f0-9]+$/'],
            'amount_minor' => ['required', 'integer', 'min:0'],
            'currency' => ['required', 'string', 'regex:/^[A-Z]{3}$/'],
            'provider_order_ref' => ['required', 'string', 'min:8', 'max:255', 'regex:/^[A-Za-z0-9._:-]+$/'],
            'payment_evidence_ref' => ['required', 'string', 'min:8', 'max:255', 'regex:/^[A-Za-z0-9._:-]+$/'],
            'payment_verified_at' => ['required', 'date'],
            'correlation_id' => ['required', 'uuid'],
        ];
    }
}
