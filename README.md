# fullsend-sessions

Store selected Claude Code sessions and Fullsend GitHub Actions runs in S3,
then browse and query them with
[AgentsView](https://github.com/kenn-io/agentsview).

S3 is the only transcript backend. Git is used only to identify repositories
for privacy policy checks and as the source of GitHub Actions artifacts.

## Session identity

AgentsView exposes project, agent, and machine dimensions. This repository maps
them consistently:

| AgentsView field | Meaning |
|---|---|
| `project` | Git repository name, such as `rhdh-agentic` |
| `agent` | Session format/runtime, normally `claude` |
| `machine` | Producing user or Fullsend agent, such as `marcel-hild` or `fs-code` |

S3 objects follow AgentsView's native layout:

```text
<machine>/raw/claude/<project>/<session-id>.jsonl
<machine>/raw/claude/<project>/<session-id>/subagents/...
```

## Install

Prerequisites are Node.js/npm, Python 3.10 or newer, and boto3:

```bash
python3 -c 'import boto3' 2>/dev/null || python3 -m pip install --user boto3
```

Install both skills globally for Claude Code and Codex:

```bash
npx skills add -g git@github.com:durandom/fullsend-sessions.git \
  --skill fs-sessions agentsview \
  --agent claude-code codex \
  --copy -y
```

Start a new agent session after installation.

## Configure session sharing

Load an existing S3 bucket and boto3-compatible credentials, then ask an agent:

> Use fs-sessions to configure S3 session sharing. Use my stable user identity
> as the AgentsView machine, keep policy default-deny, allow this repository,
> verify one upload, and install exactly one global hook.

Manual setup uses the installed CLI:

```bash
FS_SESSIONS="$HOME/.agents/skills/fs-sessions/scripts/fs-sessions"

export S3_BUCKET=team-agent-sessions
export S3_REGION=eu-central-1
export AWS_PROFILE=team-sessions  # or use the normal AWS environment chain

"$FS_SESSIONS" config init --machine alice
"$FS_SESSIONS" s3 check
```

The machine value is a stable actor identity, not necessarily a physical
computer. It becomes the AgentsView machine filter. Credentials remain in the
standard boto3 credential chain; only bucket metadata is stored in
`~/.config/rhdh-skill/config.json`.

## Choose which repositories may upload

Automatic uploads are controlled by a global ordered policy. The recommended
model is a default-deny whitelist:

```bash
"$FS_SESSIONS" policy default deny
"$FS_SESSIONS" policy allow --origin 'github.com/example-org/*'
"$FS_SESSIONS" policy check /absolute/path/to/repository
```

The last matching rule wins. A repository may opt out with
`.rhdh/config.json`, but cannot grant itself upload permission:

```json
{"sessions":{"enabled":false}}
```

Verify a real upload, then install the global Claude Code `SessionEnd` hook:

```bash
"$FS_SESSIONS" share --last
"$FS_SESSIONS" s3 roots
"$FS_SESSIONS" hook install
"$FS_SESSIONS" status
```

The hook preserves the parent transcript, nested subagents, tool results, and
regular companion files.

## Import Fullsend runs from GitHub

The importer queries exact `fullsend-*` GitHub Actions artifacts, downloads
them on demand, reconstructs AgentsView-compatible sessions, and uploads them
directly to S3. Repository names become projects and artifact agent names become
machines:

```text
fullsend-code   -> fs-code
fullsend-review -> fs-review
fullsend-triage -> fs-triage
```

Preview the last seven days without writing S3:

```bash
"$FS_SESSIONS" fullsend import --since 7d --dry-run
```

Import them:

```bash
"$FS_SESSIONS" fullsend import --since 7d
```

Useful scopes:

```bash
"$FS_SESSIONS" fullsend import \
  --repo redhat-developer/rhdh-agentic \
  --run-id 123456789

"$FS_SESSIONS" fullsend import --all
```

Each import stores the original artifact, workflow provenance, available
revision-pinned context, the derived session family, and a completion manifest.
Existing manifests make repeated imports idempotent. `--force` reconverts an
artifact with the current converter.

For the one-time migration from the old `rhdh-fullsend` cache:

```bash
"$FS_SESSIONS" fullsend import \
  --cache-dir /path/to/rhdh-fullsend/agentsview/artifacts \
  --dry-run
```

Remove `--dry-run` after reviewing the counts.

## Start AgentsView

Use the `agentsview` skill to create private runtime configuration outside Git
and populate `claude_project_dirs` from every root returned by:

```bash
"$FS_SESSIONS" s3 roots
```

The deterministic CLI operation used by that setup is:

```bash
"$FS_SESSIONS" s3 agentsview-config \
  --data-dir "$HOME/.local/share/fullsend-agentsview"
```

It changes only `claude_project_dirs` and preserves existing AgentsView tokens
and unrelated runtime settings.

Then start the repository's S3-only compose service:

```bash
just up
```

The runtime directory defaults to
`~/.local/share/fullsend-agentsview`; override it with `AGENTSVIEW_DATA`.
Stop the container without deleting its derived index:

```bash
just down
```

The `agentsview` skill connects its host CLI to the container and remains
read-only by default.

## Development

```bash
uv sync
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
```
