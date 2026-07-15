"""S3 upload backend for session transcripts."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

log = logging.getLogger(__name__)


class S3Error(RuntimeError):
    """Raised when the configured S3 backend cannot be used."""


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
        log.warning("S3 backend configured but no bucket specified")
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
