"""Tests for fs_sessions.git — all subprocess calls are monkeypatched."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import fs_sessions.git as git_mod


def _mock_run(returncode=0):
    mock = MagicMock()
    mock.return_value.returncode = returncode
    return mock


class TestGitAdd:
    def test_success(self, monkeypatch):
        mock = _mock_run(0)
        monkeypatch.setattr(git_mod, "_run", mock)
        assert git_mod.add(Path("/repo"), "sessions/file.jsonl") is True
        mock.assert_called_once_with(
            ["git", "add", "sessions/file.jsonl"], cwd=Path("/repo")
        )

    def test_failure(self, monkeypatch):
        monkeypatch.setattr(git_mod, "_run", _mock_run(1))
        assert git_mod.add(Path("/repo"), "file") is False


class TestGitCommit:
    def test_success(self, monkeypatch):
        mock = _mock_run(0)
        monkeypatch.setattr(git_mod, "_run", mock)
        assert git_mod.commit(Path("/repo"), "msg") is True
        args = mock.call_args[0][0]
        assert args == ["git", "commit", "-q", "-m", "msg"]

    def test_failure(self, monkeypatch):
        monkeypatch.setattr(git_mod, "_run", _mock_run(128))
        assert git_mod.commit(Path("/repo"), "msg") is False


class TestGitPullRebase:
    def test_success(self, monkeypatch):
        mock = _mock_run(0)
        monkeypatch.setattr(git_mod, "_run", mock)
        assert git_mod.pull_rebase(Path("/repo")) is True
        args = mock.call_args[0][0]
        assert "pull" in args and "--rebase" in args

    def test_failure(self, monkeypatch):
        monkeypatch.setattr(git_mod, "_run", _mock_run(1))
        assert git_mod.pull_rebase(Path("/repo")) is False


class TestGitPush:
    def test_success(self, monkeypatch):
        mock = _mock_run(0)
        monkeypatch.setattr(git_mod, "_run", mock)
        assert git_mod.push(Path("/repo")) is True
        args = mock.call_args[0][0]
        assert args == ["git", "push", "-q"]

    def test_failure(self, monkeypatch):
        monkeypatch.setattr(git_mod, "_run", _mock_run(1))
        assert git_mod.push(Path("/repo")) is False
