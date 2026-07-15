"""Build metadata and copy session transcripts to the shared repository."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO, Optional


@dataclass
class ExportResult:
    dest: Path
    verb: str
    project: str
    username: str
    paths: list[Path]


def build_metadata_line(
    project: str, username: str, timestamp: Optional[str] = None
) -> str:
    ts = timestamp or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cwd = f"/sessions/{project}"
    meta = {
        "type": "user",
        "timestamp": ts,
        "message": {"content": f"[Session: {project}] by {username}\nProject: {cwd}"},
        "cwd": cwd,
    }
    return json.dumps(meta, separators=(",", ":"))


def destination(repo: Path, username: str, project: str, session_id: str) -> Path:
    return repo / "sessions" / f"{username}_{project}" / f"{session_id}.jsonl"


def _streams_equal(left: BinaryIO, right: BinaryIO) -> bool:
    while True:
        left_chunk = left.read(1024 * 1024)
        right_chunk = right.read(1024 * 1024)
        if left_chunk != right_chunk:
            return False
        if not left_chunk:
            return True


def _transcript_matches(source: Path, exported: Path) -> bool:
    if not exported.is_file():
        return False
    with source.open("rb") as source_stream, exported.open("rb") as output_stream:
        output_stream.readline()
        return _streams_equal(source_stream, output_stream)


def _files_equal(source: Path, dest: Path) -> bool:
    if not dest.is_file() or source.stat().st_size != dest.stat().st_size:
        return False
    with source.open("rb") as source_stream, dest.open("rb") as dest_stream:
        return _streams_equal(source_stream, dest_stream)


def _copy_companion_files(source_dir: Path, dest_dir: Path) -> list[Path]:
    """Copy every regular companion file while preserving Claude's layout."""
    changed = []
    if not source_dir.is_dir():
        return changed
    for source in sorted(source_dir.rglob("*")):
        if source.is_symlink() or not source.is_file():
            continue
        dest = dest_dir / source.relative_to(source_dir)
        if _files_equal(source, dest):
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)
        changed.append(dest)
    return changed


def prepare_export(
    transcript: Path,
    session_id: str,
    project: str,
    sessions_repo: Path,
    username: str,
    timestamp: Optional[str] = None,
) -> Optional[ExportResult]:
    if not transcript.is_file() or transcript.stat().st_size == 0:
        return None
    dest = destination(sessions_repo, username, project, session_id)
    existed = dest.exists()
    changed = []
    if not _transcript_matches(transcript, dest):
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("w", encoding="utf-8") as output:
            output.write(build_metadata_line(project, username, timestamp) + "\n")
            with transcript.open(encoding="utf-8") as source:
                shutil.copyfileobj(source, output)
        changed.append(dest)

    source_companions = transcript.parent / session_id
    dest_companions = dest.parent / session_id
    changed.extend(_copy_companion_files(source_companions, dest_companions))
    if not changed:
        return None
    return ExportResult(
        dest=dest,
        verb="update" if existed else "add",
        project=project,
        username=username,
        paths=changed,
    )
