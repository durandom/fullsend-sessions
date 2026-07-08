# setup

Automated first-time setup for session sharing. Run each step, report results.

## Procedure

### 1. Check prerequisites

```bash
command -v jq >/dev/null 2>&1 && echo "jq: ok" || echo "jq: MISSING"
command -v git >/dev/null 2>&1 && echo "git: ok" || echo "git: MISSING"
```

If missing, tell the user to install them and stop.

### 2. Locate the sessions repo

Check if running inside the fullsend-sessions repo (look for `skills/fs-sessions/scripts/export-session.sh`):

```bash
# Try cwd first, then common locations
for candidate in "." "$HOME/fullsend-sessions" "$HOME/src/fullsend-sessions"; do
  if [ -f "$candidate/skills/fs-sessions/scripts/export-session.sh" ]; then
    echo "Found: $(cd "$candidate" && pwd)"
    break
  fi
done
```

If not found, ask the user where they cloned the repo, or tell them to clone it first:
```bash
git clone git@github.com:durandom/fullsend-sessions.git
```

Store the resolved absolute path as `SESSIONS_REPO` for the remaining steps.

### 3. Create the config file

```bash
mkdir -p ~/.config/fullsend
cat > ~/.config/fullsend/sessions.env << EOF
FULLSEND_SESSIONS_REPO=${SESSIONS_REPO}
EOF
chmod 600 ~/.config/fullsend/sessions.env
```

### 4. Install the SessionEnd hook (user-global)

Read `~/.claude/settings.json`, merge the SessionEnd hook, write it back. The hook must be in the **user-global** settings so it fires for all projects.

```bash
SETTINGS_FILE="$HOME/.claude/settings.json"
mkdir -p "$HOME/.claude"
```

If `$SETTINGS_FILE` exists, read it. Otherwise start with `{}`.

The hook entry to merge:
```json
{
  "hooks": {
    "SessionEnd": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "bash -c '. ~/.config/fullsend/sessions.env 2>/dev/null && [ -n \"$FULLSEND_SESSIONS_REPO\" ] && [ -f \"$FULLSEND_SESSIONS_REPO/skills/fs-sessions/scripts/export-session.sh\" ] && exec bash \"$FULLSEND_SESSIONS_REPO/skills/fs-sessions/scripts/export-session.sh\" || true'"
          }
        ]
      }
    ]
  }
}
```

Use `jq` to merge. If `hooks.SessionEnd` already exists, check if the fs-sessions hook is already present (search for `export-session.sh` in the command string). If present, skip. If not, append to the array.

```bash
# Check if already installed
if jq -e '.hooks.SessionEnd[]?.hooks[]? | select(.command | contains("export-session.sh"))' "$SETTINGS_FILE" >/dev/null 2>&1; then
  echo "Hook already installed."
else
  HOOK='{"matcher":"","hooks":[{"type":"command","command":"bash -c '\'''. ~/.config/fullsend/sessions.env 2>/dev/null && [ -n \"$FULLSEND_SESSIONS_REPO\" ] && [ -f \"$FULLSEND_SESSIONS_REPO/skills/fs-sessions/scripts/export-session.sh\" ] && exec bash \"$FULLSEND_SESSIONS_REPO/skills/fs-sessions/scripts/export-session.sh\" || true'\''\""}]}'

  jq --argjson hook "$HOOK" '
    .hooks //= {} |
    .hooks.SessionEnd //= [] |
    .hooks.SessionEnd += [$hook]
  ' "$SETTINGS_FILE" > "${SETTINGS_FILE}.tmp" && mv "${SETTINGS_FILE}.tmp" "$SETTINGS_FILE"
  echo "Hook installed into $SETTINGS_FILE"
fi
```

**Important**: The jq merge above is tricky to get right with shell escaping. Prefer reading the current file, constructing the new JSON programmatically, and writing it back. Show the user the diff of what changed.

### 5. Verify

Report the setup state:

```bash
echo ""
echo "=== Setup complete ==="
echo "Config:  ~/.config/fullsend/sessions.env"
echo "Hook:    ~/.claude/settings.json (SessionEnd)"
echo "Repo:    ${SESSIONS_REPO}"
echo ""
echo "Sessions will be auto-exported and pushed when you end a Claude Code session."
echo "Run /fs-sessions status to verify after your next session."
```
