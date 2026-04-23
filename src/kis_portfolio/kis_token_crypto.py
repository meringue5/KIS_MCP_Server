"""Encryption helpers for the KIS API access-token cache."""

from __future__ import annotations

import os

from cryptography.fernet import Fernet, InvalidToken


class TokenEncryptionConfigError(RuntimeError):
    """Raised when the KIS token encryption key is missing or invalid."""


class TokenDecryptionError(RuntimeError):
    """Raised when a cached KIS token cannot be decrypted."""


def _load_fernet() -> Fernet:
    key = os.environ.get("KIS_TOKEN_ENCRYPTION_KEY", "").strip()
    if not key:
        raise TokenEncryptionConfigError(
            "KIS_TOKEN_ENCRYPTION_KEY is required for KIS access token caching."
        )
    try:
        return Fernet(key.encode("utf-8"))
    except Exception as exc:  # pragma: no cover - cryptography raises multiple subclasses
        raise TokenEncryptionConfigError(
            "KIS_TOKEN_ENCRYPTION_KEY must be a Fernet-compatible base64 32-byte key."
        ) from exc


def ensure_token_encryption_ready() -> None:
    """Validate token-encryption configuration without encrypting a value."""
    _load_fernet()


def encrypt_token(token: str) -> str:
    """Encrypt a raw KIS access token for DB storage."""
    return _load_fernet().encrypt(token.encode("utf-8")).decode("utf-8")


def decrypt_token(ciphertext: str) -> str:
    """Decrypt a DB-stored KIS access token."""
    try:
        value = _load_fernet().decrypt(ciphertext.encode("utf-8"))
    except InvalidToken as exc:
        raise TokenDecryptionError("Stored KIS token ciphertext is invalid or unreadable.") from exc
    return value.decode("utf-8")
