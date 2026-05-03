from __future__ import annotations

from datetime import date, datetime

from cryptography.fernet import Fernet

from kis_portfolio.common import values
from kis_portfolio.db import utils as db_utils
from kis_portfolio.security import oauth_crypto, redaction, token_encryption


def test_mask_account_id_matches_existing_public_shape():
    assert redaction.mask_account_id("11111111") == "11****11"
    assert redaction.mask_account_id("1234") == "****"
    assert redaction.mask_account_id("") == ""


def test_redact_mapping_removes_known_secret_values():
    payload = {
        "authorization": "Bearer token",
        "appsecret": "secret",
        "symbol": "005930",
    }

    assert redaction.redact_mapping(payload) == {
        "authorization": "<redacted>",
        "appsecret": "<redacted>",
        "symbol": "005930",
    }


def test_db_utils_reexports_common_value_helpers():
    assert db_utils.to_float is values.to_float
    assert db_utils.to_int is values.to_int
    assert db_utils.normalize_row is values.normalize_row
    assert db_utils.rows_to_dicts is values.rows_to_dicts
    assert db_utils.json_safe is values.json_safe
    assert db_utils.json_loads is values.json_loads


def test_common_values_preserve_json_safe_conversion():
    row = {
        "created_at": datetime(2026, 5, 3, 12, 30, 0),
        "trade_date": date(2026, 5, 3),
        "balance_data": '{"cash": 1000}',
        "plain": "not-json",
    }

    assert values.to_float("1,234.5") == 1234.5
    assert values.to_int("1,234") == 1234
    assert values.to_int("1234.0") is None
    assert values.normalize_row(row) == {
        "created_at": "2026-05-03T12:30:00",
        "trade_date": "2026-05-03",
        "balance_data": {"cash": 1000},
        "plain": "not-json",
    }
    assert values.json_safe('{"x": 1}') == {"x": 1}
    assert values.json_safe("plain") == "plain"


def test_kis_token_crypto_shim_reexports_security_helpers(monkeypatch):
    from kis_portfolio import kis_token_crypto

    key = Fernet.generate_key().decode("utf-8")
    monkeypatch.setenv("KIS_TOKEN_ENCRYPTION_KEY", key)

    ciphertext = kis_token_crypto.encrypt_token("raw-token")

    assert kis_token_crypto.decrypt_token(ciphertext) == "raw-token"
    assert kis_token_crypto.encrypt_token is token_encryption.encrypt_token
    assert kis_token_crypto.decrypt_token is token_encryption.decrypt_token
    assert kis_token_crypto.TokenDecryptionError is token_encryption.TokenDecryptionError


def test_auth_crypto_shim_reexports_security_helpers():
    from kis_portfolio.adapters.auth import crypto

    digest = crypto.digest_token("token", "pepper")

    assert digest == oauth_crypto.digest_token("token", "pepper")
    assert crypto.generate_token is oauth_crypto.generate_token
    assert crypto.hash_client_secret is oauth_crypto.hash_client_secret
    assert crypto.verify_client_secret is oauth_crypto.verify_client_secret
