"""End-to-end tests for the installed-style CLI entry point."""

from __future__ import annotations

import json
import subprocess

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
    committed = subprocess.run(
        ["git", "show", "--pretty=", "--name-only", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    assert committed == [exported.relative_to(repo).as_posix()]
    assert (
        subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", "unrelated"], cwd=repo
        ).returncode
        == 1
    )
