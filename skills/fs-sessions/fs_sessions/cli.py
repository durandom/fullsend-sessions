"""Command-line interface for session sharing, policy, and hook management."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Dict, List, Optional

from fs_sessions.config import (
    ConfigError,
    get_backends,
    get_machine,
    get_s3_config,
    get_sessions_config,
    get_sessions_repo,
    get_user_config_path,
    initialize_s3_sessions_config,
    initialize_sessions_config,
    load_user_config,
    save_user_config,
)
from fs_sessions.discovery import SessionInfo, discover_sessions
from fs_sessions.export import prepare_export
from fs_sessions.git import commit_files, pull_rebase, push
from fs_sessions.hook import (
    DEFAULT_SETTINGS,
    HookError,
    hook_status,
    install_hook,
    uninstall_hook,
)
from fs_sessions.policy import add_rule, evaluate_policy, remove_rule, validate_policy
from fs_sessions.s3 import S3Error


def _emit(data: Dict[str, Any], human: Optional[str], force_json: bool) -> None:
    if force_json or not sys.stdout.isatty():
        json.dump(data, sys.stdout, indent=2 if force_json else None)
        sys.stdout.write("\n")
    elif human:
        print(human)


def _username() -> str:
    try:
        result = subprocess.run(
            ["git", "config", "user.name"], capture_output=True, text=True, check=True
        )
        if result.stdout.strip():
            return result.stdout.strip().replace(" ", "-").lower()
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    return os.environ.get("USER", "unknown")


def _script_path() -> Path:
    return Path(__file__).resolve().parent.parent / "scripts" / "fs-sessions"


@contextmanager
def _export_dir(repo: Optional[Path]):
    """Yield the Git repo or a self-cleaning staging directory for S3."""
    if repo is not None:
        yield repo
        return
    with TemporaryDirectory(prefix="fs-sessions-") as temp_dir:
        destination = Path(temp_dir)
        (destination / "sessions").mkdir()
        yield destination


def _settings(args: argparse.Namespace) -> Path:
    return (
        Path(args.settings).expanduser()
        if getattr(args, "settings", None)
        else DEFAULT_SETTINGS
    )


def cmd_config_init(args: argparse.Namespace) -> int:
    if args.backend == "git":
        if not args.repo:
            raise ConfigError("--repo is required for the legacy Git backend")
        data = initialize_sessions_config(Path(args.repo), args.default)
    else:
        if args.repo:
            raise ConfigError("--repo is valid only with --backend git")
        bucket = args.bucket or os.environ.get("S3_BUCKET", "")
        region = (
            args.region
            or os.environ.get("S3_REGION")
            or os.environ.get("AWS_REGION")
            or os.environ.get("AWS_DEFAULT_REGION", "")
        )
        machine = args.machine or os.environ.get("FS_SESSIONS_MACHINE") or _username()
        data = initialize_s3_sessions_config(
            bucket=bucket,
            region=region,
            machine=machine,
            default=args.default,
            profile=args.profile or os.environ.get("AWS_PROFILE"),
            endpoint_url=args.endpoint_url or os.environ.get("AWS_S3_ENDPOINT"),
            prefix=args.prefix,
        )
    _emit(
        {
            "success": True,
            "config": str(get_user_config_path()),
            "backends": get_backends(data),
            "sessions": data["sessions"],
        },
        f"Initialized session config: {get_user_config_path()}",
        args.json,
    )
    return 0


def cmd_config_show(args: argparse.Namespace) -> int:
    data = load_user_config(missing_ok=False)
    backends = get_backends(data)
    payload = {
        "config": str(get_user_config_path()),
        "backends": backends,
        "sessions": get_sessions_config(data),
    }
    if "git" in backends:
        payload["repo"] = str(get_sessions_repo(data))
    _emit(payload, json.dumps(payload, indent=2), args.json)
    return 0


def cmd_s3_check(args: argparse.Namespace) -> int:
    from fs_sessions.s3 import check_access

    config = load_user_config(missing_ok=False)
    s3_config = get_s3_config(config)
    if not s3_config:
        raise ConfigError("S3 is not configured; run 'config init' first")
    payload = check_access(s3_config)
    _emit(payload, f"S3 access ready: s3://{payload['bucket']}/", args.json)
    return 0


def cmd_s3_roots(args: argparse.Namespace) -> int:
    from fs_sessions.s3 import discover_claude_roots

    config = load_user_config(missing_ok=False)
    s3_config = get_s3_config(config)
    if not s3_config:
        raise ConfigError("S3 is not configured; run 'config init' first")
    roots = discover_claude_roots(s3_config)
    payload = {"count": len(roots), "roots": roots}
    _emit(payload, "\n".join(roots) if roots else "No Claude S3 roots found", args.json)
    return 0 if roots else 1


def cmd_policy_check(args: argparse.Namespace) -> int:
    decision = evaluate_policy(load_user_config(missing_ok=False), Path(args.path))
    data = decision.to_dict()
    detail = f"Policy: {decision.action} ({decision.reason})"
    if decision.matched_rule is not None:
        detail += f", rule {decision.matched_rule}"
    _emit(data, detail, args.json)
    return 0 if decision.allowed else 1


def cmd_policy_default(args: argparse.Namespace) -> int:
    data = load_user_config(missing_ok=False)
    sessions = get_sessions_config(data)
    policy = validate_policy(sessions.setdefault("policy", {}))
    policy["default"] = args.action
    sessions["policy"] = policy
    save_user_config(data)
    _emit(
        {"success": True, "default": args.action},
        f"Default policy: {args.action}",
        args.json,
    )
    return 0


def cmd_policy_add(args: argparse.Namespace) -> int:
    selector = "origin" if args.origin is not None else "path"
    pattern = args.origin if args.origin is not None else args.path
    data = load_user_config(missing_ok=False)
    index = add_rule(data, args.action, selector, pattern)
    save_user_config(data)
    payload = {
        "success": True,
        "index": index,
        "rule": {"action": args.action, selector: pattern},
    }
    _emit(payload, f"Added rule {index}: {args.action} {selector} {pattern}", args.json)
    return 0


def cmd_policy_rules(args: argparse.Namespace) -> int:
    data = load_user_config(missing_ok=False)
    policy = validate_policy(get_sessions_config(data).get("policy", {}))
    payload = {"default": policy["default"], "rules": policy["rules"]}
    lines = [f"Default: {policy['default']}"]
    for index, rule in enumerate(policy["rules"], 1):
        selector = "origin" if "origin" in rule else "path"
        lines.append(f"{index}. {rule['action']} {selector} {rule[selector]}")
    _emit(payload, "\n".join(lines), args.json)
    return 0


def cmd_policy_remove(args: argparse.Namespace) -> int:
    data = load_user_config(missing_ok=False)
    removed = remove_rule(data, args.index)
    save_user_config(data)
    _emit(
        {"success": True, "removed": removed}, f"Removed rule {args.index}", args.json
    )
    return 0


def cmd_hook_install(args: argparse.Namespace) -> int:
    result = install_hook(_script_path(), _settings(args))
    _emit(
        result, f"Installed global SessionEnd hook in {result['settings']}", args.json
    )
    return 0


def cmd_hook_status(args: argparse.Namespace) -> int:
    result = hook_status(_settings(args))
    state = "installed" if result["installed"] else "not installed"
    message = f"Hook: {state} ({result['settings']})"
    _emit(result, message, args.json)
    return 0 if result["installed"] else 1


def cmd_hook_uninstall(args: argparse.Namespace) -> int:
    result = uninstall_hook(_settings(args))
    _emit(result, f"Removed {result['removed']} session hook(s)", args.json)
    return 0


def _emit_hook_notice(message: str) -> None:
    """Emit the structured user message accepted by SessionEnd hooks."""
    json.dump({"systemMessage": message}, sys.stdout)
    sys.stdout.write("\n")


def _run_hook() -> int:
    """Run fail-closed and silent so SessionEnd itself can never fail."""
    try:
        event = json.load(sys.stdin)
        cwd = event.get("cwd")
        transcript_value = event.get("transcript_path")
        session_id = event.get("session_id")
        if not cwd or not transcript_value or not session_id:
            return 0

        config = load_user_config(missing_ok=False)
        decision = evaluate_policy(config, Path(cwd))
        if not decision.allowed:
            return 0

        backends = get_backends(config)
        username = get_machine(config) or _username()
        transcript = Path(transcript_value)
        project = Path(decision.context.git_root or cwd).name

        use_git = "git" in backends
        repo = get_sessions_repo(config) if use_git else None
        with _export_dir(repo) as dest_dir:
            result = prepare_export(transcript, session_id, project, dest_dir, username)
            if result is None:
                return 0

            uploaded_to = []
            if use_git and repo:
                relative_paths = [p.relative_to(repo).as_posix() for p in result.paths]
                message = (
                    f"feat: {result.verb} session "
                    f"{result.username}/{result.project}/{session_id}"
                )
                if commit_files(repo, relative_paths, message):
                    if pull_rebase(repo) and push(repo):
                        uploaded_to.append("Git")

            if "s3" in backends:
                from fs_sessions.s3 import upload_session

                s3_config = get_s3_config(config)
                if s3_config and upload_session(
                    s3_config, result.paths, dest_dir, username, project
                ):
                    uploaded_to.append("S3")

            if uploaded_to:
                noun = "file" if len(result.paths) == 1 else "files"
                destinations = " and ".join(uploaded_to)
                _emit_hook_notice(
                    f"fs-sessions: exported and uploaded {len(result.paths)} session "
                    f"{noun} to {destinations} for {project}/{session_id}."
                )
    except Exception:
        return 0
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    config = load_user_config(missing_ok=False)
    backends = get_backends(config)
    status = hook_status(_settings(args))
    sessions = get_sessions_config(config)

    lines = []
    payload: Dict[str, Any] = {
        "config": str(get_user_config_path()),
        "backends": backends,
        "machine": get_machine(config),
        "enabled": sessions.get("enabled", True),
        "policy": validate_policy(sessions.get("policy", {})),
        "hook": status,
    }

    if "git" in backends:
        try:
            repo = get_sessions_repo(config)
            count = sum(1 for _ in (repo / "sessions").glob("*/*.jsonl"))
            payload["repo"] = str(repo)
            payload["session_count"] = count
            lines.append(f"Git: {repo} ({count} sessions)")
        except ConfigError:
            lines.append("Git: not configured")

    if "s3" in backends:
        s3_config = get_s3_config(config)
        if s3_config:
            payload["s3"] = s3_config
            lines.append(f"S3: s3://{s3_config['bucket']}/")
        else:
            lines.append("S3: not configured")

    hook_state = "installed" if status["installed"] else "not installed"
    lines.append(f"Backends: {', '.join(backends)}")
    lines.append(f"Hook: {hook_state}")
    _emit(payload, "\n".join(lines), args.json)
    return 0


def _session_payload(session: SessionInfo) -> Dict[str, Any]:
    return {
        "path": str(session.path),
        "cwd": session.cwd,
        "title": session.title,
        "size": session.size,
        "messages": session.line_count,
        "mtime": session.mtime,
    }


def cmd_list(args: argparse.Namespace) -> int:
    sessions = discover_sessions(max_results=args.limit)
    payload = {
        "count": len(sessions),
        "sessions": [_session_payload(item) for item in sessions],
    }
    lines = [
        f"{index}. {item.title} — {item.cwd or item.path.parent.name}"
        for index, item in enumerate(sessions, 1)
    ]
    _emit(payload, "\n".join(lines) if lines else "No sessions found", args.json)
    return 0 if sessions else 1


def cmd_share(args: argparse.Namespace) -> int:
    if args.last:
        sessions = discover_sessions(max_results=1)
        if not sessions:
            raise ConfigError("no Claude Code sessions found")
        session = sessions[0]
        transcript = session.path
        cwd = session.cwd
    else:
        transcript = Path(args.transcript).expanduser().resolve()
        cwd = args.cwd
    project = Path(cwd).name if cwd else transcript.parent.name.lstrip("-")
    config = load_user_config(missing_ok=False)
    backends = get_backends(config)
    username = get_machine(config) or _username()

    use_git = "git" in backends
    repo = get_sessions_repo(config) if use_git else None
    with _export_dir(repo) as dest_dir:
        result = prepare_export(
            transcript, transcript.stem, project, dest_dir, username
        )
        if result is None:
            _emit({"changed": False}, "Session unchanged", args.json)
            return 0

        committed = False
        if use_git and repo:
            relative_paths = [p.relative_to(repo).as_posix() for p in result.paths]
            msg = (
                f"feat: {result.verb} session "
                f"{result.username}/{project}/{transcript.stem}"
            )
            committed = commit_files(repo, relative_paths, msg)

        uploaded = False
        if "s3" in backends:
            from fs_sessions.s3 import upload_session

            s3_config = get_s3_config(config)
            if s3_config:
                uploaded = upload_session(
                    s3_config, result.paths, dest_dir, username, project
                )

        results = {"git": committed, "s3": uploaded}
        selected_ok = all(results[backend] for backend in backends)
        parts = []
        if committed:
            parts.append(f"committed {len(result.paths)} file(s)")
        if uploaded:
            parts.append("uploaded to S3")
        summary = ", ".join(parts) if parts else "no backend accepted the export"

        payload = {"changed": True, **results, "success": selected_ok}
        _emit(payload, summary.capitalize(), args.json)
        return 0 if selected_ok else 1


def _add_rule_parser(parent: argparse._SubParsersAction, action: str) -> None:
    parser = parent.add_parser(action, help=f"Append an ordered {action} rule")
    selectors = parser.add_mutually_exclusive_group(required=True)
    selectors.add_argument(
        "--origin", help="Normalized origin glob, e.g. github.com/org/*"
    )
    selectors.add_argument("--path", help="Canonical git-root path glob")
    parser.set_defaults(func=cmd_policy_add, action=action)


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Share Claude Code sessions under a global repository policy"
    )
    parser.add_argument("--json", action="store_true", help="Force JSON output")
    sub = parser.add_subparsers(dest="command", required=True)

    status = sub.add_parser(
        "status", help="Show config, policy, hook, and session status"
    )
    status.add_argument("--settings", help="Claude settings path override")
    status.set_defaults(func=cmd_status)

    config = sub.add_parser("config", help="Manage global session configuration")
    config_sub = config.add_subparsers(dest="config_command", required=True)
    config_init = config_sub.add_parser(
        "init", help="Initialize S3-first config without replacing unrelated keys"
    )
    config_init.add_argument(
        "--backend", choices=["s3", "git"], default="s3", help="Storage backend"
    )
    config_init.add_argument("--bucket", help="S3 bucket (default: S3_BUCKET)")
    config_init.add_argument(
        "--region", help="S3 region (default: S3_REGION or AWS_REGION)"
    )
    config_init.add_argument(
        "--machine", help="Stable AgentsView machine name (default: Git user name)"
    )
    config_init.add_argument("--profile", help="Optional AWS profile for boto3")
    config_init.add_argument("--endpoint-url", help="Optional S3-compatible endpoint")
    config_init.add_argument("--prefix", help="Optional bucket key prefix")
    config_init.add_argument("--repo", help="Shared repository for --backend git")
    config_init.add_argument("--default", choices=["allow", "deny"], default="deny")
    config_init.set_defaults(func=cmd_config_init)
    config_show = config_sub.add_parser(
        "show", help="Show effective global session config"
    )
    config_show.set_defaults(func=cmd_config_show)

    s3 = sub.add_parser("s3", help="Validate and inspect the S3 backend")
    s3_sub = s3.add_subparsers(dest="s3_command", required=True)
    s3_check = s3_sub.add_parser("check", help="Verify credentials can list the bucket")
    s3_check.set_defaults(func=cmd_s3_check)
    s3_roots = s3_sub.add_parser(
        "roots", help="Discover AgentsView Claude roots from S3 keys"
    )
    s3_roots.set_defaults(func=cmd_s3_roots)

    policy = sub.add_parser("policy", help="Manage ordered repository allow/deny rules")
    policy_sub = policy.add_subparsers(dest="policy_command", required=True)
    check = policy_sub.add_parser("check", help="Explain the decision for a repository")
    check.add_argument("path", nargs="?", default=".")
    check.set_defaults(func=cmd_policy_check)
    default = policy_sub.add_parser("default", help="Set the policy fallback action")
    default.add_argument("action", choices=["allow", "deny"])
    default.set_defaults(func=cmd_policy_default)
    _add_rule_parser(policy_sub, "allow")
    _add_rule_parser(policy_sub, "deny")
    rules = policy_sub.add_parser("rules", help="List ordered policy rules")
    rules.set_defaults(func=cmd_policy_rules)
    remove = policy_sub.add_parser(
        "remove", help="Remove a policy rule by one-based index"
    )
    remove.add_argument("index", type=int)
    remove.set_defaults(func=cmd_policy_remove)

    hook = sub.add_parser("hook", help="Manage the global Claude Code SessionEnd hook")
    hook_sub = hook.add_subparsers(dest="hook_command", required=True)
    for name, func in (
        ("install", cmd_hook_install),
        ("status", cmd_hook_status),
        ("uninstall", cmd_hook_uninstall),
    ):
        command = hook_sub.add_parser(name, help=f"{name.capitalize()} the global hook")
        command.add_argument("--settings", help="Claude settings path override")
        command.set_defaults(func=func)
    run = hook_sub.add_parser("run", help=argparse.SUPPRESS)
    run.set_defaults(internal_hook=True)

    listing = sub.add_parser("list", help="List recent local Claude Code sessions")
    listing.add_argument("--limit", type=int, default=20)
    listing.set_defaults(func=cmd_list)
    share = sub.add_parser(
        "share", help="Explicitly export one local session without policy evaluation"
    )
    source = share.add_mutually_exclusive_group(required=True)
    source.add_argument("--last", action="store_true")
    source.add_argument("--transcript")
    share.add_argument("--cwd", help="Original session working directory")
    share.set_defaults(func=cmd_share)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = create_parser()
    args = parser.parse_args(argv)
    if getattr(args, "internal_hook", False):
        return _run_hook()
    try:
        return args.func(args)
    except (ConfigError, HookError, S3Error, OSError) as exc:
        if args.json or not sys.stdout.isatty():
            json.dump({"success": False, "error": str(exc)}, sys.stdout)
            sys.stdout.write("\n")
        else:
            print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
