<?php

declare(strict_types=1);

namespace NxTutors\DemoCommandCenterAdapter\Http\Requests;

final class SocialProofRequest extends StrictGatewayRequest
{
    /** @return array<string, list<string>> */
    public function rules(): array
    {
        return ['limit' => ['sometimes', 'integer', 'min:1', 'max:20']];
    }
}
