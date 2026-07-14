"""S3 upload backend for session transcripts."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

log = logging.getLogger(__name__)


def _get_client(s3_config: Dict[str, Any]):
    """Create a boto3 S3 client from config. Raises ImportError if boto3 missing."""
    try:
        import boto3
    except ImportError:
        raise ImportError(
            "boto3 is required for S3 uploads: pip install fs-sessions[s3]"
        )

    kwargs: Dict[str, Any] = {}
    if s3_config.get("region"):
        kwargs["region_name"] = s3_config["region"]
    if s3_config.get("endpoint_url"):
        kwargs["endpoint_url"] = s3_config["endpoint_url"]
    if s3_config.get("profile"):
        session = boto3.Session(profile_name=s3_config["profile"])
        return session.client("s3", **kwargs)
    return boto3.client("s3", **kwargs)


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
    except (ImportError, Exception) as exc:
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
