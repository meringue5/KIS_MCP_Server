"""Compatibility shim for KIS token encryption helpers.

New code should import from ``kis_portfolio.security.token_encryption``.
"""

from kis_portfolio.security.token_encryption import (
    TokenDecryptionError,
    TokenEncryptionConfigError,
    decrypt_token,
    encrypt_token,
    ensure_token_encryption_ready,
)


__all__ = [
    "TokenDecryptionError",
    "TokenEncryptionConfigError",
    "decrypt_token",
    "encrypt_token",
    "ensure_token_encryption_ready",
]
