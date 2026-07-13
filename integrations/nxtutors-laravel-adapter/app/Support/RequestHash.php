<?php

declare(strict_types=1);

namespace NxTutors\DemoCommandCenterAdapter\Support;

final class RequestHash
{
    /** @param array<string, mixed> $payload */
    public static function of(array $payload): string
    {
        self::sortRecursively($payload);
        $encoded = json_encode($payload, JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);

        return hash('sha256', $encoded);
    }

    /** @param array<mixed> $value */
    private static function sortRecursively(array &$value): void
    {
        if (! array_is_list($value)) {
            ksort($value);
        }
        foreach ($value as &$item) {
            if (is_array($item)) {
                self::sortRecursively($item);
            }
        }
    }
}
