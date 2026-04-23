"""Security helpers for OAuth token and client-secret handling."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets


def generate_token(num_bytes: int = 32) -> str:
    return secrets.token_urlsafe(num_bytes)


def digest_token(value: str, pepper: str) -> str:
    return hmac.new(
        pepper.encode("utf-8"),
        value.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def hash_client_secret(
    secret: str,
    *,
    n: int = 2**14,
    r: int = 8,
    p: int = 1,
    dklen: int = 64,
) -> str:
    salt = secrets.token_bytes(16)
    derived = hashlib.scrypt(
        secret.encode("utf-8"),
        salt=salt,
        n=n,
        r=r,
        p=p,
        dklen=dklen,
    )
    salt_b64 = base64.b64encode(salt).decode("ascii")
    derived_b64 = base64.b64encode(derived).decode("ascii")
    return f"scrypt${n}${r}${p}${salt_b64}${derived_b64}"


def verify_client_secret(secret: str, stored_hash: str) -> bool:
    try:
        algorithm, n_text, r_text, p_text, salt_b64, derived_b64 = stored_hash.split("$", 5)
    except ValueError:
        return False

    if algorithm != "scrypt":
        return False

    salt = base64.b64decode(salt_b64.encode("ascii"))
    expected = base64.b64decode(derived_b64.encode("ascii"))
    actual = hashlib.scrypt(
        secret.encode("utf-8"),
        salt=salt,
        n=int(n_text),
        r=int(r_text),
        p=int(p_text),
        dklen=len(expected),
    )
    return hmac.compare_digest(actual, expected)
