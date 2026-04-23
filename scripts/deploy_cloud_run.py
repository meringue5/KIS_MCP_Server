"""Deploy KIS auth or remote service to Cloud Run from local source."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from dotenv import dotenv_values


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGION = "asia-northeast3"
DEFAULT_REMOTE_SERVICE = "kis-portfolio-remote"
DEFAULT_AUTH_SERVICE = "kis-portfolio-auth"
DEFAULT_REMOTE_CONCURRENCY = "20"
DEFAULT_REMOTE_MAX_INSTANCES = "1"
DEFAULT_CHATGPT_REMOTE_AUTH_MODE = "oauth"


def _load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    dotenv_path = PROJECT_ROOT / ".env"
    if dotenv_path.exists():
        for key, value in dotenv_values(dotenv_path).items():
            if key and value is not None:
                env[key] = value
    for key, value in os.environ.items():
        env[key] = value
    return env


def _collect_prefixed(env: dict[str, str], prefixes: tuple[str, ...]) -> dict[str, str]:
    return {
        key: value
        for key, value in env.items()
        if any(key.startswith(prefix) for prefix in prefixes) and value != ""
    }


def _required_keys_for_auth(env: dict[str, str]) -> list[str]:
    keys = [
        "KIS_DB_MODE",
        "KIS_AUTH_BASE_URL",
        "KIS_AUTH_OWNER_EMAILS",
        "KIS_AUTH_SESSION_SECRET",
        "KIS_AUTH_TOKEN_PEPPER",
        "KIS_AUTH_CLAUDE_CLIENT_ID",
        "KIS_AUTH_CLAUDE_CLIENT_SECRET",
        "KIS_OAUTH_GOOGLE_CLIENT_ID",
        "KIS_OAUTH_GOOGLE_CLIENT_SECRET",
        "KIS_OAUTH_GITHUB_CLIENT_ID",
        "KIS_OAUTH_GITHUB_CLIENT_SECRET",
    ]
    if env.get("KIS_DB_MODE", "").lower() == "motherduck":
        keys.extend(["MOTHERDUCK_DATABASE", "MOTHERDUCK_TOKEN"])
    return keys


def _required_keys_for_remote(env: dict[str, str]) -> list[str]:
    keys = [
        "KIS_DB_MODE",
        "KIS_TOKEN_ENCRYPTION_KEY",
    ]
    if env.get("KIS_DB_MODE", "").lower() == "motherduck":
        keys.extend(["MOTHERDUCK_DATABASE", "MOTHERDUCK_TOKEN"])

    auth_mode = _effective_remote_auth_mode(env)
    if auth_mode == "oauth":
        keys.extend([
            "KIS_AUTH_ISSUER_URL",
            "KIS_RESOURCE_SERVER_URL",
            "KIS_AUTH_REQUIRED_SCOPES",
            "KIS_AUTH_TOKEN_PEPPER",
        ])
    elif auth_mode == "bearer":
        keys.append("KIS_REMOTE_AUTH_MODE")
        keys.append("KIS_REMOTE_AUTH_TOKEN")

    return keys


def _effective_remote_auth_mode(env: dict[str, str]) -> str:
    return env.get("KIS_REMOTE_AUTH_MODE", DEFAULT_CHATGPT_REMOTE_AUTH_MODE).strip().lower()


def _build_auth_env(env: dict[str, str]) -> dict[str, str]:
    keys = {
        "KIS_DB_MODE",
        "MOTHERDUCK_DATABASE",
        "MOTHERDUCK_TOKEN",
        "KIS_AUTH_BASE_URL",
        "KIS_AUTH_OWNER_EMAILS",
        "KIS_AUTH_SESSION_SECRET",
        "KIS_AUTH_TOKEN_PEPPER",
        "KIS_AUTH_ALLOWED_SCOPES",
        "KIS_AUTH_CLAUDE_CLIENT_ID",
        "KIS_AUTH_CLAUDE_CLIENT_SECRET",
        "KIS_AUTH_CLAUDE_REDIRECT_URIS",
        "KIS_OAUTH_GOOGLE_CLIENT_ID",
        "KIS_OAUTH_GOOGLE_CLIENT_SECRET",
        "KIS_OAUTH_GITHUB_CLIENT_ID",
        "KIS_OAUTH_GITHUB_CLIENT_SECRET",
        "KIS_DATA_DIR",
    }
    return {key: env[key] for key in keys if env.get(key, "") != ""}


def _build_remote_env(env: dict[str, str]) -> dict[str, str]:
    keys = {
        "KIS_DB_MODE",
        "MOTHERDUCK_DATABASE",
        "MOTHERDUCK_TOKEN",
        "KIS_ACCOUNT_TYPE",
        "KIS_ENABLE_ORDER_TOOLS",
        "KIS_DATA_DIR",
        "KIS_TOKEN_ENCRYPTION_KEY",
        "KIS_REMOTE_AUTH_MODE",
        "KIS_REMOTE_AUTH_TOKEN",
        "KIS_AUTH_ISSUER_URL",
        "KIS_RESOURCE_SERVER_URL",
        "KIS_AUTH_REQUIRED_SCOPES",
        "KIS_AUTH_ALLOWED_SCOPES",
        "KIS_AUTH_TOKEN_PEPPER",
    }
    payload = {key: env[key] for key in keys if env.get(key, "") != ""}
    payload["KIS_REMOTE_AUTH_MODE"] = _effective_remote_auth_mode(env)
    payload.update(_collect_prefixed(env, ("KIS_APP_KEY_", "KIS_APP_SECRET_", "KIS_CANO_", "KIS_ACNT_PRDT_CD_")))
    return payload


def _validate_required(env: dict[str, str], required: list[str]) -> list[str]:
    return [key for key in required if env.get(key, "") == ""]


def _write_env_yaml(payload: dict[str, str]) -> str:
    handle = tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False)
    with handle:
        for key in sorted(payload):
            handle.write(f"{key}: {json.dumps(payload[key], ensure_ascii=False)}\n")
    return handle.name


def _run(command: list[str], *, dry_run: bool) -> int:
    print("$", " ".join(command))
    if dry_run:
        return 0
    completed = subprocess.run(command, cwd=PROJECT_ROOT)
    return completed.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", choices=("auth", "remote"))
    parser.add_argument("--region", default=DEFAULT_REGION)
    parser.add_argument("--project")
    parser.add_argument("--service")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    env = _load_env()
    project = args.project or env.get("GOOGLE_CLOUD_PROJECT") or env.get("GCLOUD_PROJECT")

    if args.target == "auth":
        service = args.service or DEFAULT_AUTH_SERVICE
        required = _required_keys_for_auth(env)
        payload = _build_auth_env(env)
        command_name = "kis-portfolio-auth"
        runtime_flags: list[str] = []
    else:
        service = args.service or DEFAULT_REMOTE_SERVICE
        required = _required_keys_for_remote(env)
        payload = _build_remote_env(env)
        command_name = "kis-portfolio-remote"
        runtime_flags = [
            "--concurrency",
            env.get("KIS_CLOUD_RUN_REMOTE_CONCURRENCY", DEFAULT_REMOTE_CONCURRENCY),
            "--max-instances",
            env.get("KIS_CLOUD_RUN_REMOTE_MAX_INSTANCES", DEFAULT_REMOTE_MAX_INSTANCES),
        ]

    missing = _validate_required(env, required)
    if missing:
        print("Missing required environment variables:")
        for key in missing:
            print(f"- {key}")
        return 1

    env_yaml_path = _write_env_yaml(payload)
    try:
        command = [
            "gcloud",
            "run",
            "deploy",
            service,
            "--source",
            ".",
            "--region",
            args.region,
            "--allow-unauthenticated",
            "--env-vars-file",
            env_yaml_path,
            "--command",
            "uv",
            "--args",
            f"run,{command_name}",
        ]
        command.extend(runtime_flags)
        if project:
            command.extend(["--project", project])
        return _run(command, dry_run=args.dry_run)
    finally:
        try:
            os.unlink(env_yaml_path)
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    sys.exit(main())
