# Global Cursor sessionEnd hook

Install only when the user uses Cursor and asks for Cursor session upload.
The shared S3 config and repository policy are identical to Claude Code; only
the hook target and S3 prefix (`raw/cursor/`) differ.

```bash
"$FS" cursor-hook install
"$FS" cursor-hook status
"$FS" cursor-hook uninstall
```

The installer writes `~/.cursor/hooks.json` and preserves unrelated hook
entries. It replaces earlier managed commands containing `export-session` or
`fs-sessions cursor-hook run`.

The internal `cursor-hook run` command reads Cursor's sessionEnd JSON from
stdin. Do not invoke it without a test event. It exits successfully and
silently for policy denials, malformed events, missing credentials, or upload
failures so Cursor shutdown cannot be blocked.

Cursor sessionEnd is fire-and-forget: unlike Claude's SessionEnd hook, it does
not emit a user-visible success message.

## IDE vs Cursor CLI (`agent`)

Both read the same hook configuration:

- user-wide: `~/.cursor/hooks.json`
- project-wide: `.cursor/hooks.json` in the repository

Today they are not equivalent:

| Surface | sessionEnd at chat close | Practical note |
| --- | --- | --- |
| Cursor IDE | yes | Fires when a Composer/Agent chat is closed or deleted |
| Cursor CLI `agent --print` | yes | Fires when the one-shot run completes (`reason: completed`) |
| Cursor CLI `agent` interactive | varies | `/exit` should fire `sessionEnd`, but timing can race transcript flush |

If automatic CLI export is required before Cursor ships full parity, a later
`stop` hook can upload after each agent turn. That is a separate, more chatty
mode and is intentionally not the default.

Cloud agents do not fire `sessionEnd`. User-level `~/.cursor/hooks.json` is
also invisible to cloud runs; only project `.cursor/hooks.json` applies there.

## Skill installation flow

1. Run the base S3 setup from `references/setup.md` steps 1–4.
2. Install the Claude hook only when the user uses Claude Code.
3. When the user asks to enable Cursor upload, run `cursor-hook install` and
   `cursor-hook status`.
4. Verify from the IDE by closing an allowed Composer chat, then inspect S3
   under `<machine>/raw/cursor/<project>/`.

Do not install the Cursor hook during first-time setup unless the user
explicitly requests Cursor support.
