<?php

declare(strict_types=1);

namespace NxTutors\DemoCommandCenterAdapter\Http\Controllers;

use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use NxTutors\DemoCommandCenterAdapter\Support\GatewayResponse;

final class RegionMappingsController
{
    public function __invoke(Request $request): JsonResponse
    {
        $mappings = config('demo_command_center.region_mappings', []);
        $safe = [];
        if (is_array($mappings)) {
            foreach ($mappings as $mapping) {
                if (! is_array($mapping)) {
                    continue;
                }
                $safe[] = array_intersect_key($mapping, array_flip([
                    'region_ref', 'region_name', 'states', 'districts', 'cities', 'pincodes',
                ]));
            }
        }

        return GatewayResponse::success($request, [
            'mapping_version' => (string) config('demo_command_center.region_mapping_version', 'unconfigured'),
            'mappings' => $safe,
            'configured' => $safe !== [],
        ]);
    }
}
