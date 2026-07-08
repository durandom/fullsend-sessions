# view

Start AgentsView to browse shared sessions.

## Procedure

```bash
just sessions
```

This will:
1. Start the podman machine if not already running
2. Read `~/.config/fullsend/sessions.env` to find the sessions directory (`FULLSEND_SESSIONS_REPO`)
3. Start AgentsView with `--public-url` set to `$(hostname).local` for LAN access

To stop:
```bash
just down
```

Sessions appear grouped by `<user>_<project>` in the AgentsView sidebar. The metadata line prepended by `export-session.sh` provides the session title and project grouping.
