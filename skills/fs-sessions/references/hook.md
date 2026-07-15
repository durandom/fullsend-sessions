# Global SessionEnd hook

Manage the hook only through the CLI so JSON settings and unrelated hooks are preserved.

```bash
"$FS" hook install
"$FS" hook status
"$FS" hook uninstall
```

The global settings file defaults to `~/.claude/settings.json`. Use `--settings PATH` only to inspect/migrate a project-local settings file or for testing.

`hook install` is idempotent: it replaces any managed Python hook or legacy command containing `export-session`, then writes one command pointing to this installed skill's script.

The installer gives the command a 30-second timeout. Claude Code otherwise allows `SessionEnd` hooks only 1.5 seconds by default, which is too short for a complete session-family copy and S3 upload.

The internal `hook run` command reads Claude's SessionEnd JSON from stdin. Do not invoke it without a test event. It intentionally exits successfully and silently for policy denials, malformed events, missing credentials, or upload failures so Claude shutdown cannot be blocked.

After an upload succeeds, the hook emits a Claude Code `systemMessage` with the project, session ID, S3 destination, and file count. Denied, unchanged, or failed uploads emit nothing.

For migration, verify the global hook and policy before uninstalling the local hook. Otherwise a gap between removal and installation can drop session exports.

## Notifications and interaction

`SessionEnd` emits the user-visible success message described above. It could also trigger an operating-system notification as a command side effect, but it has no decision control and cannot hold an interactive conversation because the session is already terminating. Keep the exporter non-interactive so logout cannot stall.

Use Claude Code's `Notification` event for alerts when Claude needs input or permission. Use `Stop` for completion checks after an assistant response; `Stop` can block the stop and give Claude another instruction, but it is distinct from terminal session termination.
