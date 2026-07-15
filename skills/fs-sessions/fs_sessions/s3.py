"""S3 storage for session transcripts and Fullsend imports."""

from __future__ import annotations

import json
import logging
import mimetypes
import os
import tempfile
from pathlib import Path
from typing import Any, Dict

log = logging.getLogger(__name__)


class S3Error(RuntimeError):
    """Raised when the configured S3 storage cannot be used."""


def _get_client(s3_config: Dict[str, Any]):
    """Create a boto3 S3 client from config. Raises ImportError if boto3 missing."""
    try:
        import boto3
    except ImportError as exc:
        raise S3Error(
            "boto3 is required for S3 uploads: pip install fs-sessions[s3]"
        ) from exc

    kwargs: Dict[str, Any] = {}
    if s3_config.get("region"):
        kwargs["region_name"] = s3_config["region"]
    if s3_config.get("endpoint_url"):
        kwargs["endpoint_url"] = s3_config["endpoint_url"]
    if s3_config.get("profile"):
        session = boto3.Session(profile_name=s3_config["profile"])
        return session.client("s3", **kwargs)
    return boto3.client("s3", **kwargs)


def check_access(s3_config: Dict[str, Any]) -> Dict[str, Any]:
    """Verify credentials can list the configured bucket without writing data."""
    bucket = s3_config.get("bucket")
    if not bucket:
        raise S3Error("S3 bucket is not configured")
    try:
        response = _get_client(s3_config).list_objects_v2(Bucket=bucket, MaxKeys=1)
    except Exception as exc:
        if isinstance(exc, S3Error):
            raise
        raise S3Error(f"cannot list s3://{bucket}: {exc}") from exc
    return {
        "success": True,
        "bucket": bucket,
        "region": s3_config.get("region"),
        "can_list": True,
        "has_objects": bool(response.get("Contents")),
    }


def discover_claude_roots(s3_config: Dict[str, Any]) -> list[str]:
    """Discover AgentsView Claude roots from uploaded object keys."""
    bucket = s3_config.get("bucket")
    if not bucket:
        raise S3Error("S3 bucket is not configured")
    prefix = s3_config.get("prefix", "").strip("/")
    list_prefix = f"{prefix}/" if prefix else ""
    client = _get_client(s3_config)
    token = None
    machines = set()
    try:
        while True:
            kwargs: Dict[str, Any] = {
                "Bucket": bucket,
                "Prefix": list_prefix,
            }
            if token:
                kwargs["ContinuationToken"] = token
            response = client.list_objects_v2(**kwargs)
            for item in response.get("Contents", []):
                key = item.get("Key", "")
                relative = (
                    key[len(list_prefix) :] if key.startswith(list_prefix) else key
                )
                parts = relative.split("/")
                if len(parts) >= 4 and parts[1:3] == ["raw", "claude"]:
                    machines.add(parts[0])
            if not response.get("IsTruncated"):
                break
            token = response.get("NextContinuationToken")
    except Exception as exc:
        raise S3Error(f"cannot discover Claude roots in s3://{bucket}: {exc}") from exc

    base = f"s3://{bucket}/"
    if prefix:
        base += f"{prefix}/"
    return [f"{base}{machine}/raw/claude" for machine in sorted(machines)]


def s3_key(username: str, project: str, relative_path: str, prefix: str = "") -> str:
    """Build the S3 object key using AgentsView path convention.

    AgentsView expects: <machine>/raw/claude/<project>/<uuid>.jsonl
    """
    key = f"{username}/raw/claude/{project}/{relative_path}"
    if prefix:
        key = f"{prefix.rstrip('/')}/{key}"
    return key


def upload_session(
    s3_config: Dict[str, Any],
    paths: list[Path],
    base_dir: Path,
    username: str,
    project: str,
) -> bool:
    """Upload exported session files to S3.

    Returns True on success, False on failure (best-effort).
    """
    bucket = s3_config.get("bucket")
    if not bucket:
        log.warning("S3 configured but no bucket specified")
        return False

    prefix = s3_config.get("prefix", "")

    try:
        client = _get_client(s3_config)
    except Exception as exc:
        log.warning("S3 client creation failed: %s", exc)
        return False

    ok = True
    for path in paths:
        rel = path.relative_to(base_dir / "sessions")
        if len(rel.parts) < 2:
            log.warning("Unexpected session export path: %s", path)
            ok = False
            continue
        session_relative = Path(*rel.parts[1:]).as_posix()
        key = s3_key(username, project, session_relative, prefix)
        try:
            client.upload_file(str(path), bucket, key)
            log.info("Uploaded s3://%s/%s", bucket, key)
        except Exception as exc:
            log.warning("S3 upload failed for %s: %s", key, exc)
            ok = False
    return ok


def object_exists(s3_config: Dict[str, Any], key: str) -> bool:
    """Return whether an object exists without downloading it."""
    bucket = s3_config.get("bucket")
    if not bucket:
        raise S3Error("S3 bucket is not configured")
    client = _get_client(s3_config)
    try:
        client.head_object(Bucket=bucket, Key=key)
        return True
    except Exception as exc:
        response = getattr(exc, "response", {})
        code = str(response.get("Error", {}).get("Code", ""))
        if code in {"404", "NoSuchKey", "NotFound"}:
            return False
        raise S3Error(f"cannot inspect s3://{bucket}/{key}: {exc}") from exc


def upload_objects(
    s3_config: Dict[str, Any],
    objects: list[tuple[str, bytes]],
) -> None:
    """Upload in-memory objects in order, raising on the first failure."""
    bucket = s3_config.get("bucket")
    if not bucket:
        raise S3Error("S3 bucket is not configured")
    client = _get_client(s3_config)
    for key, body in objects:
        content_type = (
            "application/x-ndjson"
            if key.endswith(".jsonl")
            else mimetypes.guess_type(key)[0] or "application/octet-stream"
        )
        try:
            client.put_object(
                Bucket=bucket,
                Key=key,
                Body=body,
                ContentType=content_type,
            )
        except Exception as exc:
            raise S3Error(f"cannot upload s3://{bucket}/{key}: {exc}") from exc


def repair_export_project_metadata(
    s3_config: Dict[str, Any], *, apply: bool = False
) -> Dict[str, Any]:
    """Repair old exporter-generated headers that included machine in project cwd."""
    bucket = s3_config.get("bucket")
    if not bucket:
        raise S3Error("S3 bucket is not configured")
    prefix = s3_config.get("prefix", "").strip("/")
    list_prefix = f"{prefix}/" if prefix else ""
    client = _get_client(s3_config)
    token = None
    scanned = 0
    changed = 0
    try:
        while True:
            kwargs: Dict[str, Any] = {"Bucket": bucket, "Prefix": list_prefix}
            if token:
                kwargs["ContinuationToken"] = token
            response = client.list_objects_v2(**kwargs)
            for item in response.get("Contents", []):
                key = item.get("Key", "")
                relative = (
                    key[len(list_prefix) :] if key.startswith(list_prefix) else key
                )
                parts = relative.split("/")
                if (
                    len(parts) != 5
                    or parts[1:3] != ["raw", "claude"]
                    or not parts[4].endswith(".jsonl")
                    or parts[0].startswith("fs-")
                ):
                    continue
                scanned += 1
                body = client.get_object(Bucket=bucket, Key=key)["Body"].read()
                first, separator, rest = body.partition(b"\n")
                try:
                    metadata = json.loads(first)
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue
                project = parts[3]
                message = metadata.get("message", {})
                content = (
                    message.get("content", "") if isinstance(message, dict) else ""
                )
                old_cwd = metadata.get("cwd", "")
                if (
                    metadata.get("type") != "user"
                    or not content.startswith("[Session:")
                    or not old_cwd.startswith("/sessions/")
                ):
                    continue
                cwd = f"/sessions/{project}"
                if old_cwd == cwd:
                    continue
                metadata["cwd"] = cwd
                message["content"] = content.replace(old_cwd, cwd, 1)
                repaired = json.dumps(metadata, separators=(",", ":")).encode()
                if separator:
                    repaired += separator + rest
                changed += 1
                if apply:
                    client.put_object(
                        Bucket=bucket,
                        Key=key,
                        Body=repaired,
                        ContentType="application/x-ndjson",
                    )
            if not response.get("IsTruncated"):
                break
            token = response.get("NextContinuationToken")
    except Exception as exc:
        if isinstance(exc, S3Error):
            raise
        raise S3Error(
            f"cannot repair project metadata in s3://{bucket}: {exc}"
        ) from exc
    return {"success": True, "apply": apply, "scanned": scanned, "changed": changed}


def write_agentsview_config(
    s3_config: Dict[str, Any], data_dir: Path
) -> Dict[str, Any]:
    """Update only AgentsView's Claude S3 roots in its private config."""
    roots = discover_claude_roots(s3_config)
    if not roots:
        raise S3Error("no Claude S3 roots found; upload a session first")
    data_dir = data_dir.expanduser().resolve()
    data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(data_dir, 0o700)
    path = data_dir / "config.toml"
    original = path.read_text(encoding="utf-8") if path.exists() else ""
    rendered = (
        "claude_project_dirs = [\n"
        + "".join(f"  {json.dumps(root)},\n" for root in roots)
        + "]"
    )
    lines = original.splitlines()
    start = None
    end = None
    depth = 0
    for index, line in enumerate(lines):
        if start is None and line.strip().startswith("claude_project_dirs"):
            start = index
        if start is not None:
            depth += line.count("[") - line.count("]")
            if depth <= 0:
                end = index + 1
                break
    replacement = rendered.splitlines()
    if start is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines.extend(replacement)
    else:
        if end is None:
            raise S3Error(f"invalid claude_project_dirs assignment in {path}")
        lines[start:end] = replacement
    content = "\n".join(lines).rstrip() + "\n"
    fd, temp_name = tempfile.mkstemp(prefix="config-", suffix=".toml", dir=data_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
        os.chmod(temp_name, 0o600)
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise
    return {"config": str(path), "roots": roots, "count": len(roots)}
