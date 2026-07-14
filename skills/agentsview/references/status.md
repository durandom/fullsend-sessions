# AgentsView Status

Use this workflow to check local readiness and discover what data is available.
It does not install, update, or synchronize AgentsView.

## Workflow

1. Run the preflight from `SKILL.md`. Report the CLI version and path.
2. If the user asked about the daemon, inspect it without starting it:

   ```bash
   "$AGENTSVIEW_BIN" serve status
   ```

   A stopped daemon is not an error because a normal read may start it.
3. Discover indexed projects:

   ```bash
   "$AGENTSVIEW_BIN" projects --json
   ```

4. If the user asks whether data is current, explain that read commands can use
   AgentsView's normal local refresh behavior. Do not run an explicit sync
   silently.
5. If freshness cannot be established from the requested records, offer one
   explicit `"$AGENTSVIEW_BIN" sync`. Run it only after approval. Add `--full` only if
   the user separately agrees to rebuild the full local index.

## Output

Report:

- CLI path and version
- daemon status, when available
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
| Daemon unavailable but CLI works | Try the requested read once; report its resulting error if it fails |
