"""Compatibility shim for OAuth crypto helpers.

New code should import from ``kis_portfolio.security.oauth_crypto``.
"""

from kis_portfolio.security.oauth_crypto import (
    digest_token,
    generate_token,
    hash_client_secret,
    verify_client_secret,
)


__all__ = [
    "digest_token",
    "generate_token",
    "hash_client_secret",
    "verify_client_secret",
]
