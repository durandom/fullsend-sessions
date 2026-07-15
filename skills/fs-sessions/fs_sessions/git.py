"""Small, testable wrappers around the Git operations used by the hook."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import List


def run(repo: Path, args: List[str]) -> bool:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def commit_file(repo: Path, relative_path: str, message: str) -> bool:
    """Commit only the exported transcript, leaving unrelated staged files alone."""
    return commit_files(repo, [relative_path], message)


def commit_files(repo: Path, relative_paths: List[str], message: str) -> bool:
    """Commit one session family without including unrelated staged changes."""
    paths = list(dict.fromkeys(relative_paths))
    if not paths:
        return False
    if not run(repo, ["add", "--", *paths]):
        return False
    return run(repo, ["commit", "-q", "--only", "-m", message, "--", *paths])


def pull_rebase(repo: Path) -> bool:
    return run(repo, ["pull", "--rebase", "-q"])


def push(repo: Path) -> bool:
    return run(repo, ["push", "-q"])
