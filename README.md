# fullsend-sessions

Share and browse Claude Code session transcripts across your team.

Allowed sessions are uploaded to S3 when a Claude Code session ends. [AgentsView](https://github.com/kenn-io/agentsview) reads the bucket directly for browsing, searching, per-user filtering, and analysis. Git storage remains available only as an explicit legacy backend.

## Quick start

```bash
# 1. Clone the skill repository
git clone git@github.com:durandom/fullsend-sessions.git

# 2. Install the session-sharing skill globally
npx skills add -g git@github.com:durandom/fullsend-sessions.git \
  --skill fs-sessions --agent claude-code codex -y --copy

# 3. Resolve the installed CLI
FS_SESSIONS="$HOME/.agents/skills/fs-sessions/scripts/fs-sessions"

# 4. Load S3 deployment settings and credentials without printing them
export S3_BUCKET=team-agent-sessions
export S3_REGION=eu-central-1
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...

# 5. Configure the S3-first backend and a default-deny policy
"$FS_SESSIONS" config init --machine alice-laptop
"$FS_SESSIONS" s3 check
"$FS_SESSIONS" policy allow --origin 'github.com/example-org/*'

# 6. Verify one repository and one real upload, then install the hook
"$FS_SESSIONS" policy check /absolute/path/to/an/allowed-repository
"$FS_SESSIONS" share --last
"$FS_SESSIONS" s3 roots
"$FS_SESSIONS" hook install
"$FS_SESSIONS" status
```

Configuration lives in `~/.config/rhdh-skill/config.json` so it can later move into the RHDH skill without another migration. The hook lives once in `~/.claude/settings.json`; repositories cannot install their own permission to export transcripts.

### Update the skill

The global installation remembers its Git source. Pull the current
`fs-sessions` version with:

```bash
npx skills update -g fs-sessions
```

Start a new Claude Code session after installing or updating so Claude
discovers the current skill instructions. Confirm the installation when needed
with:

```bash
npx skills list -g --json
```

### Configure through Claude Code

Claude can run the policy and hook CLI through the installed skill. For a safe
initial setup, ask:

> Use fs-sessions to configure S3 session sharing from my current environment.
> Keep the policy default-deny, confirm the bucket access and machine name,
> install exactly one global SessionEnd hook, share one test session, and show
> the resulting AgentsView roots.

Allow another repository with an origin rule:

> Use fs-sessions to allow automatic session sharing for
> `/absolute/path/to/repository`. Keep default-deny, prefer an origin rule, and
> show the normalized origin and policy decision afterward.

Inspect an existing setup without changing it:

> Use fs-sessions to show the current configuration and hook status, and
> explain whether this repository is allowed to export sessions.

For mixed policies, state the broad rule before its narrower exceptions because
the last matching rule wins:

> Use fs-sessions with default-deny. Allow `github.com/example-org/*`, deny
> `/work/customer-*`, then allow `/work/customer-sanitized-demo`. Show the
> ordered rules and verify each affected repository.

## How it works

```
Session ends → global SessionEnd hook → repository policy check
  → stages the parent transcript and its complete companion directory
  → uploads to S3 under <machine>/raw/claude/<project>/
  → removes the temporary staging copy
```

Sessions preserve Claude's AgentsView-compatible layout:

```text
<machine>/raw/claude/<project>/
  <session-id>.jsonl
  <session-id>/
    subagents/**
    tool-results/**
    <other regular companion files>
```

The parent transcript gets a metadata header with project, user, and timestamp. Companion files are copied byte-for-byte, including binary attachments; symlinks are skipped. This lets AgentsView connect delegated subagent work to its parent and resolve externalized tool results.

After an upload succeeds, Claude Code shows a message such as `fs-sessions: exported and uploaded 3 session files to S3 for example/session-id.` Denied or unchanged sessions stay quiet, and the hook never reports a backend upload that failed.

## Repository policy

Automatic sharing fails closed: missing or malformed configuration, non-Git directories, and unmatched repositories under `default: deny` are skipped silently. Rules are evaluated in order and the last matching rule wins.

```bash
# Whitelist an organization.
"$FS_SESSIONS" policy default deny
"$FS_SESSIONS" policy allow --origin 'github.com/example-org/*'

# Exclude sensitive paths, then allow one sanitized exception.
"$FS_SESSIONS" policy deny --path '/work/customer-*'
"$FS_SESSIONS" policy allow --path '/work/customer-sanitized-demo'

"$FS_SESSIONS" policy rules
"$FS_SESSIONS" policy check /work/customer-sanitized-demo
```

Origin rules normalize SSH and HTTPS remotes to `host/owner/repository`. Path rules match the canonical Git root. A repository may opt out with `.rhdh/config.json` containing `{"sessions":{"enabled":false}}`, but local configuration cannot opt a repository into sharing.

## CLI

List or explicitly share sessions without the automatic-hook policy:

```bash
"$FS_SESSIONS" list
"$FS_SESSIONS" share --last
"$FS_SESSIONS" share --transcript /path/to/session.jsonl --cwd /path/to/project
```

Inspect and manage the hook:

```bash
"$FS_SESSIONS" hook status
"$FS_SESSIONS" hook install
"$FS_SESSIONS" hook uninstall
```

When migrating an old project-local hook, verify the global policy and hook first. Then remove only the managed command while preserving unrelated project settings:

```bash
"$FS_SESSIONS" hook uninstall \
  --settings /path/to/project/.claude/settings.json
```

## AgentsView

Browse shared sessions in a web UI:

```bash
just sessions-s3                      # start AgentsView directly from S3
just down-s3                          # stop S3 viewer and remove derived index
```

For LAN access: `AGENTSVIEW_HOST=$(hostname).local just sessions`

## Fullsend runs

Fetch and browse [fullsend](https://github.com/redhat-developer/rhdh-agentic) agent runs from GitHub Actions:

```bash
just fetch                            # download runs from default repos
just up                               # fetch + start AgentsView
just local                            # import local fullsend runs (auto-discovers from $TMPDIR)
just local /path/to/output            # import from explicit path
```

## Skill commands

Once installed, use `/fs-sessions` in any Claude Code session:

| Command | Description |
|---------|-------------|
| `/fs-sessions setup` | Configure S3, credentials, machine, policy, and hook |
| `/fs-sessions policy` | Allow, deny, list, or explain repository rules |
| `/fs-sessions hook` | Install, inspect, migrate, or remove the global hook |
| `/fs-sessions status` | Check S3 config, policy, credentials, and hook state |
| `/fs-sessions share` | List or explicitly upload a local session |
| `/fs-sessions s3` | Validate access or discover AgentsView roots |
| `/fs-sessions view` | Start AgentsView |

The repository also contains an `agentsview` skill for factual, read-only access
to a local AgentsView archive through its CLI:

```bash
npx skills add git@github.com:durandom/fullsend-sessions.git --skill agentsview
```

It can find and inspect sessions, search historical evidence, and retrieve
health, usage, activity, and stats data. Session-quality analysis and workflow
recommendations are intentionally out of scope.

## Pod

This repo is home to the RHDH AI-Augmented Pod — a focused sub-team experimenting with AI-driven engineering workflows. See [docs/](docs/) for the charter and operating principles.

## Directory layout

```
docs/                                 # Pod charter and commandments
meetings/transcripts/                 # Google Meet transcript exports
scripts/
  fetch-fullsend-runs.sh              # download fullsend runs from GH Actions
  import-local-run.sh                 # import local fullsend runs
skills/fs-sessions/                   # agent skill (npx skills add)
  SKILL.md                            # skill definition
  scripts/
    export-session                    # legacy Python hook compatibility entry point
    fs-sessions                       # policy, hook, and sharing CLI
    export-session.sh                 # legacy Bash hook
    fs-sessions.sh                    # legacy Bash CLI
  references/                         # skill command references
skills/agentsview/                    # factual local AgentsView retrieval skill
  SKILL.md                            # router and shared guardrails
  references/                         # status, find, inspect, search, report
  scripts/preflight.py                # read-only CLI capability check
```

## Prerequisites

- Python 3.10+, `git`, and `boto3`
- `podman` (for AgentsView)
- `gh` (for fetching fullsend runs)

## Development

```bash
uv sync
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
```
