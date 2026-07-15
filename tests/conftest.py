"""Shared fixtures for fs-sessions tests."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest


@dataclass
class CLIResult:
    exit_code: int
    stdout: str
    stderr: str


@pytest.fixture()
def isolated_env(tmp_path, monkeypatch):
    """Set up an isolated test environment."""
    claude_projects = tmp_path / "claude-projects"
    claude_projects.mkdir()

    config_dir = tmp_path / "config" / "rhdh-skill"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "config.json"
    config_file.write_text(
        json.dumps(
            {
                "sessions": {
                    "enabled": True,
                    "machine": "test-user",
                    "s3": {"bucket": "team-sessions", "region": "eu-test-1"},
                    "policy": {"default": "deny", "rules": []},
                },
            }
        )
    )

    monkeypatch.setenv("RHDH_SKILL_CONFIG", str(config_file))
    monkeypatch.setattr("fs_sessions.config.CLAUDE_PROJECTS_DIR", claude_projects)
    monkeypatch.setattr("fs_sessions.discovery.CLAUDE_PROJECTS_DIR", claude_projects)

    return {
        "claude_projects": claude_projects,
        "config_file": config_file,
    }


def make_transcript(
    projects_dir: Path,
    project_name: str = "test-project",
    session_id: str = "abc-123",
    title: str = "Test Session",
    cwd: str | None = "/Users/test/myproject",
) -> Path:
    """Create a fake JSONL transcript in the Claude projects dir."""
    project_dir = projects_dir / f"-Users-test-{project_name}"
    project_dir.mkdir(parents=True, exist_ok=True)
    jsonl = project_dir / f"{session_id}.jsonl"

    lines = [
        json.dumps(
            {
                "type": "user",
                "sessionId": session_id,
                "cwd": cwd,
                "message": {"content": "hello"},
            }
        ),
        json.dumps({"type": "ai-title", "aiTitle": title}),
        json.dumps(
            {
                "type": "assistant",
                "message": {"content": "hi there"},
            }
        ),
    ]
    jsonl.write_text("\n".join(lines) + "\n")
    return jsonl
