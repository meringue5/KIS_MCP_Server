"""Redaction helpers for sensitive response and log values."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


DEFAULT_SECRET_KEYS = frozenset({
    "authorization",
    "appsecret",
    "app_secret",
    "client_secret",
    "kis_app_secret",
    "motherduck_token",
    "token",
    "access_token",
    "refresh_token",
})


def mask_account_id(account_id: str) -> str:
    """Mask a KIS account id while preserving the existing public shape."""
    if len(account_id) <= 4:
        return "*" * len(account_id)
    return f"{account_id[:2]}{'*' * max(len(account_id) - 4, 0)}{account_id[-2:]}"


def redact_mapping(
    value: Mapping[str, Any],
    *,
    secret_keys: Iterable[str] = DEFAULT_SECRET_KEYS,
    replacement: str = "<redacted>",
) -> dict[str, Any]:
    """Return a shallow copy with known secret-looking keys redacted."""
    normalized_keys = {key.lower() for key in secret_keys}
    return {
        key: replacement if str(key).lower() in normalized_keys else item
        for key, item in value.items()
    }
