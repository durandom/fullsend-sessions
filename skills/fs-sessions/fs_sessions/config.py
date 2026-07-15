"""Global and project-local configuration for session sharing."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

USER_CONFIG_ENV = "RHDH_SKILL_CONFIG"
USER_CONFIG_FILE = Path.home() / ".config" / "rhdh-skill" / "config.json"
PROJECT_CONFIG_DIR = ".rhdh"
CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"


class ConfigError(ValueError):
    """Raised when session configuration is missing or invalid."""


def get_user_config_path() -> Path:
    """Return the user configuration path, honoring the test/automation override."""
    override = os.environ.get(USER_CONFIG_ENV)
    return Path(override).expanduser() if override else USER_CONFIG_FILE


def load_json(path: Path, missing_ok: bool = True) -> Dict[str, Any]:
    """Load a JSON object without silently accepting malformed configuration."""
    if not path.exists():
        if missing_ok:
            return {}
        raise ConfigError(f"configuration not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"invalid configuration {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"configuration must contain a JSON object: {path}")
    return data


def load_user_config(missing_ok: bool = True) -> Dict[str, Any]:
    return load_json(get_user_config_path(), missing_ok=missing_ok)


def save_user_config(data: Dict[str, Any]) -> Path:
    """Atomically save global config while preserving unrelated rhdh-skill keys."""
    path = get_user_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix="config-", suffix=".json", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, indent=2, sort_keys=True)
            stream.write("\n")
        os.chmod(temp_name, 0o600)
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise
    return path


def _initialize_policy(sessions: Dict[str, Any], default: str) -> None:
    if default not in {"allow", "deny"}:
        raise ConfigError("policy default must be 'allow' or 'deny'")
    sessions.setdefault("enabled", True)
    policy = sessions.setdefault("policy", {})
    if not isinstance(policy, dict):
        raise ConfigError("config key 'sessions.policy' must be an object")
    policy.setdefault("default", default)
    policy.setdefault("rules", [])


def _sessions_object(data: Dict[str, Any]) -> Dict[str, Any]:
    sessions = data.setdefault("sessions", {})
    if not isinstance(sessions, dict):
        raise ConfigError("config key 'sessions' must be an object")
    return sessions


def validate_machine(machine: str) -> str:
    machine = machine.strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", machine):
        raise ConfigError(
            "machine must start with a letter or digit and contain only "
            "letters, digits, dots, underscores, or hyphens"
        )
    return machine


def initialize_s3_sessions_config(
    bucket: str,
    region: str,
    machine: str,
    default: str = "deny",
    profile: Optional[str] = None,
    endpoint_url: Optional[str] = None,
    prefix: Optional[str] = None,
) -> Dict[str, Any]:
    """Initialize S3 as the sole default backend without storing credentials."""
    bucket = bucket.strip()
    region = region.strip()
    if not bucket:
        raise ConfigError("S3 bucket is required (--bucket or S3_BUCKET)")
    if not region:
        raise ConfigError("S3 region is required (--region or S3_REGION)")

    data = load_user_config()
    sessions = _sessions_object(data)
    _initialize_policy(sessions, default)
    sessions["backends"] = ["s3"]
    sessions["machine"] = validate_machine(machine)
    s3: Dict[str, Any] = {"bucket": bucket, "region": region}
    for key, value in (
        ("profile", profile),
        ("endpoint_url", endpoint_url),
        ("prefix", prefix),
    ):
        if value:
            s3[key] = value
    sessions["s3"] = s3
    save_user_config(data)
    return data


def initialize_sessions_config(repo: Path, default: str = "deny") -> Dict[str, Any]:
    """Initialize the explicit legacy Git backend."""
    repo = repo.expanduser().resolve()
    if not repo.is_dir():
        raise ConfigError(f"sessions repository does not exist: {repo}")

    data = load_user_config()
    repos = data.setdefault("repos", {})
    if not isinstance(repos, dict):
        raise ConfigError("config key 'repos' must be an object")
    repos["sessions"] = str(repo)
    sessions = _sessions_object(data)
    _initialize_policy(sessions, default)
    sessions["backends"] = ["git"]
    save_user_config(data)
    return data


def get_sessions_config(data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    config = data if data is not None else load_user_config(missing_ok=False)
    sessions = config.get("sessions")
    if not isinstance(sessions, dict):
        raise ConfigError("missing config object: sessions")
    return sessions


def get_sessions_repo(data: Optional[Dict[str, Any]] = None) -> Path:
    config = data if data is not None else load_user_config(missing_ok=False)
    repos = config.get("repos")
    repo_value = repos.get("sessions") if isinstance(repos, dict) else None
    if not isinstance(repo_value, str) or not repo_value:
        raise ConfigError("missing config key: repos.sessions")
    repo = Path(repo_value).expanduser().resolve()
    if not repo.is_dir():
        raise ConfigError(f"sessions repository does not exist: {repo}")
    return repo


def find_project_config(git_root: Path) -> Path:
    return git_root / PROJECT_CONFIG_DIR / "config.json"


def project_disables_sessions(git_root: Path) -> bool:
    """Project config may opt out, but cannot elevate global permission."""
    path = find_project_config(git_root)
    if not path.exists():
        return False
    data = load_json(path)
    sessions = data.get("sessions")
    return isinstance(sessions, dict) and sessions.get("enabled") is False


def get_backends(data: Optional[Dict[str, Any]] = None) -> list[str]:
    """Return validated backends; missing values retain legacy Git behavior."""
    config = data if data is not None else load_user_config(missing_ok=False)
    sessions = config.get("sessions", {})
    backends = sessions.get("backends", ["git"])
    if not isinstance(backends, list) or not backends:
        raise ConfigError("sessions.backends must be a non-empty list")
    if any(backend not in {"s3", "git"} for backend in backends):
        raise ConfigError("sessions.backends may contain only 's3' and 'git'")
    return backends


def get_machine(data: Optional[Dict[str, Any]] = None) -> Optional[str]:
    config = data if data is not None else load_user_config(missing_ok=False)
    sessions = config.get("sessions", {})
    machine = sessions.get("machine") if isinstance(sessions, dict) else None
    return validate_machine(machine) if isinstance(machine, str) else None


def get_s3_config(data: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """Return S3 config dict, or None if not configured."""
    config = data if data is not None else load_user_config(missing_ok=False)
    sessions = config.get("sessions", {})
    s3 = sessions.get("s3")
    if isinstance(s3, dict) and s3.get("bucket"):
        return s3
    return None
