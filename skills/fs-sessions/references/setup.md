# setup

Automated first-time setup for session sharing. Run each step, report results.

## Procedure

### 1. Check prerequisites

```bash
command -v python3 >/dev/null 2>&1 && echo "python3: ok" || echo "python3: MISSING"
command -v git >/dev/null 2>&1 && echo "git: ok" || echo "git: MISSING"
```

If missing, tell the user to install them and stop. Note: `jq` is no longer required — the Python scripts handle JSON natively.

### 2. Locate the sessions repo

Check if running inside the fullsend-sessions repo (look for `skills/fs-sessions/scripts/export-session`):

```bash
# Try cwd first, then common locations
for candidate in "." "$HOME/fullsend-sessions" "$HOME/src/fullsend-sessions"; do
  if [ -f "$candidate/skills/fs-sessions/scripts/export-session" ]; then
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

### 4. Install the SessionEnd hook (project-local)

Install the hook into the **current project's** `.claude/settings.json` so only this project auto-exports sessions.

```bash
SETTINGS_FILE=".claude/settings.json"
mkdir -p ".claude"
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
            "command": "bash -c '. ~/.config/fullsend/sessions.env 2>/dev/null && [ -n \"$FULLSEND_SESSIONS_REPO\" ] && [ -f \"$FULLSEND_SESSIONS_REPO/skills/fs-sessions/scripts/export-session\" ] && exec python3 \"$FULLSEND_SESSIONS_REPO/skills/fs-sessions/scripts/export-session\" || true'"
          }
        ]
      }
    ]
  }
}
```

Use `jq` to merge. If `hooks.SessionEnd` already exists, check if the fs-sessions hook is already present (search for `export-session` in the command string). If present, skip. If not, append to the array.

```bash
if jq -e '.hooks.SessionEnd[]?.hooks[]? | select(.command | contains("export-session"))' "$SETTINGS_FILE" >/dev/null 2>&1; then
  echo "Hook already installed in $SETTINGS_FILE"
else
  jq '. * {
    "hooks": {
      "SessionEnd": (((.hooks // {}).SessionEnd // []) + [{
        "matcher": "",
        "hooks": [{
          "type": "command",
          "command": "bash -c '"'"'. ~/.config/fullsend/sessions.env 2>/dev/null && [ -n \"$FULLSEND_SESSIONS_REPO\" ] && [ -f \"$FULLSEND_SESSIONS_REPO/skills/fs-sessions/scripts/export-session\" ] && exec python3 \"$FULLSEND_SESSIONS_REPO/skills/fs-sessions/scripts/export-session\" || true'"'"'"
        }]
      }])
    }
  }' "$SETTINGS_FILE" > "${SETTINGS_FILE}.tmp" && mv "${SETTINGS_FILE}.tmp" "$SETTINGS_FILE"
  echo "Hook installed into $SETTINGS_FILE"
fi
```

Show the user what changed. Remind them to commit `.claude/settings.json` so teammates get the hook too.

### 5. Verify

Report the setup state:

```bash
echo ""
echo "=== Setup complete ==="
echo "Config:  ~/.config/fullsend/sessions.env"
echo "Hook:    .claude/settings.json (SessionEnd)"
echo "Repo:    ${SESSIONS_REPO}"
echo ""
echo "Sessions from this project will be auto-exported and pushed on session end."
echo "Commit .claude/settings.json so teammates get the hook too."
echo "Run /fs-sessions status to verify after your next session."
```
