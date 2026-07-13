<?php

declare(strict_types=1);

namespace NxTutors\DemoCommandCenterAdapter\Security;

use Illuminate\Http\Request;

final class HmacRequestAuthenticator
{
    public function authenticate(Request $request): AuthenticationResult
    {
        $keyId = (string) $request->header('X-NXTutors-Key-Id', '');
        $timestampValue = (string) $request->header('X-NXTutors-Timestamp', '');
        $nonce = (string) $request->header('X-NXTutors-Nonce', '');
        $source = (string) $request->header('X-NXTutors-Source', '');
        $audience = (string) $request->header('X-NXTutors-Audience', '');
        $scopeHeader = trim((string) $request->header('X-NXTutors-Scopes', ''));
        $signatureHeader = strtolower((string) $request->header('X-NXTutors-Signature', ''));

        if (! preg_match('/^[A-Za-z0-9._-]{1,64}$/', $keyId)
            || ! preg_match('/^[A-Za-z0-9._:-]{16,128}$/', $nonce)
            || ! ctype_digit($timestampValue)
            || ! preg_match('/^v1=[a-f0-9]{64}$/', $signatureHeader)) {
            return AuthenticationResult::invalid('AUTH_INVALID');
        }

        $timestamp = (int) $timestampValue;
        $window = max(1, (int) config('demo_command_center.replay_window_seconds', 300));
        $skew = max(0, (int) config('demo_command_center.max_clock_skew_seconds', 30));
        if (abs(now()->utc()->timestamp - $timestamp) > $window + $skew) {
            return AuthenticationResult::invalid('AUTH_TIMESTAMP_EXPIRED');
        }

        $configuredSource = (string) config('demo_command_center.source', '');
        $configuredAudience = (string) config('demo_command_center.audience', '');
        if ($source === '' || $audience === ''
            || ! hash_equals($configuredSource, $source)
            || ! hash_equals($configuredAudience, $audience)) {
            return AuthenticationResult::invalid('AUTH_CONTEXT_INVALID');
        }

        $keys = config('demo_command_center.hmac_keys', []);
        if (! is_array($keys) || ! isset($keys[$keyId]) || ! is_array($keys[$keyId])) {
            return AuthenticationResult::invalid('AUTH_INVALID');
        }
        /** @var array<string, mixed> $key */
        $key = $keys[$keyId];
        $secret = $this->decodeSecret((string) ($key['secret'] ?? ''));
        if ($secret === null) {
            return AuthenticationResult::invalid('AUTH_KEY_UNAVAILABLE', 503);
        }
        if (isset($key['not_before']) && $timestamp < (int) $key['not_before']) {
            return AuthenticationResult::invalid('AUTH_INVALID');
        }
        if (isset($key['not_after']) && $timestamp > (int) $key['not_after']) {
            return AuthenticationResult::invalid('AUTH_INVALID');
        }

        $scopes = $scopeHeader === '' ? [] : preg_split('/\s+/', $scopeHeader);
        if (! is_array($scopes) || count($scopes) > 32) {
            return AuthenticationResult::invalid('AUTH_INVALID');
        }
        $scopes = array_values(array_unique(array_filter($scopes, static fn (mixed $scope): bool =>
            is_string($scope) && preg_match('/^[a-z][a-z0-9:-]{0,63}$/', $scope) === 1)));
        sort($scopes, SORT_STRING);
        $allowedScopes = array_values(array_filter(
            is_array($key['scopes'] ?? null) ? $key['scopes'] : [],
            static fn (mixed $scope): bool => is_string($scope),
        ));
        if (array_diff($scopes, $allowedScopes) !== []) {
            return AuthenticationResult::invalid('AUTH_SCOPE_CLAIM_INVALID', 403);
        }

        $canonical = implode("\n", [
            strtoupper($request->getMethod()),
            $request->getRequestUri(),
            (string) $timestamp,
            $nonce,
            $source,
            $audience,
            implode(' ', $scopes),
            hash('sha256', $request->getContent()),
        ]);
        $expected = hash_hmac('sha256', $canonical, $secret);
        if (! hash_equals($expected, substr($signatureHeader, 3))) {
            return AuthenticationResult::invalid('AUTH_INVALID');
        }

        return AuthenticationResult::valid($keyId, $nonce, $source, $scopes);
    }

    private function decodeSecret(string $configured): ?string
    {
        if (str_starts_with($configured, 'base64:')) {
            $decoded = base64_decode(substr($configured, 7), true);

            return is_string($decoded) && strlen($decoded) >= 32 ? $decoded : null;
        }

        return strlen($configured) >= 32 ? $configured : null;
    }
}
