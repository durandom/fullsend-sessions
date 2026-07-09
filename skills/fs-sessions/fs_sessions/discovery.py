"""Discover local Claude Code session transcripts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from fs_sessions.config import CLAUDE_PROJECTS_DIR


@dataclass
class SessionInfo:
    path: Path
    mtime: float
    title: str
    cwd: str | None
    size: int = 0
    line_count: int = 0


def _extract_title(path: Path) -> str:
    """Extract the AI-generated session title from a JSONL transcript."""
    title = ""
    try:
        for line in path.open():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("type") == "ai-title":
                title = obj.get("aiTitle", "")
    except OSError:
        pass
    return title or "(untitled)"


def _extract_cwd(path: Path) -> str | None:
    """Extract the working directory from the first user message with a sessionId."""
    try:
        for line in path.open():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if (
                obj.get("type") == "user"
                and obj.get("sessionId") is not None
                and obj.get("cwd") is not None
            ):
                return obj["cwd"]
    except OSError:
        pass
    return None


def human_size(nbytes: int) -> str:
    """Format byte count as human-readable string."""
    if nbytes >= 1_048_576:
        return f"{nbytes // 1_048_576}M"
    if nbytes >= 1024:
        return f"{nbytes // 1024}K"
    return f"{nbytes}B"


def discover_sessions(
    projects_dir: Path | None = None,
    max_results: int = 20,
) -> list[SessionInfo]:
    """Find local .jsonl sessions, sorted by mtime descending."""
    base = projects_dir or CLAUDE_PROJECTS_DIR
    if not base.is_dir():
        return []

    sessions: list[SessionInfo] = []
    for jsonl in base.glob("*/*.jsonl"):
        try:
            stat = jsonl.stat()
            mtime = stat.st_mtime
            size = stat.st_size
        except OSError:
            continue
        try:
            line_count = sum(1 for _ in jsonl.open())
        except OSError:
            line_count = 0
        sessions.append(
            SessionInfo(
                path=jsonl,
                mtime=mtime,
                title=_extract_title(jsonl),
                cwd=_extract_cwd(jsonl),
                size=size,
                line_count=line_count,
            )
        )

    sessions.sort(key=lambda s: s.mtime, reverse=True)
    return sessions[:max_results]


def display_project(session: SessionInfo) -> str:
    """Derive a display name for the project from session metadata."""
    if session.cwd:
        p = Path(session.cwd)
        return f"{p.parent.name}/{p.name}"
    return session.path.parent.name
