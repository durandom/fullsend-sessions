"""Tests for GitHub Fullsend artifact conversion and S3 import."""

from __future__ import annotations

import io
import json
import zipfile

from fs_sessions.fullsend import (
    Artifact,
    ArtifactInput,
    GitHubClient,
    cached_artifact_inputs,
    convert_artifact,
    import_cached_artifacts,
    manifest_key,
)


def artifact_zip() -> bytes:
    stream = io.BytesIO()
    root = "agent-code-89-123/iteration-1"
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr(
            f"{root}/transcripts/code-session-1.jsonl",
            "\n".join(
                [
                    json.dumps({"type": "ai-title", "aiTitle": "Old title"}),
                    json.dumps({"type": "queue-operation", "content": "internal"}),
                    json.dumps(
                        {
                            "type": "user",
                            "message": {"content": "Do work"},
                            "cwd": "/target-repo",
                            "sessionId": "session-1",
                        }
                    ),
                    json.dumps(
                        {
                            "type": "assistant",
                            "message": {"content": "Done"},
                        }
                    ),
                ]
            )
            + "\n",
        )
        archive.writestr(
            f"{root}/transcripts/code-agent-a123.jsonl",
            (
                '{"type":"user","cwd":"/target-repo",'
                '"sessionId":"session-1",'
                '"message":{"content":"delegate"}}\n'
                '{"type":"assistant","message":{"content":"child"}}\n'
            ),
        )
        archive.writestr(
            "agent-code-89-123/run-summary.json",
            json.dumps(
                {
                    "fullsend.work_item_id": (
                        "https://github.com/redhat-developer/rhdh-agentic/issues/89"
                    ),
                    "duration_ms": 215900,
                    "metrics": {"total_cost_usd": 0.44, "num_turns": 19},
                }
            ),
        )
        archive.writestr(
            f"{root}/output/agent-result.json",
            json.dumps({"comment": "Structured final result"}),
        )
        archive.writestr(
            f"{root}/output.jsonl",
            json.dumps(
                {
                    "type": "system",
                    "subtype": "init",
                    "model": "claude-test",
                    "tools": ["Read", "Bash"],
                }
            )
            + "\n",
        )
    return stream.getvalue()


def artifact_input() -> ArtifactInput:
    artifact = Artifact(
        id="1234",
        name="fullsend-code",
        run_id="9876",
        created="2026-07-15T12:00:00Z",
        repo="redhat-developer/rhdh-agentic",
    )
    return ArtifactInput(
        artifact=artifact,
        zip_bytes=artifact_zip(),
        provenance={
            "run_id": artifact.run_id,
            "repo": artifact.repo,
            "artifact_id": artifact.id,
            "artifact_name": artifact.name,
            "agent_name": "code",
            "conclusion": "success",
            "run_url": "https://github.example/run/9876",
            "created": artifact.created,
            "head_sha": "deadbeef",
            "job_name": "Code",
            "context": {"agent": ".fullsend/agents/code.md"},
        },
        workflow_log=b"workflow output\n",
        context_files={"agent": b"You are the code agent.\n"},
    )


def test_convert_maps_repo_to_project_and_fs_agent_to_machine():
    converted = convert_artifact(artifact_input(), prefix="team")

    assert converted.project == "rhdh-agentic"
    assert converted.machine == "fs-code"
    assert converted.session_id == "session-1"
    keys = [key for key, _ in converted.objects]
    assert keys[0] == (
        "team/fs-code/raw/claude/rhdh-agentic/session-1/subagents/agent-a123.jsonl"
    )
    assert keys[1] == ("team/fs-code/raw/claude/rhdh-agentic/session-1.jsonl")
    child = converted.objects[0][1].decode()
    parent = converted.objects[1][1].decode()
    assert '"cwd":"/fullsend/rhdh-agentic"' in child
    assert "/target-repo" not in child
    assert '"cwd":"/fullsend/rhdh-agentic"' in parent
    assert "/target-repo" not in parent
    assert "code issue #89 - run 9876 [success · $0.44 · 215s · 19 turns]" in parent
    assert "📋 Fullsend Execution Context" in parent
    assert "You are the code agent." in parent
    assert "Structured final result" in parent
    assert "queue-operation" not in parent
    assert '"aiTitle":"code issue #89 - run 9876' in parent
    assert converted.manifest["machine"] == "fs-code"
    assert converted.manifest["project"] == "rhdh-agentic"
    assert converted.manifest["subagent_count"] == 1
    assert converted.manifest["schema_version"] == 3


def test_import_is_idempotent_and_writes_manifest_last(monkeypatch):
    data = artifact_input()
    uploads = []
    monkeypatch.setattr("fs_sessions.fullsend.object_exists", lambda *_: False)
    monkeypatch.setattr(
        "fs_sessions.fullsend.upload_objects",
        lambda _config, objects: uploads.extend(objects),
    )
    monkeypatch.setattr("fs_sessions.fullsend.delete_objects", lambda *_: None)

    summary = import_cached_artifacts({"bucket": "sessions", "prefix": "team"}, [data])

    assert summary.to_dict()["success"] is True
    assert summary.sessions == 1
    assert summary.subagents == 1
    assert uploads[-1][0] == manifest_key("team", data.artifact)
    manifest = json.loads(uploads[-1][1])
    assert manifest["destinations"][-1].endswith("session-1.jsonl")

    monkeypatch.setattr("fs_sessions.fullsend.object_exists", lambda *_: True)
    second = import_cached_artifacts({"bucket": "sessions"}, [data])
    assert second.skipped == 1
    assert second.imported == 0


def test_force_migration_removes_obsolete_generated_destinations(monkeypatch):
    data = artifact_input()
    uploads = []
    deleted = []
    old_parent = "team/fs-code/raw/claude/rhdh-agentic/code-session-1.jsonl"
    old_child = (
        "team/fs-code/raw/claude/rhdh-agentic/code-session-1/subagents/agent-a123.jsonl"
    )
    monkeypatch.setattr(
        "fs_sessions.fullsend.read_json_object",
        lambda *_: {"destinations": [old_child, old_parent]},
    )
    monkeypatch.setattr(
        "fs_sessions.fullsend.upload_objects",
        lambda _config, objects: uploads.append(objects),
    )
    monkeypatch.setattr(
        "fs_sessions.fullsend.delete_objects",
        lambda _config, keys: deleted.extend(keys),
    )

    summary = import_cached_artifacts(
        {"bucket": "sessions", "prefix": "team"}, [data], force=True
    )

    assert summary.failed == 0
    assert deleted == sorted([old_child, old_parent])
    assert uploads[-1][0][0] == manifest_key("team", data.artifact)


def test_cached_artifact_loader_uses_old_sidecars(tmp_path):
    repo_dir = tmp_path / "rhdh-agentic"
    repo_dir.mkdir()
    zip_path = repo_dir / "9876_fullsend-code.zip"
    zip_path.write_bytes(artifact_zip())
    (repo_dir / "9876_fullsend-code.log").write_text("workflow\n")
    (repo_dir / "9876_fullsend-code.json").write_text(
        json.dumps(artifact_input().provenance)
    )
    revision = repo_dir / "revisions" / "deadbeef"
    revision.mkdir(parents=True)
    (revision / "CLAUDE.md").write_text("Project instructions")

    loaded = cached_artifact_inputs(tmp_path)

    assert len(loaded) == 1
    assert loaded[0].artifact.fs_agent == "fs-code"
    assert loaded[0].workflow_log == b"workflow\n"
    assert loaded[0].context_files["CLAUDE.md"] == b"Project instructions"


def test_github_artifact_listing_filters_expired_and_run(monkeypatch):
    client = GitHubClient()
    responses = {
        "fullsend-code": {
            "artifacts": [
                {
                    "id": 1,
                    "name": "fullsend-code",
                    "expired": False,
                    "created_at": "2026-07-15T00:00:00Z",
                    "workflow_run": {"id": 42},
                },
                {
                    "id": 2,
                    "name": "fullsend-code",
                    "expired": True,
                    "created_at": "2026-07-15T00:00:00Z",
                    "workflow_run": {"id": 43},
                },
            ]
        }
    }
    monkeypatch.setattr(
        client,
        "api_json",
        lambda endpoint: responses["fullsend-code"],
    )

    artifacts = client.list_artifacts(
        "redhat-developer/rhdh-agentic", None, ["fullsend-code"], run_id="42"
    )

    assert [item.id for item in artifacts] == ["1"]
