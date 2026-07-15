"""End-to-end tests for the installed-style CLI entry point."""

from __future__ import annotations

import json
from pathlib import Path

from fs_sessions.cli import main
from tests.conftest import make_transcript


def test_list_emits_discovered_sessions(isolated_env, capsys):
    make_transcript(isolated_env["claude_projects"], title="My Great Session")

    assert main(["list"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["count"] == 1
    assert payload["sessions"][0]["title"] == "My Great Session"


def test_share_last_uploads_complete_session_family(isolated_env, monkeypatch, capsys):
    transcript = make_transcript(isolated_env["claude_projects"])
    companions = transcript.parent / transcript.stem
    subagent = companions / "subagents" / "agent-child.jsonl"
    tool_result = companions / "tool-results" / "tool-1.txt"
    subagent.parent.mkdir(parents=True)
    tool_result.parent.mkdir(parents=True)
    subagent.write_text('{"type":"assistant"}\n')
    tool_result.write_text("full output")
    uploaded: dict[str, bytes] = {}

    def fake_upload(_config, paths, base, username, project):
        for path in paths:
            relative = path.relative_to(base / "sessions")
            session_relative = Path(*relative.parts[1:]).as_posix()
            uploaded[f"{username}/{project}/{session_relative}"] = path.read_bytes()
        return True

    monkeypatch.setattr("fs_sessions.s3.upload_session", fake_upload)

    assert main(["share", "--last"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["changed"] is True
    assert set(uploaded) == {
        "test-user/myproject/abc-123.jsonl",
        "test-user/myproject/abc-123/subagents/agent-child.jsonl",
        "test-user/myproject/abc-123/tool-results/tool-1.txt",
    }


def test_s3_first_init_uses_environment(tmp_path, monkeypatch, capsys):
    config_file = tmp_path / "config.json"
    monkeypatch.setenv("RHDH_SKILL_CONFIG", str(config_file))
    monkeypatch.setenv("S3_BUCKET", "team-sessions")
    monkeypatch.setenv("S3_REGION", "eu-test-1")
    monkeypatch.setattr("fs_sessions.cli._username", lambda: "test-user")

    assert main(["config", "init"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["storage"] == "s3"
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
