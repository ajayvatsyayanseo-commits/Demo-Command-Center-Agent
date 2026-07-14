from __future__ import annotations

import base64
import binascii
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class EncryptionConfigurationError(ValueError):
    """Raised when the field-encryption key cannot be used safely."""


class PayloadCipher:
    """Versioned AES-256-GCM envelope for restricted database payloads."""

    _VERSION = b"\x01"
    _NONCE_BYTES = 12

    def __init__(self, key: bytes) -> None:
        if len(key) != 32:
            raise EncryptionConfigurationError("field encryption key must contain 32 bytes")
        self._cipher = AESGCM(key)

    @classmethod
    def from_encoded_key(cls, encoded_key: str) -> PayloadCipher:
        try:
            if encoded_key.startswith("base64:"):
                key = base64.urlsafe_b64decode(encoded_key.removeprefix("base64:") + "===")
            elif encoded_key.startswith("hex:"):
                key = bytes.fromhex(encoded_key.removeprefix("hex:"))
            else:
                raise EncryptionConfigurationError(
                    "field encryption key must use the base64: or hex: encoding prefix"
                )
        except (ValueError, binascii.Error) as exc:
            raise EncryptionConfigurationError("field encryption key is malformed") from exc
        return cls(key)

    def encrypt(self, plaintext: bytes, *, associated_data: bytes) -> bytes:
        nonce = os.urandom(self._NONCE_BYTES)
        ciphertext = self._cipher.encrypt(nonce, plaintext, associated_data)
        return self._VERSION + nonce + ciphertext

    def decrypt(self, envelope: bytes, *, associated_data: bytes) -> bytes:
        minimum_length = 1 + self._NONCE_BYTES + 16
        if len(envelope) < minimum_length or envelope[:1] != self._VERSION:
            raise ValueError("unsupported or malformed encrypted payload")
        nonce = envelope[1 : 1 + self._NONCE_BYTES]
        ciphertext = envelope[1 + self._NONCE_BYTES :]
        return self._cipher.decrypt(nonce, ciphertext, associated_data)
