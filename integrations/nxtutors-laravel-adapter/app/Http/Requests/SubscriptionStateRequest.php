<?php

declare(strict_types=1);

namespace NxTutors\DemoCommandCenterAdapter\Http\Requests;

final class SubscriptionStateRequest extends StrictGatewayRequest
{
    /** @return array<string, list<string>> */
    public function rules(): array
    {
        return ['website_user_ref' => ['required', 'string', 'min:1', 'max:255']];
    }
}
