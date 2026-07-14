# AgentsView Status

Use this workflow to check host-CLI/container readiness and discover what data
is available. It does not install, update, or synchronize AgentsView.

## Workflow

1. Run the preflight from `SKILL.md`. Report the CLI version/path, container
   URL, endpoint source, remote session count, container CLI version, and
   aggregate capabilities.
2. Treat `server_working: true` as the container readiness check. Do not run
   `serve status`; that command describes a host-managed daemon, which this
   deployment intentionally does not use.
3. If `container_cli.capabilities.projects` is true, discover indexed projects
   through the `container_cli.command` returned by preflight:

   ```bash
   podman compose exec -T agentsview agentsview projects --json
   ```

   Use `docker compose` when it is the available compose frontend. This command
   reads the container-owned database; the host `projects` command has no
   upstream `--server` flag.

4. If the user asks whether data is current, report the container records as
   indexed state. Do not run an explicit sync silently.
5. If freshness cannot be established from the requested records, offer one
   explicit container sync. Run it only after approval. Add `--full` only if the
   user separately agrees to rebuild the full container index.

## Output

Report:

- CLI path and version
- container URL and connectivity
- project names and session counts
- any concrete readiness error
- whether no explicit sync was performed

Do not treat an empty project list as a broken installation. State that the
local archive currently exposes no projects.

## Errors

| Error | Action |
|---|---|
| CLI missing or version command fails | Return the preflight remediation and stop |
| Config/database compatibility error | Report the exact error; do not repair or resync automatically |
| Project query returns no rows | Report an empty local archive |
| Container unavailable but CLI works | Report the preflight error; do not fall back to a host database or daemon |
