# view

Start AgentsView to browse shared sessions.

## Procedure

```bash
make sessions
```

For LAN access:
```bash
AGENTSVIEW_HOST=deimos.local make sessions
```

To stop:
```bash
make down
```

Sessions appear grouped by `<user>_<project>` in the AgentsView sidebar. The metadata line prepended by `export-session.sh` provides the session title and project grouping.
