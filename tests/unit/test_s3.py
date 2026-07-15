"""Tests for S3 session storage."""

from __future__ import annotations

import io
import json

from fs_sessions import s3


class FakeClient:
    def __init__(self, objects=None, bodies=None):
        self.uploads = []
        self.puts = []
        self.objects = objects or []
        self.bodies = bodies or {}

    def upload_file(self, path, bucket, key):
        self.uploads.append((path, bucket, key))

    def list_objects_v2(self, **_kwargs):
        return {"Contents": [{"Key": key} for key in self.objects]}

    def head_object(self, Bucket, Key):
        if Key not in self.objects:
            error = RuntimeError("missing")
            error.response = {"Error": {"Code": "404"}}
            raise error
        return {"Bucket": Bucket, "Key": Key}

    def put_object(self, **kwargs):
        self.puts.append(kwargs)

    def get_object(self, Bucket, Key):
        return {"Bucket": Bucket, "Key": Key, "Body": io.BytesIO(self.bodies[Key])}

    def delete_objects(self, **kwargs):
        self.deletes = getattr(self, "deletes", [])
        self.deletes.append(kwargs)
        return {}


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


def test_check_and_discover_agentsview_roots(monkeypatch):
    client = FakeClient(
        [
            "team/alice/raw/claude/project/a.jsonl",
            "team/bob/raw/claude/project/b.jsonl",
            "team/alice/raw/claude/project/a/tool-results/tool.txt",
            "team/ignored/raw/codex/2026/01/01/rollout.jsonl",
        ]
    )
    monkeypatch.setattr(s3, "_get_client", lambda _config: client)
    config = {"bucket": "sessions", "region": "eu-test-1", "prefix": "team"}

    assert s3.check_access(config) == {
        "success": True,
        "bucket": "sessions",
        "region": "eu-test-1",
        "can_list": True,
        "has_objects": True,
    }
    assert s3.discover_claude_roots(config) == [
        "s3://sessions/team/alice/raw/claude",
        "s3://sessions/team/bob/raw/claude",
    ]


def test_generic_object_checks_and_ordered_upload(monkeypatch):
    client = FakeClient(["existing"])
    monkeypatch.setattr(s3, "_get_client", lambda _config: client)
    config = {"bucket": "sessions"}

    assert s3.object_exists(config, "existing") is True
    assert s3.object_exists(config, "missing") is False

    s3.upload_objects(
        config,
        [("child.jsonl", b"child"), ("parent.jsonl", b"parent")],
    )

    assert [item["Key"] for item in client.puts] == [
        "child.jsonl",
        "parent.jsonl",
    ]
    assert all(item["ContentType"] == "application/x-ndjson" for item in client.puts)


def test_read_json_and_delete_objects(monkeypatch):
    client = FakeClient(bodies={"manifest.json": b'{"schema_version":3}'})
    monkeypatch.setattr(s3, "_get_client", lambda _config: client)

    assert s3.read_json_object({"bucket": "sessions"}, "manifest.json") == {
        "schema_version": 3
    }
    s3.delete_objects({"bucket": "sessions"}, ["old-parent", "old-child"])

    assert client.deletes[0]["Delete"]["Objects"] == [
        {"Key": "old-parent"},
        {"Key": "old-child"},
    ]


def test_repair_export_project_metadata_previews_and_applies(monkeypatch):
    key = "alice/raw/claude/example-repo/session.jsonl"
    old_cwd = "/sessions/alice_example-repo"
    header = {
        "type": "user",
        "message": {"content": f"[Session: example-repo] by alice\nProject: {old_cwd}"},
        "cwd": old_cwd,
    }
    original = json.dumps(header).encode() + b'\n{"type":"assistant"}\n'
    client = FakeClient([key], {key: original})
    monkeypatch.setattr(s3, "_get_client", lambda _config: client)

    preview = s3.repair_export_project_metadata({"bucket": "sessions"})

    assert preview == {"success": True, "apply": False, "scanned": 1, "changed": 1}
    assert client.puts == []

    applied = s3.repair_export_project_metadata({"bucket": "sessions"}, apply=True)

    assert applied["changed"] == 1
    repaired = client.puts[0]["Body"]
    first, rest = repaired.split(b"\n", 1)
    metadata = json.loads(first)
    assert metadata["cwd"] == "/sessions/example-repo"
    assert "alice_example-repo" not in metadata["message"]["content"]
    assert rest == b'{"type":"assistant"}\n'


def test_agentsview_config_updates_roots_and_preserves_secrets(tmp_path, monkeypatch):
    data_dir = tmp_path / "agentsview"
    data_dir.mkdir()
    config_file = data_dir / "config.toml"
    config_file.write_text(
        'auth_token = "keep-me"\n'
        'claude_project_dirs = ["s3://old/old/raw/claude"]\n'
        'cursor_secret = "also-keep-me"\n'
    )
    monkeypatch.setattr(
        s3,
        "discover_claude_roots",
        lambda _config: [
            "s3://sessions/fs-code/raw/claude",
            "s3://sessions/user/raw/claude",
        ],
    )

    result = s3.write_agentsview_config({"bucket": "sessions"}, data_dir)

    assert result["count"] == 2
    content = config_file.read_text()
    assert 'auth_token = "keep-me"' in content
    assert 'cursor_secret = "also-keep-me"' in content
    assert "s3://old/old/raw/claude" not in content
    assert '  "s3://sessions/fs-code/raw/claude",' in content
    assert '  "s3://sessions/user/raw/claude",' in content
    assert config_file.stat().st_mode & 0o777 == 0o600
