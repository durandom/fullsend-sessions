"""Load configuration from env vars and ~/.config/fullsend/sessions.env."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

CONFIG_FILE = Path.home() / ".config" / "fullsend" / "sessions.env"
CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"


def _parse_env_file(path: Path) -> dict[str, str]:
    """Parse KEY=VALUE lines from a shell-style env file."""
    result: dict[str, str] = {}
    if not path.is_file():
        return result
    text = path.read_text()
    for match in re.finditer(
        r'^([A-Z_][A-Z0-9_]*)=["\']?([^"\'#\n]*)["\']?',
        text,
        re.MULTILINE,
    ):
        result[match.group(1)] = match.group(2).strip()
    return result


def get_sessions_repo() -> Path | None:
    """Return the sessions repo path, or None if not configured / missing."""
    repo = os.environ.get("FULLSEND_SESSIONS_REPO")
    if not repo:
        env_vars = _parse_env_file(CONFIG_FILE)
        repo = env_vars.get("FULLSEND_SESSIONS_REPO")
    if not repo:
        return None
    p = Path(repo)
    return p if p.is_dir() else None


def get_username() -> str:
    """Derive a lowercase, hyphenated username from git config or $USER."""
    try:
        name = subprocess.run(
            ["git", "config", "user.name"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        if name:
            return name.replace(" ", "-").lower()
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    return os.environ.get("USER", "unknown")


def get_project_name(cwd: str | None) -> str:
    """Extract a project name from a working directory path."""
    if cwd:
        return Path(cwd).name
    return "unknown"
