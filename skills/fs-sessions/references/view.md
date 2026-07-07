# view

Start AgentsView to browse shared sessions.

## Procedure

```bash
just sessions
```

For LAN access:
```bash
AGENTSVIEW_HOST=deimos.local just sessions
```

To stop:
```bash
just down
```

Sessions appear grouped by `<user>_<project>` in the AgentsView sidebar. The metadata line prepended by `export-session.sh` provides the session title and project grouping.
