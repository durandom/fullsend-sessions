"""Tests for the optional S3 session backend."""

from __future__ import annotations

from fs_sessions import s3


class FakeClient:
    def __init__(self):
        self.uploads = []

    def upload_file(self, path, bucket, key):
        self.uploads.append((path, bucket, key))


def test_upload_preserves_complete_session_family_layout(tmp_path, monkeypatch):
    base = tmp_path / "export"
    project_dir = base / "sessions" / "user_project"
    parent = project_dir / "session.jsonl"
    subagent = project_dir / "session" / "subagents" / "agent-child.jsonl"
    tool_result = project_dir / "session" / "tool-results" / "tool-1.txt"
    parent.parent.mkdir(parents=True)
    subagent.parent.mkdir(parents=True)
    tool_result.parent.mkdir(parents=True)
    parent.write_text("parent")
    subagent.write_text("child")
    tool_result.write_text("tool output")
    client = FakeClient()
    monkeypatch.setattr(s3, "_get_client", lambda _config: client)

    assert s3.upload_session(
        {"bucket": "sessions", "prefix": "team"},
        [parent, subagent, tool_result],
        base,
        "user",
        "project",
    )

    assert {key for _, _, key in client.uploads} == {
        "team/user/raw/claude/project/session.jsonl",
        "team/user/raw/claude/project/session/subagents/agent-child.jsonl",
        "team/user/raw/claude/project/session/tool-results/tool-1.txt",
    }
