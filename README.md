# fullsend-sessions

Share and browse Claude Code session transcripts across your team.

Allowed sessions are auto-exported when a Claude Code session ends, committed to this shared Git repository, and pushed to the remote. [AgentsView](https://github.com/kenn-io/agentsview) serves them for browsing, searching, and analysis.

## Quick start

```bash
# 1. Clone (anywhere you like)
git clone git@github.com:durandom/fullsend-sessions.git

# 2. Install the session-sharing skill globally
npx skills add -g git@github.com:durandom/fullsend-sessions.git \
  --skill fs-sessions --agent claude-code codex -y

# 3. Resolve the installed CLI
FS_SESSIONS="$HOME/.agents/skills/fs-sessions/scripts/fs-sessions"

# 4. Configure this clone and a default-deny policy
"$FS_SESSIONS" config init --repo "$PWD" --default deny
"$FS_SESSIONS" policy allow --origin 'github.com/example-org/*'

# 5. Verify one repository, then install the global Claude Code hook
"$FS_SESSIONS" policy check /absolute/path/to/an/allowed-repository
"$FS_SESSIONS" hook install
"$FS_SESSIONS" status
```

Configuration lives in `~/.config/rhdh-skill/config.json` so it can later move into the RHDH skill without another migration. The hook lives once in `~/.claude/settings.json`; repositories cannot install their own permission to export transcripts.

## How it works

```
Session ends → global SessionEnd hook → repository policy check
  → copies transcript to sessions/<user>_<project>/<session-id>.jsonl
  → git commit
  → git pull --rebase && git push (best-effort, silent on failure)
```

Sessions are stored as JSONL files matching the AgentsView Claude discovery layout. Each file gets a metadata header line with project name, user, and timestamp.

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
just sessions                         # start AgentsView with shared sessions
just down                             # stop AgentsView
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
| `/fs-sessions setup` | Configure the repository, policy, and global hook |
| `/fs-sessions policy` | Allow, deny, list, or explain repository rules |
| `/fs-sessions hook` | Install, inspect, migrate, or remove the global hook |
| `/fs-sessions status` | Check config, policy, sessions, and hook state |
| `/fs-sessions share` | List or explicitly export a local session |
| `/fs-sessions push` | Push local session commits |
| `/fs-sessions pull` | Pull team sessions |
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
sessions/                             # shared session transcripts
  <user>_<project>/
    <session-id>.jsonl
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

- Python 3.10+ and `git`
- `podman` (for AgentsView)
- `gh` (for fetching fullsend runs)

## Development

```bash
uv sync
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
```
