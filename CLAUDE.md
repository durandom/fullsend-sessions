# fullsend-sessions

S3-only tooling for Claude Code transcripts and Fullsend agent run data.

## Project structure

- `skills/fs-sessions/` — agent skill for session management, installable via `npx skills add`
  - `scripts/fs-sessions` — Python CLI for S3 sharing and Fullsend imports
- `skills/agentsview/` — read-only AgentsView setup and retrieval skill
- `justfile` — task runner (`just --list` for available commands)

## Key commands

```bash
just up                # start S3-backed AgentsView
just down              # stop AgentsView
just fullsend-dry-run  # preview recent GitHub artifact imports
just fullsend          # upload recent Fullsend sessions to S3
```

## Session flow

SessionEnd hook → policy check → temporary complete-family export → S3 upload.

Config: `~/.config/rhdh-skill/config.json` contains non-secret S3 metadata and policy.
Hook: installed globally in `~/.claude/settings.json`.

## Conventions

- S3 is the only transcript backend.
- Machine means the producing user or Fullsend agent; project means repository.
- Runtime secrets and AgentsView `config.toml` stay outside Git.
- Source transcripts are append-only; derived Fullsend transcripts are reproducible from archived artifacts.
