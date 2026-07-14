"""CLI entry points: main() for interactive use, hook_main() for SessionEnd hook."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from fs_sessions.config import get_sessions_repo, get_username
from fs_sessions.discovery import (
    SessionInfo,
    discover_sessions,
    display_project,
    human_size,
)
from fs_sessions.export import prepare_export
from fs_sessions.git import add, commit, pull_rebase, push


def _format_time(mtime: float) -> str:
    return datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")


def _display_sessions(sessions: list[SessionInfo]) -> None:
    hdr = "  {:<4} {:<40} {:<18} {:>7} {:>6} {}"
    print()
    print(hdr.format("#", "PROJECT", "MODIFIED", "SIZE", "MSGS", "TITLE"))
    print(
        hdr.format(
            "---",
            "----------------------------------------",
            "------------------",
            "-------",
            "------",
            "-----",
        )
    )
    for i, s in enumerate(sessions, 1):
        project = display_project(s)
        title = s.title
        if len(title) > 50:
            title = title[:47] + "..."
        ftime = _format_time(s.mtime)
        size = human_size(s.size)
        print(hdr.format(f"[{i}]", project, ftime, size, s.line_count, title))
    print()


def _share_session(
    jsonl: Path,
    session: SessionInfo,
    sessions_repo: Path,
    username: str,
) -> bool:
    session_id = jsonl.stem
    cwd = session.cwd
    project = Path(cwd).name if cwd else jsonl.parent.name.lstrip("-")

    result = prepare_export(
        str(jsonl),
        session_id,
        cwd,
        sessions_repo,
        username=username,
        project=project,
    )
    if result is None:
        print(f"Unchanged: {username}_{project}/{session_id}.jsonl")
        return True

    rel = result.dest.relative_to(sessions_repo).as_posix()
    print(f"Copied → {rel}")

    if not add(sessions_repo, rel):
        print(f"error: failed to stage {rel}", file=sys.stderr)
        return False
    if not commit(
        sessions_repo,
        f"feat: {result.verb} session {username}/{project}/{session_id}",
    ):
        print("error: failed to commit session", file=sys.stderr)
        return False
    print("Committed.")

    try:
        answer = input("Push to remote? [Y/n] ")
    except EOFError:
        answer = "y"
    if not answer or answer.lower().startswith("y"):
        if not pull_rebase(sessions_repo):
            print("error: failed to pull with rebase", file=sys.stderr)
            return False
        if not push(sessions_repo):
            print("error: failed to push session", file=sys.stderr)
            return False
        print("Pushed.")
    else:
        print("Skipped push. Run 'git push' in the sessions repo later.")
    return True


def main(argv: list[str] | None = None) -> None:
    """Interactive CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="fs-sessions",
        description="Share and browse Claude Code session transcripts",
    )
    parser.add_argument("--list", action="store_true", help="list recent sessions")
    parser.add_argument(
        "--last", action="store_true", help="share the most recent session"
    )
    args = parser.parse_args(argv)

    sessions = discover_sessions()
    if not sessions:
        print("error: no Claude Code sessions found", file=sys.stderr)
        sys.exit(1)

    if args.list:
        _display_sessions(sessions)
        return

    sessions_repo = get_sessions_repo()
    if sessions_repo is None:
        print("error: FULLSEND_SESSIONS_REPO not configured", file=sys.stderr)
        sys.exit(1)

    username = get_username()

    if args.last:
        if not _share_session(sessions[0].path, sessions[0], sessions_repo, username):
            sys.exit(1)
        return

    _display_sessions(sessions)
    try:
        choice_str = input("  Share which session? [1] ")
    except EOFError:
        choice_str = ""
    if not choice_str:
        choice_str = "1"

    try:
        choice = int(choice_str)
    except ValueError:
        print(f"error: invalid choice: {choice_str}", file=sys.stderr)
        sys.exit(1)

    if choice < 1 or choice > len(sessions):
        print(f"error: invalid choice: {choice}", file=sys.stderr)
        sys.exit(1)

    selected = sessions[choice - 1]
    if not _share_session(selected.path, selected, sessions_repo, username):
        sys.exit(1)


def hook_main() -> None:
    """SessionEnd hook entry point — reads JSON from stdin, never fails."""
    try:
        sessions_repo = get_sessions_repo()
        if sessions_repo is None:
            return

        raw = sys.stdin.read()
        data = json.loads(raw)

        transcript_path = data.get("transcript_path", "")
        session_id = data.get("session_id", "")
        cwd = data.get("cwd")

        if not transcript_path or not session_id:
            return

        result = prepare_export(transcript_path, session_id, cwd, sessions_repo)
        if result is None:
            return

        username = get_username()
        project = Path(cwd).name if cwd else "unknown"
        rel = f"sessions/{username}_{project}/{session_id}.jsonl"

        add(sessions_repo, rel)
        commit(
            sessions_repo,
            f"feat: {result.verb} session {username}/{project}/{session_id}",
        )
        pull_rebase(sessions_repo)
        push(sessions_repo)
    except Exception:
        pass
