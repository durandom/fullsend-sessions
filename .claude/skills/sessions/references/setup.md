# setup

First-time setup for session sharing.

## Procedure

### 1. Clone this repo (if not already)

```bash
git clone git@github.com:durandom/fullsend-sessions.git ~/src/rhdh/fullsend-sessions
```

### 2. Create the config file

```bash
mkdir -p ~/.config/fullsend
echo 'FULLSEND_SESSIONS_REPO=/Users/$(whoami)/src/rhdh/fullsend-sessions' > ~/.config/fullsend/sessions.env
chmod 600 ~/.config/fullsend/sessions.env
```

### 3. Enable the SessionEnd hook in consuming repos

Each project where you want sessions exported needs a `.claude/settings.json` with the hook. Copy the one from this repo:

```bash
# In the consuming repo (e.g., rhdh-fullsend):
mkdir -p .claude
cp ~/src/rhdh/fullsend-sessions/.claude/settings.json .claude/settings.json
```

Or add manually — the hook command sources `sessions.env` to find the export script:

```json
{
  "hooks": {
    "SessionEnd": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "bash -c '. ~/.config/fullsend/sessions.env 2>/dev/null && [ -n \"$FULLSEND_SESSIONS_REPO\" ] && [ -f \"$FULLSEND_SESSIONS_REPO/scripts/export-session.sh\" ] && exec bash \"$FULLSEND_SESSIONS_REPO/scripts/export-session.sh\" || true'"
          }
        ]
      }
    ]
  }
}
```

The hook exits silently if sessions aren't configured — safe to commit to shared repos.

### 4. Verify

End a Claude Code session in a consuming repo and check:

```bash
cd ~/src/rhdh/fullsend-sessions
git log --oneline -3
ls sessions/
```
