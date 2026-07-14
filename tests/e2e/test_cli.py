"""End-to-end tests for CLI entry points."""

from __future__ import annotations

import io
import json
import subprocess

import pytest

from fs_sessions.cli import hook_main, main
from tests.conftest import make_transcript


class TestHookMain:
    def test_exports_transcript(self, isolated_env, monkeypatch):
        projects = isolated_env["claude_projects"]
        repo = isolated_env["sessions_repo"]
        transcript = make_transcript(projects)

        hook_input = json.dumps(
            {
                "transcript_path": str(transcript),
                "session_id": "abc-123",
                "cwd": "/Users/test/myproject",
            }
        )
        monkeypatch.setattr("sys.stdin", io.StringIO(hook_input))
        monkeypatch.setattr(
            "fs_sessions.config.subprocess.run",
            lambda *a, **kw: type(
                "R", (), {"stdout": "test-user\n", "returncode": 0}
            )(),
        )

        hook_main()

        exported = repo / "sessions" / "test-user_myproject" / "abc-123.jsonl"
        assert exported.exists()
        lines = exported.read_text().splitlines()
        meta = json.loads(lines[0])
        assert meta["type"] == "user"
        assert "myproject" in meta["message"]["content"]

    def test_never_raises(self, monkeypatch):
        monkeypatch.setattr("sys.stdin", io.StringIO("not json"))
        hook_main()

    def test_silent_on_missing_config(self, monkeypatch, tmp_path):
        monkeypatch.delenv("FULLSEND_SESSIONS_REPO", raising=False)
        monkeypatch.setattr("fs_sessions.config.CONFIG_FILE", tmp_path / "nope.env")
        monkeypatch.setattr(
            "sys.stdin",
            io.StringIO(
                json.dumps(
                    {
                        "transcript_path": "/tmp/x.jsonl",
                        "session_id": "s1",
                        "cwd": "/tmp",
                    }
                )
            ),
        )
        hook_main()


class TestMainList:
    def test_list_shows_sessions(self, isolated_env, capsys):
        projects = isolated_env["claude_projects"]
        make_transcript(projects, title="My Great Session")

        main(["--list"])

        captured = capsys.readouterr()
        assert "My Great Session" in captured.out
        assert "SIZE" in captured.out
        assert "MSGS" in captured.out

    def test_list_no_sessions(self, isolated_env):
        with pytest.raises(SystemExit) as exc_info:
            main(["--list"])
        assert exc_info.value.code == 1


class TestMainLast:
    def test_last_shares_session(self, isolated_env, monkeypatch, capsys):
        projects = isolated_env["claude_projects"]
        make_transcript(projects)

        monkeypatch.setattr(
            "fs_sessions.config.subprocess.run",
            lambda *a, **kw: type(
                "R", (), {"stdout": "test-user\n", "returncode": 0}
            )(),
        )
        monkeypatch.setattr("sys.stdin", io.StringIO("n\n"))
        monkeypatch.setattr("builtins.input", lambda _: "n")

        main(["--last"])
        captured = capsys.readouterr()
        assert "Copied" in captured.out

    def test_last_without_cwd_commits_fallback_project(self, isolated_env, monkeypatch):
        projects = isolated_env["claude_projects"]
        repo = isolated_env["sessions_repo"]
        transcript = make_transcript(
            projects,
            project_name="legacy-project",
            cwd=None,
        )

        monkeypatch.setattr(
            "fs_sessions.config.subprocess.run",
            lambda *a, **kw: type(
                "R", (), {"stdout": "test-user\n", "returncode": 0}
            )(),
        )
        monkeypatch.setattr("builtins.input", lambda _: "n")

        main(["--last"])

        exported = (
            repo / "sessions" / "test-user_Users-test-legacy-project" / transcript.name
        )
        assert exported.exists()
        assert (
            subprocess.run(
                ["git", "diff", "--quiet", "HEAD", "--", str(exported)],
                cwd=repo,
            ).returncode
            == 0
        )

    def test_git_failure_exits_nonzero(self, isolated_env, monkeypatch, capsys):
        projects = isolated_env["claude_projects"]
        make_transcript(projects)
        monkeypatch.setattr("fs_sessions.cli.add", lambda *a, **kw: False)

        with pytest.raises(SystemExit) as exc_info:
            main(["--last"])

        assert exc_info.value.code == 1
        assert "failed to stage" in capsys.readouterr().err


class TestMainErrors:
    def test_no_sessions_exits_1(self, isolated_env):
        with pytest.raises(SystemExit) as exc_info:
            main(["--list"])
        assert exc_info.value.code == 1
