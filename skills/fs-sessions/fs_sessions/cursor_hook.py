"""Cursor sessionEnd hook installation and lifecycle management."""

from __future__ import annotations

import json
import shlex
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

DEFAULT_HOOKS = Path.home() / ".cursor" / "hooks.json"
HOOK_TIMEOUT_SECONDS = 30


class CursorHookError(ValueError):
    """Raised when Cursor hooks.json cannot be safely updated."""


def _load_hooks(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"version": 1, "hooks": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CursorHookError(f"invalid Cursor hooks {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise CursorHookError(f"Cursor hooks must contain a JSON object: {path}")
    return data


def _save_hooks(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix="hooks-", suffix=".json", dir=path.parent
    )
    try:
        with open(fd, "w", encoding="utf-8", closefd=True) as stream:
            json.dump(data, stream, indent=2)
            stream.write("\n")
        Path(temp_name).replace(path)
    except Exception:
        Path(temp_name).unlink(missing_ok=True)
        raise


def is_managed_command(command: Any) -> bool:
    if not isinstance(command, str):
        return False
    return "export-session" in command or (
        "fs-sessions" in command and "cursor-hook run" in command
    )


def _remove_managed(entries: Any) -> Tuple[List[Dict[str, Any]], int]:
    if entries is None:
        return [], 0
    if not isinstance(entries, list):
        raise CursorHookError("hooks.sessionEnd must be an array")
    kept: List[Dict[str, Any]] = []
    removed = 0
    for entry in entries:
        if not isinstance(entry, dict):
            kept.append(entry)
            continue
        command = entry.get("command")
        if is_managed_command(command):
            removed += 1
        else:
            kept.append(entry)
    return kept, removed


def hook_command(script_path: Path) -> str:
    return f"python3 {shlex.quote(str(script_path.resolve()))} cursor-hook run"


def install_hook(
    script_path: Path, hooks_path: Path = DEFAULT_HOOKS
) -> Dict[str, Any]:
    data = _load_hooks(hooks_path)
    hooks = data.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise CursorHookError("Cursor hooks key 'hooks' must be an object")
    entries, removed = _remove_managed(hooks.get("sessionEnd"))
    entries.append(
        {
            "command": hook_command(script_path),
            "timeout": HOOK_TIMEOUT_SECONDS,
        }
    )
    hooks["sessionEnd"] = entries
    _save_hooks(hooks_path, data)
    return {
        "installed": True,
        "hooks": str(hooks_path),
        "command": hook_command(script_path),
        "replaced": removed,
    }


def uninstall_hook(hooks_path: Path = DEFAULT_HOOKS) -> Dict[str, Any]:
    data = _load_hooks(hooks_path)
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        return {"installed": False, "hooks": str(hooks_path), "removed": 0}
    entries, removed = _remove_managed(hooks.get("sessionEnd"))
    if entries:
        hooks["sessionEnd"] = entries
    else:
        hooks.pop("sessionEnd", None)
    if not hooks:
        data.pop("hooks", None)
    _save_hooks(hooks_path, data)
    return {"installed": False, "hooks": str(hooks_path), "removed": removed}


def _describe_entry(entry: Any) -> Dict[str, Any]:
    command = entry.get("command") if isinstance(entry, dict) else None
    return {
        "command": command,
        "managed": is_managed_command(command),
        "timeout": entry.get("timeout") if isinstance(entry, dict) else None,
        "matcher": entry.get("matcher") if isinstance(entry, dict) else None,
    }


def hook_status(hooks_path: Path = DEFAULT_HOOKS) -> Dict[str, Any]:
    exists = hooks_path.exists()
    data = _load_hooks(hooks_path) if exists else {"version": 1, "hooks": {}}
    hooks = data.get("hooks")
    entries = hooks.get("sessionEnd", []) if isinstance(hooks, dict) else []
    described: List[Dict[str, Any]] = []
    if isinstance(entries, list):
        for entry in entries:
            if isinstance(entry, dict):
                described.append(_describe_entry(entry))
    commands = [item["command"] for item in described if item["managed"]]
    return {
        "installed": bool(commands),
        "exists": exists,
        "hooks": str(hooks_path),
        "commands": commands,
        "managed_count": sum(1 for item in described if item["managed"]),
        "other_count": sum(
            1 for item in described if not item["managed"] and item["command"]
        ),
        "entries": described,
    }
