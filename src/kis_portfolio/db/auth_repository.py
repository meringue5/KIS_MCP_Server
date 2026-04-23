"""Repository helpers for OAuth/authentication state."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from kis_portfolio.db.connection import get_connection
from kis_portfolio.db.utils import json_loads


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _row_to_dict(cursor, row) -> dict[str, Any] | None:
    if row is None:
        return None
    columns = [desc[0] for desc in cursor.description]
    payload = dict(zip(columns, row))
    for key in ("redirect_uris", "grant_types", "response_types", "profile_data", "metadata"):
        if key in payload:
            payload[key] = json_loads(payload[key])
    return payload


def normalize_scope(scope: str | list[str] | None) -> str:
    if scope is None:
        return ""
    if isinstance(scope, str):
        values = [item for item in scope.split(" ") if item]
    else:
        values = [item for item in scope if item]
    return " ".join(sorted(dict.fromkeys(values)))


def split_scope(scope: str | None) -> list[str]:
    if not scope:
        return []
    return [item for item in scope.split(" ") if item]


def get_auth_user_by_id(user_id: str) -> dict[str, Any] | None:
    con = get_connection()
    cursor = con.execute("""
        SELECT id, primary_email, display_name, is_active, created_at, updated_at
        FROM auth_users
        WHERE id=?
    """, [user_id])
    return _row_to_dict(cursor, cursor.fetchone())


def get_auth_user_by_email(email: str) -> dict[str, Any] | None:
    con = get_connection()
    cursor = con.execute("""
        SELECT id, primary_email, display_name, is_active, created_at, updated_at
        FROM auth_users
        WHERE lower(primary_email)=lower(?)
    """, [email])
    return _row_to_dict(cursor, cursor.fetchone())


def get_auth_identity(provider: str, provider_subject: str) -> dict[str, Any] | None:
    con = get_connection()
    cursor = con.execute("""
        SELECT id, user_id, provider, provider_subject, email, email_verified, profile_data,
               created_at, updated_at
        FROM auth_identities
        WHERE provider=? AND provider_subject=?
    """, [provider, provider_subject])
    return _row_to_dict(cursor, cursor.fetchone())


def upsert_auth_user(
    email: str,
    display_name: str | None,
) -> dict[str, Any]:
    con = get_connection()
    now = _utcnow()
    cursor = con.execute("""
        INSERT INTO auth_users (primary_email, display_name, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT (primary_email) DO UPDATE SET
            display_name = COALESCE(excluded.display_name, auth_users.display_name),
            updated_at = excluded.updated_at
        RETURNING id, primary_email, display_name, is_active, created_at, updated_at
    """, [email.lower(), display_name, now])
    row = cursor.fetchone()
    assert row is not None
    return _row_to_dict(cursor, row) or {}


def upsert_auth_identity(
    *,
    provider: str,
    provider_subject: str,
    email: str,
    email_verified: bool,
    display_name: str | None,
    profile_data: dict[str, Any],
) -> dict[str, Any]:
    existing_identity = get_auth_identity(provider, provider_subject)
    if existing_identity:
        user_id = existing_identity["user_id"]
        user = get_auth_user_by_id(user_id)
        if user:
            upsert_auth_user(user["primary_email"], display_name or user.get("display_name"))
    else:
        existing_user = get_auth_user_by_email(email.lower())
        user = existing_user or upsert_auth_user(email.lower(), display_name)
        user_id = user["id"]

    con = get_connection()
    now = _utcnow()
    cursor = con.execute("""
        INSERT INTO auth_identities (
            user_id, provider, provider_subject, email, email_verified, profile_data, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (provider, provider_subject) DO UPDATE SET
            user_id = excluded.user_id,
            email = excluded.email,
            email_verified = excluded.email_verified,
            profile_data = excluded.profile_data,
            updated_at = excluded.updated_at
        RETURNING id, user_id, provider, provider_subject, email, email_verified, profile_data,
                  created_at, updated_at
    """, [
        user_id,
        provider,
        provider_subject,
        email.lower(),
        email_verified,
        _json_dumps(profile_data),
        now,
    ])
    row = cursor.fetchone()
    assert row is not None
    return _row_to_dict(cursor, row) or {}


def upsert_oauth_client(
    *,
    client_id: str,
    client_secret_hash: str,
    redirect_uris: list[str],
    grant_types: list[str],
    response_types: list[str],
    scope: str,
    client_name: str,
    token_endpoint_auth_method: str,
    metadata: dict[str, Any] | None = None,
    client_id_issued_at: datetime | None = None,
    client_secret_expires_at: datetime | None = None,
) -> dict[str, Any]:
    con = get_connection()
    now = _utcnow()
    cursor = con.execute("""
        INSERT INTO oauth_clients (
            client_id, client_secret_hash, redirect_uris, grant_types, response_types,
            scope, client_name, token_endpoint_auth_method, metadata,
            client_id_issued_at, client_secret_expires_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (client_id) DO UPDATE SET
            client_secret_hash = excluded.client_secret_hash,
            redirect_uris = excluded.redirect_uris,
            grant_types = excluded.grant_types,
            response_types = excluded.response_types,
            scope = excluded.scope,
            client_name = excluded.client_name,
            token_endpoint_auth_method = excluded.token_endpoint_auth_method,
            metadata = excluded.metadata,
            client_id_issued_at = excluded.client_id_issued_at,
            client_secret_expires_at = excluded.client_secret_expires_at,
            updated_at = excluded.updated_at
        RETURNING client_id, client_secret_hash, redirect_uris, grant_types, response_types,
                  scope, client_name, token_endpoint_auth_method, metadata,
                  client_id_issued_at, client_secret_expires_at, created_at, updated_at
    """, [
        client_id,
        client_secret_hash,
        _json_dumps(redirect_uris),
        _json_dumps(grant_types),
        _json_dumps(response_types),
        normalize_scope(scope),
        client_name,
        token_endpoint_auth_method,
        _json_dumps(metadata) if metadata is not None else None,
        client_id_issued_at or now,
        client_secret_expires_at,
        now,
    ])
    row = cursor.fetchone()
    assert row is not None
    return _row_to_dict(cursor, row) or {}


def get_oauth_client(client_id: str) -> dict[str, Any] | None:
    con = get_connection()
    cursor = con.execute("""
        SELECT client_id, client_secret_hash, redirect_uris, grant_types, response_types,
               scope, client_name, token_endpoint_auth_method, metadata,
               client_id_issued_at, client_secret_expires_at, created_at, updated_at
        FROM oauth_clients
        WHERE client_id=?
    """, [client_id])
    return _row_to_dict(cursor, cursor.fetchone())


def get_oauth_grant(user_id: str, client_id: str, scope: str) -> dict[str, Any] | None:
    con = get_connection()
    cursor = con.execute("""
        SELECT id, user_id, client_id, scope, granted_at, revoked_at, created_at, updated_at
        FROM oauth_grants
        WHERE user_id=? AND client_id=? AND scope=? AND revoked_at IS NULL
    """, [user_id, client_id, normalize_scope(scope)])
    return _row_to_dict(cursor, cursor.fetchone())


def upsert_oauth_grant(user_id: str, client_id: str, scope: str) -> dict[str, Any]:
    con = get_connection()
    now = _utcnow()
    cursor = con.execute("""
        INSERT INTO oauth_grants (user_id, client_id, scope, granted_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT (user_id, client_id, scope) DO UPDATE SET
            granted_at = excluded.granted_at,
            revoked_at = NULL,
            updated_at = excluded.updated_at
        RETURNING id, user_id, client_id, scope, granted_at, revoked_at, created_at, updated_at
    """, [user_id, client_id, normalize_scope(scope), now, now])
    row = cursor.fetchone()
    assert row is not None
    return _row_to_dict(cursor, row) or {}


def insert_authorization_code(
    *,
    user_id: str,
    client_id: str,
    grant_id: str | None,
    code_digest: str,
    scope: str,
    redirect_uri: str,
    redirect_uri_provided_explicitly: bool,
    code_challenge: str,
    resource: str | None,
    state: str | None,
    provider: str | None,
    expires_at: datetime,
) -> dict[str, Any]:
    con = get_connection()
    cursor = con.execute("""
        INSERT INTO oauth_authorization_codes (
            user_id, client_id, grant_id, code_digest, scope, redirect_uri,
            redirect_uri_provided_explicitly, code_challenge, resource, state, provider, expires_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        RETURNING id, user_id, client_id, grant_id, code_digest, scope, redirect_uri,
                  redirect_uri_provided_explicitly, code_challenge, resource, state, provider,
                  created_at, expires_at, consumed_at, revoked_at
    """, [
        user_id,
        client_id,
        grant_id,
        code_digest,
        normalize_scope(scope),
        redirect_uri,
        redirect_uri_provided_explicitly,
        code_challenge,
        resource,
        state,
        provider,
        expires_at,
    ])
    row = cursor.fetchone()
    assert row is not None
    return _row_to_dict(cursor, row) or {}


def get_authorization_code(code_digest: str) -> dict[str, Any] | None:
    con = get_connection()
    cursor = con.execute("""
        SELECT id, user_id, client_id, grant_id, code_digest, scope, redirect_uri,
               redirect_uri_provided_explicitly, code_challenge, resource, state, provider,
               created_at, expires_at, consumed_at, revoked_at
        FROM oauth_authorization_codes
        WHERE code_digest=?
    """, [code_digest])
    return _row_to_dict(cursor, cursor.fetchone())


def consume_authorization_code(code_id: str) -> None:
    con = get_connection()
    con.execute("""
        UPDATE oauth_authorization_codes
        SET consumed_at = ?, revoked_at = COALESCE(revoked_at, ?)
        WHERE id=?
    """, [_utcnow(), _utcnow(), code_id])


def insert_oauth_token(
    *,
    user_id: str,
    client_id: str,
    grant_id: str | None,
    token_type: str,
    token_digest: str,
    scope: str,
    resource: str | None,
    expires_at: datetime | None,
    parent_token_id: str | None = None,
    replaces_token_id: str | None = None,
) -> dict[str, Any]:
    con = get_connection()
    cursor = con.execute("""
        INSERT INTO oauth_tokens (
            user_id, client_id, grant_id, token_type, token_digest, scope, resource, expires_at,
            parent_token_id, replaces_token_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        RETURNING id, user_id, client_id, grant_id, token_type, token_digest, scope,
                  resource, created_at, expires_at, revoked_at, parent_token_id, replaces_token_id
    """, [
        user_id,
        client_id,
        grant_id,
        token_type,
        token_digest,
        normalize_scope(scope),
        resource,
        expires_at,
        parent_token_id,
        replaces_token_id,
    ])
    row = cursor.fetchone()
    assert row is not None
    return _row_to_dict(cursor, row) or {}


def get_oauth_token(token_digest: str, token_type: str | None = None) -> dict[str, Any] | None:
    con = get_connection()
    query = """
        SELECT id, user_id, client_id, grant_id, token_type, token_digest, scope,
               resource, created_at, expires_at, revoked_at, parent_token_id, replaces_token_id
        FROM oauth_tokens
        WHERE token_digest=?
    """
    params: list[Any] = [token_digest]
    if token_type:
        query += " AND token_type=?"
        params.append(token_type)
    cursor = con.execute(query, params)
    return _row_to_dict(cursor, cursor.fetchone())


def revoke_oauth_token(token_id: str) -> None:
    con = get_connection()
    con.execute("""
        UPDATE oauth_tokens
        SET revoked_at = COALESCE(revoked_at, ?)
        WHERE id=?
    """, [_utcnow(), token_id])


def revoke_oauth_tokens_for_grant(grant_id: str) -> None:
    con = get_connection()
    con.execute("""
        UPDATE oauth_tokens
        SET revoked_at = COALESCE(revoked_at, ?)
        WHERE grant_id=?
    """, [_utcnow(), grant_id])


def revoke_oauth_token_by_digest(
    token_digest: str,
    client_id: str | None = None,
) -> dict[str, Any] | None:
    token = get_oauth_token(token_digest)
    if token is None:
        return None
    if client_id and token["client_id"] != client_id:
        return None
    revoke_oauth_token(token["id"])
    return get_oauth_token(token_digest)
