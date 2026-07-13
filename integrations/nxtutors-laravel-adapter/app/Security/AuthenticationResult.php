<?php

declare(strict_types=1);

namespace NxTutors\DemoCommandCenterAdapter\Security;

final readonly class AuthenticationResult
{
    /** @param list<string> $scopes */
    private function __construct(
        public bool $valid,
        public string $errorCode,
        public int $status,
        public string $keyId = '',
        public string $nonce = '',
        public string $source = '',
        public array $scopes = [],
    ) {}

    /** @param list<string> $scopes */
    public static function valid(string $keyId, string $nonce, string $source, array $scopes): self
    {
        return new self(true, '', 200, $keyId, $nonce, $source, $scopes);
    }

    public static function invalid(string $code, int $status = 401): self
    {
        return new self(false, $code, $status);
    }
}
