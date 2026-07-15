"""End-to-end tests for the installed-style CLI entry point."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from fs_sessions.cli import main
from tests.conftest import make_transcript


def test_list_emits_discovered_sessions(isolated_env, capsys):
    make_transcript(isolated_env["claude_projects"], title="My Great Session")

    assert main(["list"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["count"] == 1
    assert payload["sessions"][0]["title"] == "My Great Session"


def test_share_last_commits_only_transcript(isolated_env, monkeypatch, capsys):
    transcript = make_transcript(isolated_env["claude_projects"])
    companions = transcript.parent / transcript.stem
    subagent = companions / "subagents" / "agent-child.jsonl"
    tool_result = companions / "tool-results" / "tool-1.txt"
    subagent.parent.mkdir(parents=True)
    tool_result.parent.mkdir(parents=True)
    subagent.write_text('{"type":"assistant"}\n')
    tool_result.write_text("full output")
    repo = isolated_env["sessions_repo"]
    unrelated = repo / "unrelated"
    unrelated.write_text("keep staged")
    subprocess.run(["git", "add", "unrelated"], cwd=repo, check=True)
    monkeypatch.setattr("fs_sessions.cli._username", lambda: "test-user")

    assert main(["share", "--last"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["changed"] is True
    exported = repo / "sessions" / "test-user_myproject" / transcript.name
    assert exported.exists()
    exported_family = exported.with_suffix("")
    assert (
        exported_family / "subagents" / subagent.name
    ).read_text() == subagent.read_text()
    assert (exported_family / "tool-results" / tool_result.name).read_text() == (
        tool_result.read_text()
    )
    committed = subprocess.run(
        ["git", "show", "--pretty=", "--name-only", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    assert set(committed) == {
        exported.relative_to(repo).as_posix(),
        (exported_family / "subagents" / subagent.name).relative_to(repo).as_posix(),
        (exported_family / "tool-results" / tool_result.name)
        .relative_to(repo)
        .as_posix(),
    }
    assert (
        subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", "unrelated"], cwd=repo
        ).returncode
        == 1
    )


def test_s3_first_init_uses_environment(tmp_path, monkeypatch, capsys):
    config_file = tmp_path / "config.json"
    monkeypatch.setenv("RHDH_SKILL_CONFIG", str(config_file))
    monkeypatch.setenv("S3_BUCKET", "team-sessions")
    monkeypatch.setenv("S3_REGION", "eu-test-1")
    monkeypatch.setattr("fs_sessions.cli._username", lambda: "test-user")

    assert main(["config", "init"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["backends"] == ["s3"]
    assert payload["sessions"]["s3"] == {
        "bucket": "team-sessions",
        "region": "eu-test-1",
    }
    assert payload["sessions"]["machine"] == "test-user"


def test_s3_share_cleans_staging_directory(isolated_env, monkeypatch, capsys):
    transcript = make_transcript(isolated_env["claude_projects"])
    config_file = isolated_env["config_file"]
    data = json.loads(config_file.read_text())
    data["sessions"].update(
        {
            "backends": ["s3"],
            "machine": "test-user",
            "s3": {"bucket": "team-sessions", "region": "eu-test-1"},
        }
    )
    config_file.write_text(json.dumps(data))
    staged_paths: list[Path] = []

    def fake_upload(_config, paths, _base, _username, _project):
        staged_paths.extend(paths)
        assert all(path.exists() for path in paths)
        return True

    monkeypatch.setattr("fs_sessions.s3.upload_session", fake_upload)

    assert main(["share", "--last"]) == 0
    assert json.loads(capsys.readouterr().out)["success"] is True
    assert staged_paths
    assert all(not path.exists() for path in staged_paths)

    monkeypatch.setattr("fs_sessions.s3.upload_session", lambda *_args: False)
    assert main(["share", "--transcript", str(transcript)]) == 1
    assert json.loads(capsys.readouterr().out)["success"] is False
