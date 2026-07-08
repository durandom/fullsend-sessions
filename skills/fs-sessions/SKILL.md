---
name: fs-sessions
description: |
  Manage shared Claude Code session transcripts — setup, status, push, pull, view in AgentsView.
  Use when asked to share, export, push, or pull Claude Code sessions,
  configure session sharing, view shared team sessions, browse sessions,
  set up session hooks, or start AgentsView for sessions.
---

# /fs-sessions

Share and browse team Claude Code session transcripts via a shared git repo.

## Overview

Sessions are auto-exported and pushed on session end via a `SessionEnd` hook in the project's `.claude/settings.json`. AgentsView serves them for browsing, searching, and analysis.

### How it works

1. **SessionEnd hook** fires when any Claude Code session ends
2. `export-session.sh` copies the transcript to `sessions/<user>_<project>/`
3. Commits locally, then pulls and pushes to the shared remote
4. Teammates pull to see each other's sessions

## Commands

| Command | Description |
|---------|-------------|
| `setup` | Automated first-time setup: config, hook, verify |
| `status` | Config check, session count, unpushed commits |
| `push` | Push local session commits to remote |
| `pull` | Pull team sessions from remote |
| `view` | Start AgentsView with shared sessions |

If no subcommand is given, show status.

## Routing

Parse the first word after `/fs-sessions` as the subcommand.

| Command | Reference |
|---------|-----------|
| `setup` | `references/setup.md` |
| `status` | `references/status.md` |
| `push` | `references/sync.md` |
| `pull` | `references/sync.md` |
| `view` | `references/view.md` |
