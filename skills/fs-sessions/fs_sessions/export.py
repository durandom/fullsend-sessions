"""Build metadata and copy session transcripts to the shared repo."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from fs_sessions.config import get_project_name, get_username


@dataclass
class ExportResult:
    dest: Path
    verb: str


def build_metadata_line(
    project: str,
    username: str,
    timestamp: str | None = None,
) -> str:
    """Build the JSON metadata line prepended to exported transcripts."""
    ts = timestamp or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cwd = f"/sessions/{username}_{project}"
    meta = {
        "type": "user",
        "timestamp": ts,
        "message": {"content": f"[Session: {project}] by {username}\nProject: {cwd}"},
        "cwd": cwd,
    }
    return json.dumps(meta, separators=(",", ":"))


def dest_path(
    sessions_repo: Path,
    username: str,
    project: str,
    session_id: str,
) -> Path:
    """Compute the destination path for an exported transcript."""
    return sessions_repo / "sessions" / f"{username}_{project}" / f"{session_id}.jsonl"


def export_transcript(
    transcript: Path,
    dest: Path,
    metadata_line: str,
) -> None:
    """Copy transcript to dest with metadata line prepended."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w") as out:
        out.write(metadata_line + "\n")
        with transcript.open() as src:
            shutil.copyfileobj(src, out)


def _content_size(exported: Path) -> int:
    """Size of the exported file excluding the first (metadata) line."""
    with exported.open("rb") as f:
        first_line = f.readline()
        return exported.stat().st_size - len(first_line)


def prepare_export(
    transcript_path: str,
    session_id: str,
    cwd: str | None,
    sessions_repo: Path,
    username: str | None = None,
    timestamp: str | None = None,
    project: str | None = None,
) -> ExportResult | None:
    """Full export pipeline: validate, build metadata, copy.

    Returns ExportResult with verb ("add" or "update"), or None if skipped.
    """
    src = Path(transcript_path)
    if not src.is_file() or src.stat().st_size == 0:
        return None

    user = username or get_username()
    project_name = project if project is not None else get_project_name(cwd)
    dst = dest_path(sessions_repo, user, project_name, session_id)

    verb = "add"
    if dst.exists():
        if src.stat().st_size == _content_size(dst):
            return None
        verb = "update"

    meta = build_metadata_line(project_name, user, timestamp)
    export_transcript(src, dst, meta)
    return ExportResult(dest=dst, verb=verb)
