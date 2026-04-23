import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "deploy_cloud_run.py"
SPEC = importlib.util.spec_from_file_location("deploy_cloud_run", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
deploy_cloud_run = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(deploy_cloud_run)


def test_remote_deploy_defaults_to_chatgpt_friendly_oauth():
    env = {
        "KIS_DB_MODE": "motherduck",
        "MOTHERDUCK_DATABASE": "kis_portfolio",
        "MOTHERDUCK_TOKEN": "md-token",
        "KIS_TOKEN_ENCRYPTION_KEY": "enc-key",
        "KIS_AUTH_ISSUER_URL": "https://auth.example.com",
        "KIS_RESOURCE_SERVER_URL": "https://resource.example.com/mcp",
        "KIS_AUTH_REQUIRED_SCOPES": "mcp:read",
        "KIS_AUTH_TOKEN_PEPPER": "pepper",
    }

    required = deploy_cloud_run._required_keys_for_remote(env)
    payload = deploy_cloud_run._build_remote_env(env)

    assert deploy_cloud_run._effective_remote_auth_mode(env) == "oauth"
    assert "KIS_REMOTE_AUTH_TOKEN" not in required
    assert payload["KIS_REMOTE_AUTH_MODE"] == "oauth"


def test_remote_deploy_keeps_explicit_bearer_override():
    env = {
        "KIS_DB_MODE": "local",
        "KIS_TOKEN_ENCRYPTION_KEY": "enc-key",
        "KIS_REMOTE_AUTH_MODE": "bearer",
        "KIS_REMOTE_AUTH_TOKEN": "shared-token",
    }

    required = deploy_cloud_run._required_keys_for_remote(env)
    payload = deploy_cloud_run._build_remote_env(env)

    assert deploy_cloud_run._effective_remote_auth_mode(env) == "bearer"
    assert "KIS_REMOTE_AUTH_TOKEN" in required
    assert payload["KIS_REMOTE_AUTH_MODE"] == "bearer"
