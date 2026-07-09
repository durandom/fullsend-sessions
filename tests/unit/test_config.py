"""Tests for fs_sessions.config."""

from __future__ import annotations

from fs_sessions.config import (
    _parse_env_file,
    get_project_name,
    get_sessions_repo,
    get_username,
)


class TestParseEnvFile:
    def test_simple_key_value(self, tmp_path):
        f = tmp_path / "env"
        f.write_text("FULLSEND_SESSIONS_REPO=/some/path\n")
        assert _parse_env_file(f) == {"FULLSEND_SESSIONS_REPO": "/some/path"}

    def test_quoted_value(self, tmp_path):
        f = tmp_path / "env"
        f.write_text('FULLSEND_SESSIONS_REPO="/some/path"\n')
        assert _parse_env_file(f) == {"FULLSEND_SESSIONS_REPO": "/some/path"}

    def test_single_quoted(self, tmp_path):
        f = tmp_path / "env"
        f.write_text("FULLSEND_SESSIONS_REPO='/some/path'\n")
        assert _parse_env_file(f) == {"FULLSEND_SESSIONS_REPO": "/some/path"}

    def test_comments_ignored(self, tmp_path):
        f = tmp_path / "env"
        f.write_text("# comment\nKEY=value\n")
        assert _parse_env_file(f) == {"KEY": "value"}

    def test_missing_file(self, tmp_path):
        assert _parse_env_file(tmp_path / "nope") == {}

    def test_multiple_keys(self, tmp_path):
        f = tmp_path / "env"
        f.write_text("A=1\nB=2\n")
        assert _parse_env_file(f) == {"A": "1", "B": "2"}


class TestGetSessionsRepo:
    def test_env_var_takes_priority(self, monkeypatch, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        monkeypatch.setenv("FULLSEND_SESSIONS_REPO", str(repo))
        assert get_sessions_repo() == repo

    def test_falls_back_to_config_file(self, isolated_env):
        repo = isolated_env["sessions_repo"]
        assert get_sessions_repo() == repo

    def test_returns_none_when_unconfigured(self, monkeypatch, tmp_path):
        monkeypatch.delenv("FULLSEND_SESSIONS_REPO", raising=False)
        monkeypatch.setattr("fs_sessions.config.CONFIG_FILE", tmp_path / "missing.env")
        assert get_sessions_repo() is None

    def test_returns_none_when_dir_missing(self, monkeypatch, tmp_path):
        monkeypatch.setenv("FULLSEND_SESSIONS_REPO", str(tmp_path / "nope"))
        assert get_sessions_repo() is None


class TestGetUsername:
    def test_from_git_config(self, monkeypatch):
        monkeypatch.setattr(
            "fs_sessions.config.subprocess.run",
            lambda *a, **kw: type(
                "R", (), {"stdout": "Marcel Hild\n", "returncode": 0}
            )(),
        )
        assert get_username() == "marcel-hild"

    def test_fallback_to_user_env(self, monkeypatch):
        import subprocess as sp

        monkeypatch.setattr(
            "fs_sessions.config.subprocess.run",
            lambda *a, **kw: (_ for _ in ()).throw(sp.CalledProcessError(1, "git")),
        )
        monkeypatch.setenv("USER", "testuser")
        assert get_username() == "testuser"


class TestGetProjectName:
    def test_from_cwd(self):
        assert get_project_name("/Users/me/src/myproject") == "myproject"

    def test_none_returns_unknown(self):
        assert get_project_name(None) == "unknown"
