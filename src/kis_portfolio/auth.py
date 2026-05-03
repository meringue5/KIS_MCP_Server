"""KIS OAuth token and hashkey helpers."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

from .config import get_token_dir
from .db.kis_token_repository import get_kis_api_access_token, upsert_kis_api_access_token
from .security.token_encryption import (
    TokenDecryptionError,
    TokenEncryptionConfigError,
    decrypt_token,
    ensure_token_encryption_ready,
    encrypt_token,
)


CONTENT_TYPE = "application/json"
AUTH_TYPE = "Bearer"
TOKEN_PATH = "/oauth2/tokenP"
HASHKEY_PATH = "/uapi/hashkey"
TOKEN_REFRESH_SAFETY = timedelta(minutes=10)
DEFAULT_TOKEN_LIFETIME = timedelta(hours=23, minutes=50)
_TOKEN_REFRESH_LOCKS: dict[str, asyncio.Lock] = {}


def get_token_file(cano: str | None = None) -> Path:
    token_dir = get_token_dir()
    token_dir.mkdir(parents=True, exist_ok=True)
    return token_dir / f"token_{cano or os.environ.get('KIS_CANO', 'default')}.json"


def load_token(token_file: Path | None = None) -> tuple[str | None, datetime | None]:
    """Load token from file if it exists and is not expired."""
    path = token_file or get_token_file()
    if path.exists():
        try:
            token_data = json.loads(path.read_text())
            expires_at = datetime.fromisoformat(token_data["expires_at"])
            if is_token_valid(expires_at):
                return token_data["token"], expires_at
        except Exception as e:
            print(f"Error loading token: {e}", file=sys.stderr)
    return None, None


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required for KIS token cache operations.")
    return value


def _get_cache_context() -> dict[str, str]:
    account_type = _require_env("KIS_ACCOUNT_TYPE").upper()
    cano = _require_env("KIS_CANO")
    app_key = _require_env("KIS_APP_KEY")
    return {
        "account_type": account_type,
        "account_id": cano,
        "app_key": app_key,
        "cache_key": hashlib.sha256(f"{account_type}:{cano}:{app_key}".encode("utf-8")).hexdigest(),
        "app_key_fingerprint": hashlib.sha256(app_key.encode("utf-8")).hexdigest(),
    }


def _coerce_expires_in(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _persist_token_record(
    *,
    cache_context: dict[str, str],
    token: str,
    issued_at: datetime,
    expires_at: datetime,
    token_type: str | None,
    expires_in: int | None,
    response_expiry_raw: str | None,
    migrated_from_file: bool,
) -> dict[str, Any]:
    ciphertext = encrypt_token(token)
    return upsert_kis_api_access_token(
        cache_key=cache_context["cache_key"],
        account_id=cache_context["account_id"],
        account_type=cache_context["account_type"],
        app_key_fingerprint=cache_context["app_key_fingerprint"],
        token_ciphertext=ciphertext,
        token_type=token_type or AUTH_TYPE,
        issued_at=issued_at,
        expires_at=expires_at,
        expires_in=expires_in,
        response_expiry_raw=response_expiry_raw,
        migrated_from_file=migrated_from_file,
    )


def _read_db_token_record(cache_context: dict[str, str]) -> dict[str, Any] | None:
    return get_kis_api_access_token(cache_context["cache_key"])


def _read_valid_token_from_db(cache_context: dict[str, str]) -> tuple[str | None, dict[str, Any] | None]:
    record = _read_db_token_record(cache_context)
    if record is None:
        return None, None

    expires_at = record.get("expires_at")
    if not isinstance(expires_at, datetime):
        raise RuntimeError("Cached KIS token row is missing a valid expires_at timestamp.")
    if not is_token_valid(expires_at):
        return None, record

    ciphertext = record.get("token_ciphertext")
    if not isinstance(ciphertext, str) or not ciphertext:
        raise RuntimeError("Cached KIS token row is missing token ciphertext.")
    return decrypt_token(ciphertext), record


def _migrate_legacy_token_if_available(
    cache_context: dict[str, str],
    token_file: Path | None,
) -> tuple[str | None, datetime | None]:
    path = token_file or get_token_file()
    token, expires_at = load_token(path)
    if not token or not expires_at:
        return None, None

    token_data = json.loads(path.read_text())
    issued_at_raw = token_data.get("issued_at")
    issued_at = datetime.fromisoformat(issued_at_raw) if issued_at_raw else datetime.now()
    _persist_token_record(
        cache_context=cache_context,
        token=token,
        issued_at=issued_at,
        expires_at=expires_at,
        token_type=token_data.get("token_type"),
        expires_in=_coerce_expires_in(token_data.get("expires_in")),
        response_expiry_raw=token_data.get("access_token_token_expired"),
        migrated_from_file=True,
    )
    path.unlink(missing_ok=True)
    return token, expires_at


def get_token_status(token_file: Path | None = None) -> dict[str, Any]:
    """Return token cache metadata without exposing the token value."""
    try:
        cache_context = _get_cache_context()
        record = _read_db_token_record(cache_context)
    except RuntimeError as e:
        return {
            "exists": False,
            "status": "misconfigured",
            "error": str(e),
        }
    except Exception as e:
        return {
            "exists": True,
            "status": "unreadable",
            "error": str(e),
        }

    if record is None:
        path = token_file or get_token_file()
        if not path.exists():
            return {
                "exists": False,
                "status": "missing",
            }
        try:
            token_data = json.loads(path.read_text())
            expires_at = datetime.fromisoformat(token_data["expires_at"])
        except Exception as e:
            return {
                "exists": True,
                "status": "unreadable",
                "storage": "legacy_file",
                "error": str(e),
            }
        now = datetime.now()
        if is_token_valid(expires_at, now):
            status = "valid"
        elif now < expires_at:
            status = "near_expiry"
        else:
            status = "expired"
        result = {
            "exists": True,
            "status": status,
            "storage": "legacy_file",
            "has_token": bool(token_data.get("token")),
            "issued_at": token_data.get("issued_at"),
            "expires_at": expires_at.isoformat(),
            "minutes_until_expiry": round((expires_at - now).total_seconds() / 60, 1),
        }
        for key in ("token_type", "expires_in", "access_token_token_expired"):
            if key in token_data:
                result[key] = token_data[key]
        return result

    expires_at = record["expires_at"]
    now = datetime.now()
    if is_token_valid(expires_at, now):
        status = "valid"
    elif now < expires_at:
        status = "near_expiry"
    else:
        status = "expired"

    result = {
        "exists": True,
        "status": status,
        "storage": "db",
        "has_token": bool(record.get("token_ciphertext")),
        "issued_at": record["issued_at"].isoformat() if record.get("issued_at") else None,
        "expires_at": expires_at.isoformat(),
        "minutes_until_expiry": round((expires_at - now).total_seconds() / 60, 1),
    }
    if record.get("token_type"):
        result["token_type"] = record["token_type"]
    if record.get("expires_in") is not None:
        result["expires_in"] = record["expires_in"]
    if record.get("response_expiry_raw"):
        result["access_token_token_expired"] = record["response_expiry_raw"]
    if record.get("migrated_from_file"):
        result["migrated_from_file"] = True
    return result


def is_token_valid(expires_at: datetime, now: datetime | None = None) -> bool:
    """Return whether a token is safely reusable."""
    now = now or datetime.now()
    return now < expires_at - TOKEN_REFRESH_SAFETY


def parse_kis_expiry(token_data: dict[str, Any], issued_at: datetime) -> datetime:
    """Parse KIS token expiry from the response, falling back conservatively."""
    raw_expiry = token_data.get("access_token_token_expired")
    if raw_expiry:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(str(raw_expiry), fmt)
            except ValueError:
                pass
        try:
            return datetime.fromisoformat(str(raw_expiry))
        except ValueError:
            pass

    expires_in = token_data.get("expires_in")
    if expires_in:
        try:
            return issued_at + timedelta(seconds=int(expires_in))
        except Exception:
            pass

    return issued_at + DEFAULT_TOKEN_LIFETIME


def save_token(
    token: str,
    expires_at: datetime,
    token_file: Path | None = None,
    *,
    issued_at: datetime | None = None,
    response_data: dict[str, Any] | None = None,
) -> None:
    """Save token to file."""
    path = token_file or get_token_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    issued_at = issued_at or datetime.now()
    payload = {
        "token": token,
        "issued_at": issued_at.isoformat(),
        "expires_at": expires_at.isoformat(),
    }
    if response_data:
        if "token_type" in response_data:
            payload["token_type"] = response_data["token_type"]
        if "expires_in" in response_data:
            payload["expires_in"] = response_data["expires_in"]
        if "access_token_token_expired" in response_data:
            payload["access_token_token_expired"] = response_data["access_token_token_expired"]

    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    tmp.chmod(0o600)
    tmp.replace(path)


def _get_refresh_lock(cache_key: str) -> asyncio.Lock:
    lock = _TOKEN_REFRESH_LOCKS.get(cache_key)
    if lock is None:
        lock = asyncio.Lock()
        _TOKEN_REFRESH_LOCKS[cache_key] = lock
    return lock


async def get_access_token(
    client: httpx.AsyncClient,
    domain: str,
    token_file: Path | None = None,
) -> str:
    """Get access token from the encrypted DB cache or request a new one."""
    cache_context = _get_cache_context()
    ensure_token_encryption_ready()
    try:
        token, _record = _read_valid_token_from_db(cache_context)
    except (TokenDecryptionError, TokenEncryptionConfigError):
        raise
    if token:
        return token

    async with _get_refresh_lock(cache_context["cache_key"]):
        try:
            token, record = _read_valid_token_from_db(cache_context)
        except (TokenDecryptionError, TokenEncryptionConfigError):
            raise
        if token:
            return token

        if record is None:
            token, expires_at = _migrate_legacy_token_if_available(cache_context, token_file)
            if token and expires_at:
                return token

        token_response = await client.post(
            f"{domain}{TOKEN_PATH}",
            headers={"content-type": CONTENT_TYPE},
            json={
                "grant_type": "client_credentials",
                "appkey": os.environ["KIS_APP_KEY"],
                "appsecret": os.environ["KIS_APP_SECRET"],
            },
        )

        if token_response.status_code != 200:
            raise Exception(f"Failed to get token: {token_response.text}")

        issued_at = datetime.now()
        token_data = token_response.json()
        token = token_data["access_token"]
        expires_at = parse_kis_expiry(token_data, issued_at)
        _persist_token_record(
            cache_context=cache_context,
            token=token,
            issued_at=issued_at,
            expires_at=expires_at,
            token_type=token_data.get("token_type"),
            expires_in=_coerce_expires_in(token_data.get("expires_in")),
            response_expiry_raw=token_data.get("access_token_token_expired"),
            migrated_from_file=False,
        )

    return token


async def get_hashkey(
    client: httpx.AsyncClient,
    domain: str,
    token: str,
    body: dict[str, Any],
) -> str:
    """Get hash key for order request."""
    response = await client.post(
        f"{domain}{HASHKEY_PATH}",
        headers={
            "content-type": CONTENT_TYPE,
            "authorization": f"{AUTH_TYPE} {token}",
            "appkey": os.environ["KIS_APP_KEY"],
            "appsecret": os.environ["KIS_APP_SECRET"],
        },
        json=body,
    )

    if response.status_code != 200:
        raise Exception(f"Failed to get hash key: {response.text}")

    return response.json()["HASH"]
