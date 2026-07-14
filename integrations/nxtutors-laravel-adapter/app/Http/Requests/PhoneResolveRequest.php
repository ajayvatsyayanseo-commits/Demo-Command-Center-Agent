<?php

declare(strict_types=1);

namespace NxTutors\DemoCommandCenterAdapter\Http\Requests;

final class PhoneResolveRequest extends StrictGatewayRequest
{
    /** @return array<string, list<string>> */
    public function rules(): array
    {
        return [
            'demo_ref' => ['required', 'string', 'regex:/^[A-Za-z0-9][A-Za-z0-9._:-]{7,99}$/'],
            'purpose' => [
                'required',
                'in:demo_tutor_acceptance,demo_session_link,demo_reschedule,demo_cancellation',
            ],
        ];
    }
}
