"""Tests for fs_sessions.export."""

from __future__ import annotations

import json

from fs_sessions.export import (
    ExportResult,
    build_metadata_line,
    dest_path,
    export_transcript,
    prepare_export,
)


class TestBuildMetadataLine:
    def test_valid_json(self):
        line = build_metadata_line("myproj", "marcel-hild", "2025-01-01T00:00:00Z")
        obj = json.loads(line)
        assert obj["type"] == "user"
        assert obj["timestamp"] == "2025-01-01T00:00:00Z"
        assert "myproj" in obj["message"]["content"]
        assert "marcel-hild" in obj["message"]["content"]
        assert obj["cwd"] == "/sessions/marcel-hild_myproj"

    def test_auto_timestamp(self):
        line = build_metadata_line("proj", "user")
        obj = json.loads(line)
        assert obj["timestamp"].endswith("Z")


class TestDestPath:
    def test_path_construction(self, tmp_path):
        p = dest_path(tmp_path, "marcel-hild", "myproj", "abc-123")
        assert p == tmp_path / "sessions" / "marcel-hild_myproj" / "abc-123.jsonl"


class TestExportTranscript:
    def test_prepends_metadata(self, tmp_path):
        src = tmp_path / "src.jsonl"
        src.write_text('{"type":"user"}\n{"type":"assistant"}\n')
        dst = tmp_path / "out" / "dest.jsonl"
        meta = '{"type":"meta"}'

        export_transcript(src, dst, meta)

        lines = dst.read_text().splitlines()
        assert len(lines) == 3
        assert lines[0] == meta
        assert lines[1] == '{"type":"user"}'
        assert lines[2] == '{"type":"assistant"}'

    def test_creates_parent_dirs(self, tmp_path):
        src = tmp_path / "src.jsonl"
        src.write_text("line\n")
        dst = tmp_path / "a" / "b" / "c" / "dest.jsonl"
        export_transcript(src, dst, "meta")
        assert dst.exists()


class TestPrepareExport:
    def test_full_export(self, tmp_path):
        src = tmp_path / "transcript.jsonl"
        src.write_text('{"type":"user"}\n')
        repo = tmp_path / "repo"
        repo.mkdir()

        result = prepare_export(
            str(src),
            "session-1",
            "/Users/me/myproject",
            repo,
            username="test-user",
            timestamp="2025-01-01T00:00:00Z",
        )

        assert result is not None
        assert isinstance(result, ExportResult)
        assert result.verb == "add"
        assert result.dest.name == "session-1.jsonl"
        content = result.dest.read_text()
        assert content.startswith("{")
        assert '"type":"user"' in content.split("\n")[0]

    def test_skips_missing_file(self, tmp_path):
        result = prepare_export(
            str(tmp_path / "nope"), "s1", "/tmp", tmp_path, username="u"
        )
        assert result is None

    def test_skips_empty_file(self, tmp_path):
        src = tmp_path / "empty.jsonl"
        src.write_text("")
        result = prepare_export(str(src), "s1", "/tmp", tmp_path, username="u")
        assert result is None

    def test_skips_unchanged(self, tmp_path):
        src = tmp_path / "transcript.jsonl"
        src.write_text("data\n")
        repo = tmp_path / "repo"
        (repo / "sessions" / "u_proj").mkdir(parents=True)
        meta = '{"type":"meta"}\n'
        (repo / "sessions" / "u_proj" / "s1.jsonl").write_text(meta + "data\n")

        result = prepare_export(str(src), "s1", "/Users/me/proj", repo, username="u")
        assert result is None

    def test_updates_when_source_grew(self, tmp_path):
        src = tmp_path / "transcript.jsonl"
        src.write_text("line1\nline2\nline3\n")
        repo = tmp_path / "repo"
        (repo / "sessions" / "u_proj").mkdir(parents=True)
        meta = '{"type":"meta"}\n'
        (repo / "sessions" / "u_proj" / "s1.jsonl").write_text(meta + "line1\n")

        result = prepare_export(str(src), "s1", "/Users/me/proj", repo, username="u")
        assert result is not None
        assert result.verb == "update"
