# fullsend-sessions

Share and browse Claude Code session transcripts across your team.

Sessions are auto-exported when a Claude Code session ends, committed to this shared git repo, and pushed to the remote. [AgentsView](https://github.com/kenn-io/agentsview) serves them for browsing, searching, and analysis.

## Quick start

```bash
# 1. Clone (anywhere you like)
git clone git@github.com:durandom/fullsend-sessions.git

# 2. Install the skill
npx skills add git@github.com:durandom/fullsend-sessions.git --skill fs-sessions

# 3. Run setup (in any Claude Code session)
/fs-sessions setup
```

Setup creates `~/.config/fullsend/sessions.env` and installs a `SessionEnd` hook into the project's `.claude/settings.json`. After that, sessions from that project are auto-exported and pushed on session end.

## How it works

```
Session ends → SessionEnd hook fires → export-session.sh
  → copies transcript to sessions/<user>_<project>/<session-id>.jsonl
  → git commit
  → git pull --rebase && git push (best-effort, silent on failure)
```

Sessions are stored as JSONL files matching the AgentsView Claude discovery layout. Each file gets a metadata header line with project name, user, and timestamp.

## CLI

Share sessions interactively without the hook:

```bash
./skills/fs-sessions/scripts/fs-sessions.sh              # pick from recent sessions
./skills/fs-sessions/scripts/fs-sessions.sh --last       # share the most recent session
./skills/fs-sessions/scripts/fs-sessions.sh --list       # list recent sessions
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
| `/fs-sessions setup` | Automated first-time setup |
| `/fs-sessions status` | Config check, session count, hook state |
| `/fs-sessions push` | Push local commits to remote |
| `/fs-sessions pull` | Pull team sessions from remote |
| `/fs-sessions view` | Start AgentsView |

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
    export-session.sh                 # SessionEnd hook script
    fs-sessions.sh                    # interactive CLI
  references/                         # skill command references
```

## Prerequisites

- `jq`, `git`
- `podman` (for AgentsView)
- `gh` (for fetching fullsend runs)
