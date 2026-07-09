"""Tests for fs_sessions.discovery."""

from __future__ import annotations

import json
import time
from pathlib import Path

from fs_sessions.discovery import (
    _extract_cwd,
    _extract_title,
    discover_sessions,
    display_project,
    human_size,
)
from tests.conftest import make_transcript


class TestExtractTitle:
    def test_finds_title(self, tmp_path):
        f = tmp_path / "s.jsonl"
        f.write_text(
            json.dumps({"type": "user", "message": {"content": "hi"}})
            + "\n"
            + json.dumps({"type": "ai-title", "aiTitle": "My Session"})
            + "\n"
        )
        assert _extract_title(f) == "My Session"

    def test_uses_last_title(self, tmp_path):
        f = tmp_path / "s.jsonl"
        f.write_text(
            json.dumps({"type": "ai-title", "aiTitle": "First"})
            + "\n"
            + json.dumps({"type": "ai-title", "aiTitle": "Second"})
            + "\n"
        )
        assert _extract_title(f) == "Second"

    def test_untitled_when_missing(self, tmp_path):
        f = tmp_path / "s.jsonl"
        f.write_text(json.dumps({"type": "user"}) + "\n")
        assert _extract_title(f) == "(untitled)"

    def test_handles_missing_file(self, tmp_path):
        assert _extract_title(tmp_path / "nope.jsonl") == "(untitled)"


class TestExtractCwd:
    def test_finds_cwd(self, tmp_path):
        f = tmp_path / "s.jsonl"
        f.write_text(
            json.dumps(
                {
                    "type": "user",
                    "sessionId": "123",
                    "cwd": "/home/me/proj",
                    "message": {"content": "hi"},
                }
            )
            + "\n"
        )
        assert _extract_cwd(f) == "/home/me/proj"

    def test_returns_none_when_missing(self, tmp_path):
        f = tmp_path / "s.jsonl"
        f.write_text(json.dumps({"type": "user", "message": {"content": "hi"}}) + "\n")
        assert _extract_cwd(f) is None


class TestDiscoverSessions:
    def test_finds_sessions(self, isolated_env):
        projects = isolated_env["claude_projects"]
        make_transcript(projects, session_id="s1", title="First")
        sessions = discover_sessions(projects)
        assert len(sessions) == 1
        assert sessions[0].title == "First"

    def test_sorted_by_mtime_descending(self, isolated_env):
        projects = isolated_env["claude_projects"]
        make_transcript(projects, session_id="old", title="Old")
        time.sleep(0.05)
        make_transcript(projects, session_id="new", title="New")

        sessions = discover_sessions(projects)
        assert len(sessions) == 2
        assert sessions[0].title == "New"
        assert sessions[1].title == "Old"

    def test_respects_max_results(self, isolated_env):
        projects = isolated_env["claude_projects"]
        for i in range(5):
            make_transcript(projects, session_id=f"s{i}", title=f"S{i}")
        sessions = discover_sessions(projects, max_results=3)
        assert len(sessions) == 3

    def test_empty_dir(self, isolated_env):
        projects = isolated_env["claude_projects"]
        assert discover_sessions(projects) == []


class TestHumanSize:
    def test_bytes(self):
        assert human_size(500) == "500B"

    def test_kilobytes(self):
        assert human_size(2048) == "2K"

    def test_megabytes(self):
        assert human_size(3_145_728) == "3M"

    def test_zero(self):
        assert human_size(0) == "0B"


class TestDisplayProject:
    def test_with_cwd(self):
        from fs_sessions.discovery import SessionInfo

        s = SessionInfo(path=Path("/x"), mtime=0, title="t", cwd="/Users/me/src/proj")
        assert display_project(s) == "src/proj"

    def test_without_cwd(self):
        from fs_sessions.discovery import SessionInfo

        s = SessionInfo(
            path=Path("/projects/my-proj/abc.jsonl"),
            mtime=0,
            title="t",
            cwd=None,
        )
        assert display_project(s) == "my-proj"
