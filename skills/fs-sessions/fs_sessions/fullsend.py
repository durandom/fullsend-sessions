"""Import Fullsend GitHub Actions artifacts into the S3 session archive."""

from __future__ import annotations

import base64
import json
import re
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable

from fs_sessions.s3 import (
    delete_objects,
    object_exists,
    read_json_object,
    upload_objects,
)

DEFAULT_REPOS = (
    "redhat-developer/rhdh-agentic",
    "redhat-developer/rhdh-plugins",
    "redhat-developer/rhdh-plugin-export-overlays",
)
DEFAULT_ARTIFACT_NAMES = (
    "fullsend-code",
    "fullsend-debug",
    "fullsend-fix",
    "fullsend-retro",
    "fullsend-review",
    "fullsend-triage",
)
CONVERTER_VERSION = 3


class FullsendError(RuntimeError):
    """Raised when a Fullsend artifact cannot be fetched or converted."""


@dataclass(frozen=True)
class Artifact:
    id: str
    name: str
    run_id: str
    created: str
    repo: str

    @property
    def fs_agent(self) -> str:
        return f"fs-{self.name.removeprefix('fullsend-')}"

    @property
    def agent_name(self) -> str:
        return self.name.removeprefix("fullsend-")


@dataclass
class ArtifactInput:
    artifact: Artifact
    zip_bytes: bytes
    provenance: Dict[str, Any]
    workflow_log: bytes = b""
    context_files: Dict[str, bytes] = field(default_factory=dict)


@dataclass
class ConvertedArtifact:
    project: str
    machine: str
    session_id: str
    objects: list[tuple[str, bytes]]
    manifest: Dict[str, Any]


@dataclass
class ImportSummary:
    discovered: int = 0
    imported: int = 0
    skipped: int = 0
    failed: int = 0
    sessions: int = 0
    subagents: int = 0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.failed == 0,
            "discovered": self.discovered,
            "imported": self.imported,
            "skipped": self.skipped,
            "failed": self.failed,
            "sessions": self.sessions,
            "subagents": self.subagents,
            "errors": self.errors,
        }


class GitHubClient:
    """Small `gh` adapter so authentication stays in the user's gh config."""

    def _run(self, args: list[str], text: bool = False) -> bytes | str:
        try:
            result = subprocess.run(
                ["gh", *args],
                check=True,
                capture_output=True,
                text=text,
            )
        except FileNotFoundError as exc:
            raise FullsendError("gh is required for Fullsend imports") from exc
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr if text else exc.stderr.decode(errors="replace")
            message = stderr.strip() or f"gh {' '.join(args)} failed"
            raise FullsendError(message) from exc
        return result.stdout

    def api_json(self, endpoint: str) -> Any:
        raw = self._run(["api", endpoint], text=True)
        return json.loads(raw)

    def list_artifacts(
        self,
        repo: str,
        since: datetime | None,
        names: Iterable[str] = DEFAULT_ARTIFACT_NAMES,
        run_id: str | None = None,
    ) -> list[Artifact]:
        found: dict[str, Artifact] = {}
        for name in names:
            page = 1
            while True:
                response = self.api_json(
                    f"repos/{repo}/actions/artifacts?name={name}&per_page=100&page={page}"
                )
                page_items = response.get("artifacts", [])
                if not page_items:
                    break
                stop = False
                for item in page_items:
                    created = item.get("created_at", "")
                    if since and created and _parse_time(created) < since:
                        stop = True
                        continue
                    item_run = str(item.get("workflow_run", {}).get("id", ""))
                    if item.get("expired") or (run_id and item_run != run_id):
                        continue
                    artifact = Artifact(
                        id=str(item["id"]),
                        name=item["name"],
                        run_id=item_run,
                        created=created,
                        repo=repo,
                    )
                    found[artifact.id] = artifact
                if len(page_items) < 100 or stop:
                    break
                page += 1
        return sorted(found.values(), key=lambda item: item.created)

    def artifact_zip(self, artifact: Artifact) -> bytes:
        return self._run(
            ["api", f"repos/{artifact.repo}/actions/artifacts/{artifact.id}/zip"]
        )

    def run_provenance(self, artifact: Artifact) -> Dict[str, Any]:
        run = self.api_json(f"repos/{artifact.repo}/actions/runs/{artifact.run_id}")
        jobs = self.api_json(
            f"repos/{artifact.repo}/actions/runs/{artifact.run_id}/jobs?per_page=100"
        ).get("jobs", [])
        job = _select_job(jobs, artifact.agent_name)
        return {
            "run_id": artifact.run_id,
            "repo": artifact.repo,
            "artifact_id": artifact.id,
            "artifact_name": artifact.name,
            "agent_name": artifact.agent_name,
            "conclusion": run.get("conclusion", ""),
            "run_url": run.get("html_url", ""),
            "created": artifact.created,
            "head_sha": run.get("head_sha", ""),
            "head_branch": run.get("head_branch", ""),
            "event": run.get("event", ""),
            "job_id": str(job.get("id", "")),
            "job_name": job.get("name", ""),
        }

    def workflow_log(self, artifact: Artifact, job_id: str) -> bytes:
        if not job_id:
            return b""
        try:
            return self._run(
                [
                    "run",
                    "view",
                    artifact.run_id,
                    "--repo",
                    artifact.repo,
                    "--job",
                    job_id,
                    "--log",
                ]
            )
        except FullsendError:
            return b""

    def revision_file(self, repo: str, sha: str, path: str) -> bytes | None:
        if not sha or not _safe_repo_path(path):
            return None
        try:
            response = self.api_json(f"repos/{repo}/contents/{path}?ref={sha}")
            encoded = response.get("content", "")
            return base64.b64decode(encoded) if encoded else None
        except (FullsendError, ValueError):
            return None


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def since_days(days: int) -> datetime | None:
    if days <= 0:
        return None
    return datetime.now(timezone.utc) - timedelta(days=days)


def _select_job(jobs: list[Dict[str, Any]], agent: str) -> Dict[str, Any]:
    expected = f"run {agent} agent"
    for job in jobs:
        if any(
            str(step.get("name", "")).lower() == expected
            for step in job.get("steps", [])
        ):
            return job
    eligible = [
        job for job in jobs if job.get("conclusion") != "skipped" and job.get("steps")
    ]
    return eligible[-1] if eligible else {}


def _safe_repo_path(path: str) -> bool:
    return bool(path) and not path.startswith("/") and ".." not in Path(path).parts


def _log_context_path(log: bytes, label: str) -> str:
    text = log.decode(errors="replace")
    matches = re.findall(rf"{re.escape(label)}: .*?/(\.fullsend/\S+)", text)
    return matches[-1] if matches else ""


def fetch_artifact_input(client: GitHubClient, artifact: Artifact) -> ArtifactInput:
    provenance = client.run_provenance(artifact)
    log = client.workflow_log(artifact, provenance.get("job_id", ""))
    sha = provenance.get("head_sha", "")
    agent = artifact.agent_name
    candidates = {
        "CLAUDE.md": ["CLAUDE.md"],
        "AGENTS.md": ["AGENTS.md"],
        "agent": [
            _log_context_path(log, "Agent"),
            f".fullsend/rhdh/agents/{agent}.md",
            f".fullsend/agents/{agent}.md",
            f"agents/{agent}.md",
        ],
        "harness": [
            _log_context_path(log, "Loading harness"),
            f".fullsend/rhdh/harness/{agent}.yaml",
            f".fullsend/harness/{agent}.yaml",
            f"harness/{agent}.yaml",
        ],
        "policy": [
            _log_context_path(log, "Policy"),
            f".fullsend/rhdh/policies/{agent}.yaml",
            f".fullsend/policies/{agent}.yaml",
            f"policies/{agent}.yaml",
        ],
    }
    context: Dict[str, bytes] = {}
    paths: Dict[str, str] = {}
    for label, options in candidates.items():
        for path in dict.fromkeys(options):
            content = client.revision_file(artifact.repo, sha, path)
            if content is not None:
                context[label] = content
                paths[label] = path
                break
    provenance["context"] = paths
    return ArtifactInput(
        artifact=artifact,
        zip_bytes=client.artifact_zip(artifact),
        provenance=provenance,
        workflow_log=log,
        context_files=context,
    )


def _zip_entries(zip_bytes: bytes) -> Dict[str, bytes]:
    with tempfile.SpooledTemporaryFile(max_size=16 * 1024 * 1024) as stream:
        stream.write(zip_bytes)
        stream.seek(0)
        try:
            with zipfile.ZipFile(stream) as archive:
                entries = {}
                for info in archive.infolist():
                    if info.is_dir() or info.filename.startswith("/"):
                        continue
                    if ".." in Path(info.filename).parts:
                        raise FullsendError(f"unsafe artifact member: {info.filename}")
                    entries[info.filename] = archive.read(info)
                return entries
        except zipfile.BadZipFile as exc:
            raise FullsendError("artifact is not a valid ZIP file") from exc


def _find_entry(entries: Dict[str, bytes], suffix: str) -> bytes | None:
    for name in sorted(entries):
        if name.endswith(suffix):
            return entries[name]
    return None


def _load_json(value: bytes | None) -> Dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}


def _json_line(value: Dict[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()


def _transcript_session_id(source: bytes, fallback: str) -> str:
    for raw in source.splitlines():
        try:
            item = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        session_id = item.get("sessionId")
        if isinstance(session_id, str) and session_id:
            if session_id in {".", ".."} or "/" in session_id or "\\" in session_id:
                raise FullsendError(f"unsafe transcript sessionId: {session_id}")
            return session_id
    return fallback


def _work_item(
    summary: Dict[str, Any], agent: str, workflow_log: bytes
) -> tuple[str, str]:
    url = str(summary.get("fullsend.work_item_id", ""))
    match = re.search(r"(\d+)$", url)
    number = match.group(1) if match else "unknown"
    entity = "pr" if "/pull/" in url or agent in {"review", "fix"} else "issue"
    if number == "unknown":
        for line in workflow_log.decode(errors="replace").splitlines():
            match = re.search(r'"(pull_request|issue)".*?"number"\s*:\s*(\d+)', line)
            if match:
                entity = "pr" if match.group(1) == "pull_request" else "issue"
                number = match.group(2)
                break
    return entity, number


def _title_extra(summary: Dict[str, Any]) -> str:
    metrics = summary.get("metrics", {})
    parts = []
    if metrics.get("total_cost_usd") is not None:
        parts.append(f"${metrics['total_cost_usd']}")
    if summary.get("duration_ms") is not None:
        parts.append(f"{int(summary['duration_ms'] / 1000)}s")
    if metrics.get("num_turns") is not None:
        parts.append(f"{metrics['num_turns']} turns")
    return " · " + " · ".join(parts) if parts else ""


def _runtime_metadata(entries: Dict[str, bytes]) -> Dict[str, Any]:
    output = _find_entry(entries, "/output.jsonl")
    if not output:
        return {}
    for raw in output.splitlines():
        try:
            item = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if item.get("type") == "system" and item.get("subtype") == "init":
            return item
    return {}


def _execution_context(
    data: ArtifactInput,
    runtime: Dict[str, Any],
) -> str:
    provenance = data.provenance
    lines = [
        "📋 Fullsend Execution Context",
        "",
        "> Built from GitHub workflow provenance and available Claude runtime "
        "metadata. This is not Claude's proprietary built-in system prompt.",
        "",
        "## Provenance",
        "",
        f"- Agent: `{data.artifact.agent_name}`",
    ]
    for label, key in (
        ("Target revision", "head_sha"),
        ("Workflow job", "job_name"),
    ):
        if provenance.get(key):
            lines.append(f"- {label}: `{provenance[key]}`")
    log_text = data.workflow_log.decode(errors="replace")
    workflow_values = (
        ("Fullsend", r"fullsend ([0-9]+\.[0-9]+\.[0-9]+)"),
        ("Sandbox image", r"Image: ([^\s]+)"),
    )
    for label, pattern in workflow_values:
        matches = re.findall(pattern, log_text)
        if matches:
            lines.append(f"- {label}: `{matches[-1]}`")
    resources = sorted(set(re.findall(r"Base: (https://[^\s]+)", log_text)))
    if resources:
        lines.extend(["", "### Resolved remote resources", ""])
        lines.extend(f"- <{resource}>" for resource in resources)
    if runtime:
        lines.extend(["", "## Claude Runtime", ""])
        for label, key in (
            ("Model", "model"),
            ("Claude Code", "claude_code_version"),
            ("Permission mode", "permissionMode"),
            ("Working directory", "cwd"),
        ):
            if runtime.get(key):
                lines.append(f"- {label}: `{runtime[key]}`")
        for label, key in (
            ("Tools", "tools"),
            ("Agents", "agents"),
            ("Skills", "skills"),
        ):
            values = runtime.get(key) or []
            if values:
                lines.append(f"- {label}: {', '.join(map(str, values))}")
        plugins = [
            item.get("name", "") if isinstance(item, dict) else str(item)
            for item in runtime.get("plugins", [])
        ]
        plugins = [item for item in plugins if item]
        if plugins:
            lines.append(f"- Plugins: {', '.join(plugins)}")
    section_names = {
        "agent": "Agent Definition",
        "CLAUDE.md": "Project Instructions: CLAUDE.md",
        "AGENTS.md": "Project Instructions: AGENTS.md",
        "harness": "Harness",
        "policy": "Policy",
    }
    for key in ("agent", "CLAUDE.md", "AGENTS.md", "harness", "policy"):
        content = data.context_files.get(key)
        if not content:
            continue
        path = provenance.get("context", {}).get(key, key)
        lines.extend(
            [
                "",
                "---",
                "",
                f"## {section_names[key]}",
                "",
                f"_Source: `{path}` at `{provenance.get('head_sha', '')}`_",
                "",
                content.decode(errors="replace"),
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _rewrite_transcript(source: bytes, title: str, cwd: str) -> list[bytes]:
    output = []
    for raw in source.splitlines():
        if not raw:
            continue
        try:
            item = json.loads(raw)
        except json.JSONDecodeError:
            output.append(raw)
            continue
        kind = item.get("type")
        if kind == "queue-operation":
            continue
        if kind == "user":
            item["cwd"] = cwd
        if kind == "ai-title":
            item["aiTitle"] = title
        elif (
            kind == "attachment"
            and item.get("attachment", {}).get("commandMode") == "task-notification"
        ):
            continue
        output.append(_json_line(item))
    return output


def _prefixed(prefix: str, key: str) -> str:
    prefix = prefix.strip("/")
    return f"{prefix}/{key}" if prefix else key


def manifest_key(prefix: str, artifact: Artifact) -> str:
    return _prefixed(
        prefix,
        f"imports/github/{artifact.repo}/{artifact.run_id}/"
        f"{artifact.name}-{artifact.id}/manifest.json",
    )


def convert_artifact(data: ArtifactInput, prefix: str = "") -> ConvertedArtifact:
    entries = _zip_entries(data.zip_bytes)
    project = data.artifact.repo.rsplit("/", 1)[-1]
    machine = data.artifact.fs_agent
    archive_root = _prefixed(
        prefix,
        f"imports/github/{data.artifact.repo}/{data.artifact.run_id}/"
        f"{data.artifact.name}-{data.artifact.id}",
    )
    archive_objects = [
        (f"{archive_root}/artifact.zip", data.zip_bytes),
        (
            f"{archive_root}/provenance.json",
            json.dumps(data.provenance, indent=2, sort_keys=True).encode() + b"\n",
        ),
    ]
    if data.workflow_log:
        archive_objects.append((f"{archive_root}/workflow.log", data.workflow_log))
    for label, content in sorted(data.context_files.items()):
        archive_objects.append((f"{archive_root}/context/{label}", content))
    transcripts = [
        name for name in entries if "/transcripts/" in name and name.endswith(".jsonl")
    ]
    main = [name for name in transcripts if "-agent-a" not in Path(name).name]
    if not main:
        manifest = {
            "schema_version": CONVERTER_VERSION,
            "status": "no_session",
            "artifact_id": data.artifact.id,
            "artifact_name": data.artifact.name,
            "run_id": data.artifact.run_id,
            "repo": data.artifact.repo,
            "machine": machine,
            "project": project,
            "session_id": None,
            "subagent_count": 0,
            "destinations": [],
        }
        return ConvertedArtifact(project, machine, "", archive_objects, manifest)
    if len(main) != 1:
        raise FullsendError(f"expected one main transcript, found {len(main)}")
    subagents = sorted(set(transcripts) - set(main))
    main_name = main[0]
    session_id = _transcript_session_id(entries[main_name], Path(main_name).stem)
    summary = _load_json(_find_entry(entries, "/run-summary.json"))
    result = _load_json(_find_entry(entries, "/agent-result.json"))
    runtime = _runtime_metadata(entries)
    entity, number = _work_item(summary, data.artifact.agent_name, data.workflow_log)
    extra = _title_extra(summary)
    conclusion = data.provenance.get("conclusion", "")
    title = (
        f"{data.artifact.agent_name} {entity} #{number} - run "
        f"{data.artifact.run_id} [{conclusion}{extra}]"
    )
    created = data.artifact.created
    cwd = f"/fullsend/{project}"
    meta = {
        "type": "user",
        "timestamp": created,
        "message": {
            "content": f"{title}\n{data.provenance.get('run_url', '')}".rstrip()
        },
        "cwd": cwd,
    }
    context = {
        "type": "user",
        "timestamp": created,
        "message": {"content": _execution_context(data, runtime)},
        "cwd": cwd,
    }
    lines = [_json_line(meta), _json_line(context)]
    lines.extend(_rewrite_transcript(entries[main_name], title, cwd))
    comment = result.get("comment")
    if comment:
        lines.append(
            _json_line(
                {
                    "type": "assistant",
                    "timestamp": created,
                    "message": {
                        "role": "assistant",
                        "type": "message",
                        "content": [{"type": "text", "text": comment}],
                        "stop_reason": "end_turn",
                    },
                }
            )
        )
    root = f"{machine}/raw/claude/{project}"
    objects: list[tuple[str, bytes]] = []
    destinations = []
    for name in subagents:
        filename = Path(name).name
        clean = "agent-" + filename.split("-agent-", 1)[-1]
        key = _prefixed(prefix, f"{root}/{session_id}/subagents/{clean}")
        child = b"\n".join(_rewrite_transcript(entries[name], title, cwd)) + b"\n"
        objects.append((key, child))
        destinations.append(key)
    parent_key = _prefixed(prefix, f"{root}/{session_id}.jsonl")
    objects.append((parent_key, b"\n".join(lines) + b"\n"))
    destinations.append(parent_key)

    objects.extend(archive_objects)
    manifest = {
        "schema_version": CONVERTER_VERSION,
        "status": "converted",
        "artifact_id": data.artifact.id,
        "artifact_name": data.artifact.name,
        "run_id": data.artifact.run_id,
        "repo": data.artifact.repo,
        "machine": machine,
        "project": project,
        "session_id": session_id,
        "subagent_count": len(subagents),
        "destinations": destinations,
    }
    return ConvertedArtifact(project, machine, session_id, objects, manifest)


def _write_converted_artifact(
    s3_config: Dict[str, Any],
    converted: ConvertedArtifact,
    key: str,
    previous_manifest: Dict[str, Any] | None,
) -> None:
    manifest_body = (
        json.dumps(converted.manifest, indent=2, sort_keys=True).encode() + b"\n"
    )
    upload_objects(s3_config, converted.objects)
    previous = set((previous_manifest or {}).get("destinations", []))
    current = set(converted.manifest["destinations"])
    prefix = str(s3_config.get("prefix", ""))
    generated_root = _prefixed(
        prefix,
        f"{converted.machine}/raw/claude/{converted.project}/",
    )
    stale = sorted(
        destination
        for destination in previous - current
        if isinstance(destination, str)
        and destination.startswith(generated_root)
        and destination.endswith(".jsonl")
    )
    delete_objects(s3_config, stale)
    upload_objects(s3_config, [(key, manifest_body)])


def import_artifacts(
    s3_config: Dict[str, Any],
    artifacts: Iterable[Artifact],
    client: GitHubClient,
    *,
    dry_run: bool = False,
    force: bool = False,
) -> ImportSummary:
    summary = ImportSummary()
    prefix = str(s3_config.get("prefix", ""))
    for artifact in artifacts:
        summary.discovered += 1
        key = manifest_key(prefix, artifact)
        try:
            previous_manifest = None
            if not dry_run and not force and object_exists(s3_config, key):
                summary.skipped += 1
                continue
            if not dry_run and force:
                previous_manifest = read_json_object(s3_config, key)
            converted = convert_artifact(fetch_artifact_input(client, artifact), prefix)
            if not dry_run:
                _write_converted_artifact(s3_config, converted, key, previous_manifest)
            summary.imported += 1
            summary.sessions += bool(converted.session_id)
            summary.subagents += converted.manifest["subagent_count"]
        except Exception as exc:
            summary.failed += 1
            summary.errors.append(
                f"{artifact.repo} run {artifact.run_id} {artifact.name}: {exc}"
            )
    return summary


def cached_artifact_inputs(cache_dir: Path) -> list[ArtifactInput]:
    """Load the old rhdh-fullsend artifact cache for one-time backfill."""
    loaded = []
    for zip_path in sorted(cache_dir.glob("*/*.zip")):
        sidecar = zip_path.with_suffix(".json")
        if not sidecar.is_file():
            continue
        provenance = _load_json(sidecar.read_bytes())
        repo = provenance.get("repo")
        run_id = str(provenance.get("run_id", ""))
        name = provenance.get("artifact_name")
        if not repo or not run_id or not name:
            continue
        artifact = Artifact(
            id=f"legacy-{run_id}-{name}",
            name=name,
            run_id=run_id,
            created=provenance.get("created", ""),
            repo=repo,
        )
        log_path = zip_path.with_suffix(".log")
        context: Dict[str, bytes] = {}
        revision_dir = zip_path.parent / "revisions" / provenance.get("head_sha", "")
        context_paths = provenance.get("context", {})
        normalized_context_paths = {}
        for label in ("agent", "harness", "policy"):
            path = context_paths.get(f"{label}_path", context_paths.get(label, ""))
            candidate = revision_dir / path
            if _safe_repo_path(path) and candidate.is_file():
                context[label] = candidate.read_bytes()
                normalized_context_paths[label] = path
        for filename in ("CLAUDE.md", "AGENTS.md"):
            candidate = revision_dir / filename
            if candidate.is_file():
                context[filename] = candidate.read_bytes()
                normalized_context_paths[filename] = filename
        provenance["context"] = normalized_context_paths
        loaded.append(
            ArtifactInput(
                artifact=artifact,
                zip_bytes=zip_path.read_bytes(),
                provenance=provenance,
                workflow_log=log_path.read_bytes() if log_path.is_file() else b"",
                context_files=context,
            )
        )
    return loaded


def import_cached_artifacts(
    s3_config: Dict[str, Any],
    inputs: Iterable[ArtifactInput],
    *,
    dry_run: bool = False,
    force: bool = False,
) -> ImportSummary:
    summary = ImportSummary()
    prefix = str(s3_config.get("prefix", ""))
    for data in inputs:
        summary.discovered += 1
        key = manifest_key(prefix, data.artifact)
        try:
            previous_manifest = None
            if not dry_run and not force and object_exists(s3_config, key):
                summary.skipped += 1
                continue
            if not dry_run and force:
                previous_manifest = read_json_object(s3_config, key)
            converted = convert_artifact(data, prefix)
            if not dry_run:
                _write_converted_artifact(s3_config, converted, key, previous_manifest)
            summary.imported += 1
            summary.sessions += bool(converted.session_id)
            summary.subagents += converted.manifest["subagent_count"]
        except Exception as exc:
            summary.failed += 1
            summary.errors.append(
                f"{data.artifact.repo} run {data.artifact.run_id} "
                f"{data.artifact.name}: {exc}"
            )
    return summary
