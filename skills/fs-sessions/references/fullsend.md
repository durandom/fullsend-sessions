# Import Fullsend GitHub Actions sessions

Use the installed CLI; do not reconstruct or upload artifacts manually.
GitHub authentication comes from `gh`, and S3 authentication comes from the
configured boto3 credential chain.

Preview recent artifacts before writing:

```bash
"$FS" fullsend import --since 7d --dry-run
```

Import after the preview succeeds:

```bash
"$FS" fullsend import --since 7d
```

Scope to a repository or workflow run when requested:

```bash
"$FS" fullsend import --repo redhat-developer/rhdh-agentic --run-id 123456789
```

The mapping is fixed:

```text
project = repository basename
agent   = claude
machine = fs-<artifact agent>, for example fs-code or fs-review
```

The importer writes subagents before the parent session, archives the source
ZIP, workflow log, provenance, and available revision-pinned context, then
writes a manifest last. An existing manifest skips the artifact. Use `--force`
only when the user explicitly wants conversion with the current schema.

For the old `rhdh-fullsend/agentsview/artifacts` cache, preview and then import:

```bash
"$FS" fullsend import --cache-dir /absolute/path/to/artifacts --dry-run
"$FS" fullsend import --cache-dir /absolute/path/to/artifacts
```

Artifacts without a transcript are archived with a `no_session` manifest and
do not create an AgentsView session.
