"""Structure and helper tests for the AgentsView retrieval skill."""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL_DIR = ROOT / "skills" / "agentsview"


def load_preflight_module():
    script = SKILL_DIR / "scripts" / "preflight.py"
    spec = importlib.util.spec_from_file_location("agentsview_preflight", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_skill_frontmatter_and_router_structure():
    content = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    assert match is not None
    frontmatter = match.group(1)
    assert re.search(r"^name:\s+agentsview$", frontmatter, re.MULTILINE)
    assert "description:" in frontmatter

    for section in (
        "cli_setup",
        "essential_principles",
        "intake",
        "routing",
        "reference_index",
        "output_contract",
        "success_criteria",
    ):
        assert f"<{section}>" in content
        assert f"</{section}>" in content


def test_router_references_and_metadata_are_complete():
    metadata = json.loads(
        (SKILL_DIR / "scripts" / "command-metadata.json").read_text(encoding="utf-8")
    )
    assert set(metadata) == {"status", "find", "inspect", "search", "report"}
    assert all(row["description"] for row in metadata.values())

    expected_references = {
        "status.md",
        "find-sessions.md",
        "inspect-session.md",
        "search-history.md",
        "report-window.md",
    }
    actual_references = {path.name for path in (SKILL_DIR / "references").glob("*.md")}
    assert actual_references == expected_references

    skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    for name in expected_references:
        assert f"references/{name}" in skill


def test_skill_keeps_analysis_and_destructive_operations_out_of_scope():
    content = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    assert "does not evaluate session quality" in content
    assert "Ask before an\nexplicit `agentsview sync`" in content
    assert "never use `--reveal`" in content


def test_workflows_use_preflight_binary_and_document_live_snapshots():
    skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    references = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (SKILL_DIR / "references").glob("*.md")
    )

    assert "AGENTSVIEW_BIN" in skill
    assert 'invitation to "try"' in skill
    assert "tool_call_pending" in skill
    assert "agentsview session" not in references
    assert '"$AGENTSVIEW_BIN"' in references
    assert "top-level `matches`" in references
    assert "`breakdown`" in references


def test_preflight_reports_missing_binary_as_json():
    script = SKILL_DIR / "scripts" / "preflight.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--json",
            "--binary",
            str(ROOT / "definitely-not-an-agentsview-binary"),
        ],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["available"] is False
    assert payload["working"] is False
    assert "not found" in payload["remediation"]


def test_preflight_requires_session_command_group(monkeypatch):
    preflight = load_preflight_module()
    monkeypatch.setattr(preflight, "resolve_binary", lambda _name: "/bin/agentsview")

    def probe(_binary, *args):
        if args == ("version",):
            return {
                "ok": True,
                "exit_code": 0,
                "output": "agentsview 0.37.2",
                "error": "",
            }
        return {"ok": False, "exit_code": 1, "output": "", "error": "unknown"}

    monkeypatch.setattr(preflight, "run_probe", probe)
    payload = preflight.inspect()

    assert payload["available"] is True
    assert payload["working"] is False
    assert payload["session_api"] is False
    assert "Upgrade" in payload["remediation"]


def test_preflight_honors_binary_environment_override(tmp_path, monkeypatch):
    preflight = load_preflight_module()
    binary = tmp_path / "agentsview"
    binary.write_text("#!/bin/sh\n", encoding="utf-8")
    binary.chmod(0o755)
    monkeypatch.setenv("AGENTSVIEW_BIN", str(binary))
    monkeypatch.setattr(preflight.shutil, "which", lambda _name: None)

    assert preflight.resolve_binary("") == str(binary.resolve())


def test_explicit_binary_wins_over_environment(tmp_path, monkeypatch):
    preflight = load_preflight_module()
    explicit = tmp_path / "explicit-agentsview"
    explicit.write_text("#!/bin/sh\n", encoding="utf-8")
    explicit.chmod(0o755)
    monkeypatch.setenv("AGENTSVIEW_BIN", str(tmp_path / "other"))
    monkeypatch.setattr(preflight.shutil, "which", lambda _name: None)

    assert preflight.resolve_binary(str(explicit)) == str(explicit.resolve())


def test_preflight_has_help():
    script = SKILL_DIR / "scripts" / "preflight.py"
    result = subprocess.run(
        [sys.executable, str(script), "--help"],
        capture_output=True,
        check=False,
        text=True,
    )
    assert result.returncode == 0
    assert "--binary" in result.stdout
    assert "--json" in result.stdout
