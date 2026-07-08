# fullsend-sessions

Shared repo for Claude Code session transcripts and fullsend agent run data.

## Project structure

- `sessions/` — shared session transcripts (`<user>_<project>/<session-id>.jsonl`)
- `skills/fs-sessions/` — agent skill for session management, installable via `npx skills add`
  - `scripts/export-session.sh` — SessionEnd hook (copies, commits, pushes)
  - `scripts/fs-sessions.sh` — interactive CLI for manual session sharing
- `scripts/` — fullsend run tooling (fetch from GH Actions, import local runs)
- `justfile` — task runner (`just --list` for available commands)

## Key commands

```bash
just sessions          # start AgentsView for shared sessions
just down              # stop AgentsView
just fetch             # download fullsend runs from GitHub Actions
just up                # fetch + start AgentsView
```

## Session flow

SessionEnd hook → `export-session.sh` → copies transcript → commits → pulls → pushes (all best-effort, silent on failure).

Config: `~/.config/fullsend/sessions.env` defines `FULLSEND_SESSIONS_REPO`.
Hook: installed in user-global `~/.claude/settings.json`.

## Conventions

- Session files are append-only — never modify existing transcripts
- Commit messages: `feat: add session <user>/<project>/<session-id>`
- No merge commits — always rebase (`git pull --rebase`)
