"""Thin subprocess wrappers for git operations."""

from __future__ import annotations

import subprocess
from pathlib import Path


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def add(repo: Path, filepath: str) -> bool:
    """Stage a file. Returns True on success."""
    r = _run(["git", "add", filepath], cwd=repo)
    return r.returncode == 0


def commit(repo: Path, message: str) -> bool:
    """Commit staged changes. Returns True on success."""
    r = _run(["git", "commit", "-q", "-m", message], cwd=repo)
    return r.returncode == 0


def pull_rebase(repo: Path) -> bool:
    """Pull with rebase. Returns True on success."""
    r = _run(["git", "pull", "--rebase", "-q"], cwd=repo)
    return r.returncode == 0


def push(repo: Path) -> bool:
    """Push to remote. Returns True on success."""
    r = _run(["git", "push", "-q"], cwd=repo)
    return r.returncode == 0
