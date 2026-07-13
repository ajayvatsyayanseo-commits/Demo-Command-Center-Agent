<?php

declare(strict_types=1);

namespace NxTutors\DemoCommandCenterAdapter\Http\Requests;

use Illuminate\Contracts\Validation\Validator;
use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Http\Exceptions\HttpResponseException;
use NxTutors\DemoCommandCenterAdapter\Support\GatewayResponse;

abstract class StrictGatewayRequest extends FormRequest
{
    public function authorize(): bool
    {
        return true;
    }

    /** @return array<string, mixed> */
    public function validationData(): array
    {
        $data = parent::validationData();
        $allowed = [];
        foreach (array_keys($this->rules()) as $ruleKey) {
            $allowed[] = explode('.', $ruleKey, 2)[0];
        }
        $unknown = array_values(array_diff(array_keys($data), array_unique($allowed)));
        if ($unknown !== []) {
            throw new HttpResponseException(GatewayResponse::error(
                $this,
                'VALIDATION_FAILED',
                422,
                ['unknown_fields' => $unknown],
            ));
        }

        return $data;
    }

    protected function failedValidation(Validator $validator): never
    {
        throw new HttpResponseException(GatewayResponse::error(
            $this,
            'VALIDATION_FAILED',
            422,
            ['fields' => array_keys($validator->errors()->toArray())],
        ));
    }
}
