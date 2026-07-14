#!/usr/bin/env python3
"""Check whether the local AgentsView CLI is available and executable."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


def resolve_binary(requested: str) -> str | None:
    """Resolve an explicit path/name or the default agentsview executable."""
    candidate = requested or "agentsview"
    if Path(candidate).parent != Path("."):
        path = Path(candidate).expanduser()
        return str(path.resolve()) if path.is_file() else None
    return shutil.which(candidate)


def run_probe(binary: str, *args: str) -> dict[str, object]:
    """Run one bounded, non-interactive CLI probe."""
    try:
        result = subprocess.run(
            [binary, *args],
            capture_output=True,
            check=False,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {"ok": False, "exit_code": None, "output": "", "error": str(exc)}

    output = (result.stdout or result.stderr).strip()
    return {
        "ok": result.returncode == 0,
        "exit_code": result.returncode,
        "output": output,
        "error": "" if result.returncode == 0 else output,
    }


def inspect(binary_name: str = "") -> dict[str, object]:
    """Return structured local CLI capability information."""
    binary = resolve_binary(binary_name)
    if binary is None:
        name = binary_name or "agentsview"
        return {
            "available": False,
            "working": False,
            "binary": None,
            "version": None,
            "session_api": False,
            "daemon_status": None,
            "remediation": (
                f"AgentsView CLI '{name}' was not found. Make the local agentsview "
                "binary available on PATH, then rerun the request."
            ),
        }

    version = run_probe(binary, "version")
    if not version["ok"]:
        return {
            "available": True,
            "working": False,
            "binary": binary,
            "version": None,
            "session_api": False,
            "daemon_status": None,
            "remediation": (
                "The AgentsView binary exists but 'agentsview version' failed: "
                f"{version['error']}"
            ),
        }

    session_api = run_probe(binary, "session", "--help")
    if not session_api["ok"]:
        return {
            "available": True,
            "working": False,
            "binary": binary,
            "version": version["output"],
            "session_api": False,
            "daemon_status": None,
            "remediation": (
                "The AgentsView CLI does not expose the required 'session' "
                "command group. Upgrade the local AgentsView binary, then rerun "
                "the request."
            ),
        }

    return {
        "available": True,
        "working": True,
        "binary": binary,
        "version": version["output"],
        "session_api": True,
        "daemon_status": None,
        "remediation": None,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Check that the local AgentsView CLI can answer read requests. "
            "This command does not start, sync, install, or modify AgentsView."
        )
    )
    parser.add_argument(
        "--binary",
        default="",
        help="AgentsView executable name or path (default: resolve agentsview on PATH)",
    )
    parser.add_argument(
        "--json", action="store_true", help="Emit compact JSON for agent consumption"
    )
    args = parser.parse_args(argv)

    result = inspect(args.binary)
    if args.json:
        json.dump(result, sys.stdout, separators=(",", ":"))
        sys.stdout.write("\n")
    else:
        if result["working"]:
            print(f"AgentsView: {result['version']}")
            print(f"Binary: {result['binary']}")
            print("Daemon: not checked")
        else:
            print(f"AgentsView unavailable: {result['remediation']}")

    return 0 if result["working"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
