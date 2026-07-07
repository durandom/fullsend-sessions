---
name: sessions
description: |
  Manage shared Claude Code session transcripts — status, push, pull, view in AgentsView.
  Use when asked to share, export, push, or pull Claude Code sessions,
  configure session sharing, view shared team sessions, browse sessions,
  or start AgentsView for sessions.
---

# /sessions

Share and browse team Claude Code session transcripts via a shared git repo.

## Overview

Sessions are auto-exported on session end via a `SessionEnd` hook, committed locally to this repo, and pushed on demand. AgentsView serves them for browsing, searching, and analysis.

## Commands

| Command | Description |
|---------|-------------|
| `status` | Config check, session count, unpushed commits |
| `push` | Push local session commits to remote |
| `pull` | Pull team sessions from remote |
| `view` | Start AgentsView with shared sessions |
| `setup` | Guide for first-time configuration |

If no subcommand is given, show status.

## Routing

Parse the first word after `/sessions` as the subcommand.

| Command | Reference |
|---------|-----------|
| `status` | `references/status.md` |
| `push` | `references/sync.md` |
| `pull` | `references/sync.md` |
| `view` | `references/view.md` |
| `setup` | `references/setup.md` |
