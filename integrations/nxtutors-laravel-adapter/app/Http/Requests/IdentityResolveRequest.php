<?php

declare(strict_types=1);

namespace NxTutors\DemoCommandCenterAdapter\Http\Requests;

use Illuminate\Validation\Validator;

final class IdentityResolveRequest extends StrictGatewayRequest
{
    /** @return array<string, list<string>> */
    public function rules(): array
    {
        return [
            'register_ref' => ['sometimes', 'string', 'regex:/^[1-9][0-9]{0,18}$/'],
            'user_ref' => ['sometimes', 'string', 'min:1', 'max:255'],
            'email' => ['sometimes', 'email:rfc', 'max:255'],
            'phone' => ['sometimes', 'string', 'regex:/^\+?[1-9][0-9]{7,14}$/'],
        ];
    }

    public function withValidator(Validator $validator): void
    {
        $validator->after(function (Validator $validator): void {
            if (count(array_intersect(array_keys($this->all()), ['register_ref', 'user_ref', 'email', 'phone'])) !== 1) {
                $validator->errors()->add('identifier', 'Exactly one identifier is required.');
            }
        });
    }
}
