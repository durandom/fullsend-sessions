#!/usr/bin/env python3
"""Check whether the local AgentsView CLI is available and executable."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse


def resolve_binary(requested: str) -> str | None:
    """Resolve an explicit path/name, environment override, or common install."""
    candidates = [requested] if requested else []
    if not requested and os.environ.get("AGENTSVIEW_BIN"):
        candidates.append(os.environ["AGENTSVIEW_BIN"])
    if not requested:
        candidates.extend(
            [
                "agentsview",
                "~/.local/bin/agentsview",
                "~/bin/agentsview",
                "/opt/homebrew/bin/agentsview",
                "/usr/local/bin/agentsview",
            ]
        )

    for candidate in candidates:
        if not candidate:
            continue
        resolved = shutil.which(candidate)
        if resolved:
            return str(Path(resolved).resolve())
        path = Path(candidate).expanduser()
        if path.is_file() and os.access(path, os.X_OK):
            return str(path.resolve())
    return None


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


def public_url_from_args(args: list[str]) -> str | None:
    """Extract --public-url from a container command line."""
    for index, value in enumerate(args):
        if value == "--public-url" and index + 1 < len(args):
            return args[index + 1]
        if value.startswith("--public-url="):
            return value.split("=", 1)[1]
    return None


def discover_compose_server() -> tuple[str | None, str | None]:
    """Discover the live AgentsView compose service's public URL."""
    for runtime in ("podman", "docker"):
        if not shutil.which(runtime):
            continue
        try:
            service = subprocess.run(
                [runtime, "compose", "ps", "-q", "agentsview"],
                capture_output=True,
                check=False,
                text=True,
                timeout=10,
            )
            container_id = service.stdout.strip().splitlines()
            if service.returncode == 0 and container_id:
                details = subprocess.run(
                    [runtime, "inspect", container_id[-1]],
                    capture_output=True,
                    check=False,
                    text=True,
                    timeout=10,
                )
                if details.returncode == 0:
                    rows = json.loads(details.stdout)
                    row = rows[0]
                    args = row.get("Args") or row.get("Config", {}).get("Cmd") or []
                    if url := public_url_from_args(args):
                        return url, f"{runtime}_compose_running"

            rendered = subprocess.run(
                [runtime, "compose", "config", "--format", "json"],
                capture_output=True,
                check=False,
                text=True,
                timeout=10,
            )
            if rendered.returncode == 0:
                config = json.loads(rendered.stdout)
                args = (
                    config.get("services", {}).get("agentsview", {}).get("command", [])
                )
                if url := public_url_from_args(args):
                    return url, f"{runtime}_compose_config"
        except (KeyError, OSError, subprocess.SubprocessError, json.JSONDecodeError):
            continue
    return None, None


def resolve_server(requested: str) -> tuple[str | None, str | None]:
    """Resolve an explicit, environment, or compose-derived container URL."""
    if requested:
        return requested.rstrip("/"), "argument"
    if configured := os.environ.get("AGENTSVIEW_SERVER_URL"):
        return configured.rstrip("/"), "environment"
    return discover_compose_server()


def inspect_container_cli() -> dict[str, object]:
    """Inspect aggregate-command support inside the running compose service."""
    unavailable = {
        "available": False,
        "runtime": None,
        "service": "agentsview",
        "version": None,
        "command": None,
        "capabilities": {
            "projects": False,
            "stats": False,
            "activity_report": False,
            "usage_daily": False,
        },
    }
    for runtime in ("podman", "docker"):
        if not shutil.which(runtime):
            continue
        base = [runtime, "compose", "exec", "-T", "agentsview", "agentsview"]
        try:
            service = subprocess.run(
                [runtime, "compose", "ps", "-q", "agentsview"],
                capture_output=True,
                check=False,
                text=True,
                timeout=10,
            )
            if service.returncode != 0 or not service.stdout.strip():
                continue

            def help_for(*args: str) -> str:
                result = subprocess.run(
                    [*base, *args, "--help"],
                    capture_output=True,
                    check=False,
                    text=True,
                    timeout=10,
                )
                return result.stdout if result.returncode == 0 else ""

            version = subprocess.run(
                [*base, "version"],
                capture_output=True,
                check=False,
                text=True,
                timeout=10,
            )
            projects_help = help_for("projects")
            stats_help = help_for("stats")
            activity_help = help_for("activity", "report")
            daily_help = help_for("usage", "daily")
            return {
                "available": True,
                "runtime": runtime,
                "service": "agentsview",
                "version": version.stdout.strip() if version.returncode == 0 else None,
                "command": base,
                "capabilities": {
                    "projects": bool(projects_help),
                    "stats": bool(stats_help),
                    "activity_report": (
                        "--preset" in activity_help and "--no-sync" in activity_help
                    ),
                    "usage_daily": (
                        "--since" in daily_help and "--no-sync" in daily_help
                    ),
                },
            }
        except (OSError, subprocess.SubprocessError):
            continue
    return unavailable


def run_server_probe(
    binary: str, server_url: str, token_file: str = ""
) -> dict[str, object]:
    """Verify that the host CLI can read the container session API."""
    args = [
        binary,
        "session",
        "list",
        "--server",
        server_url,
        "--limit",
        "1",
        "--json",
    ]
    if token_file:
        args.extend(["--server-token-file", token_file])
    env = os.environ.copy()
    env["AGENTSVIEW_NO_DAEMON"] = "1"
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            check=False,
            text=True,
            timeout=15,
            env=env,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {"ok": False, "error": str(exc), "session_count": None}
    if result.returncode != 0:
        return {
            "ok": False,
            "error": (result.stderr or result.stdout).strip(),
            "session_count": None,
        }
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return {
            "ok": False,
            "error": f"container returned invalid JSON: {exc}",
            "session_count": None,
        }
    return {
        "ok": True,
        "error": "",
        "session_count": payload.get("total"),
    }


def inspect(
    binary_name: str = "", server_name: str = "", token_name: str = ""
) -> dict[str, object]:
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
            "server_url": None,
            "server_source": None,
            "server_working": False,
            "server_session_count": None,
            "host_daemon_disabled": True,
            "remediation": (
                f"AgentsView CLI '{name}' was not found. Run "
                "'python scripts/install_cli.py --json' after user approval, then "
                "rerun the preflight."
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
            "server_url": None,
            "server_source": None,
            "server_working": False,
            "server_session_count": None,
            "host_daemon_disabled": True,
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
            "server_url": None,
            "server_source": None,
            "server_working": False,
            "server_session_count": None,
            "host_daemon_disabled": True,
            "remediation": (
                "The AgentsView CLI does not expose the required 'session' "
                "command group. Upgrade the local AgentsView binary, then rerun "
                "the request."
            ),
        }

    if "--server" not in str(session_api["output"]):
        return {
            "available": True,
            "working": False,
            "binary": binary,
            "version": version["output"],
            "session_api": True,
            "server_url": None,
            "server_source": None,
            "server_working": False,
            "server_session_count": None,
            "host_daemon_disabled": True,
            "remediation": (
                "The AgentsView CLI session API lacks remote --server support. "
                "Upgrade it with 'python scripts/install_cli.py --force --json'."
            ),
        }

    server_url, server_source = resolve_server(server_name)
    if server_url is None:
        return {
            "available": True,
            "working": False,
            "binary": binary,
            "version": version["output"],
            "session_api": True,
            "server_url": None,
            "server_source": None,
            "server_working": False,
            "server_session_count": None,
            "host_daemon_disabled": True,
            "remediation": (
                "No container endpoint was found. Start the repository's AgentsView "
                "compose service or set AGENTSVIEW_SERVER_URL to its public URL."
            ),
        }
    parsed = urlparse(server_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return {
            "available": True,
            "working": False,
            "binary": binary,
            "version": version["output"],
            "session_api": True,
            "server_url": server_url,
            "server_source": server_source,
            "server_working": False,
            "server_session_count": None,
            "host_daemon_disabled": True,
            "remediation": "AGENTSVIEW_SERVER_URL must be an http:// or https:// URL.",
        }

    token_file = token_name or os.environ.get("AGENTSVIEW_SERVER_TOKEN_FILE", "")
    if token_file and not Path(token_file).expanduser().is_file():
        return {
            "available": True,
            "working": False,
            "binary": binary,
            "version": version["output"],
            "session_api": True,
            "server_url": server_url,
            "server_source": server_source,
            "server_working": False,
            "server_session_count": None,
            "host_daemon_disabled": True,
            "remediation": f"Server token file does not exist: {token_file}",
        }
    if token_file:
        token_file = str(Path(token_file).expanduser().resolve())

    server = run_server_probe(binary, server_url, token_file)
    if not server["ok"]:
        return {
            "available": True,
            "working": False,
            "binary": binary,
            "version": version["output"],
            "session_api": True,
            "server_url": server_url,
            "server_source": server_source,
            "server_working": False,
            "server_session_count": None,
            "host_daemon_disabled": True,
            "remediation": (
                f"The local CLI could not read the AgentsView container at "
                f"{server_url}: {server['error']}"
            ),
        }

    container_cli = inspect_container_cli()
    return {
        "available": True,
        "working": True,
        "binary": binary,
        "version": version["output"],
        "session_api": True,
        "server_url": server_url,
        "server_source": server_source,
        "server_working": True,
        "server_session_count": server["session_count"],
        "server_token_file": token_file or None,
        "host_daemon_disabled": True,
        "container_cli": container_cli,
        "remediation": None,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Check that the local AgentsView CLI can read the container API. "
            "This command disables host daemon startup and does not sync, install, "
            "or modify AgentsView."
        )
    )
    parser.add_argument(
        "--server",
        default="",
        help=(
            "Container public URL (default: AGENTSVIEW_SERVER_URL or discover the "
            "running compose service)"
        ),
    )
    parser.add_argument(
        "--server-token-file",
        default="",
        help="Bearer token file for an authenticated container endpoint",
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

    result = inspect(args.binary, args.server, args.server_token_file)
    if args.json:
        json.dump(result, sys.stdout, separators=(",", ":"))
        sys.stdout.write("\n")
    else:
        if result["working"]:
            print(f"AgentsView: {result['version']}")
            print(f"Binary: {result['binary']}")
            print(f"Container: {result['server_url']}")
            print(f"Container CLI: {result['container_cli']['version']}")
            print("Host daemon: disabled")
        else:
            print(f"AgentsView unavailable: {result['remediation']}")

    return 0 if result["working"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
