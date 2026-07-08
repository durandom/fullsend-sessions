# status

Show the current state of the sessions repo.

## Procedure

Check and report each item:

1. **Config**: Is `~/.config/fullsend/sessions.env` present with `FULLSEND_SESSIONS_REPO` set?
   ```bash
   . ~/.config/fullsend/sessions.env 2>/dev/null
   echo "Sessions repo: ${FULLSEND_SESSIONS_REPO:-not set}"
   ```

2. **Session count**: How many transcripts are stored?
   ```bash
   find sessions/ -name '*.jsonl' 2>/dev/null | wc -l
   ```

3. **Project breakdown**: Which projects have sessions?
   ```bash
   for d in sessions/*/; do
     [ -d "$d" ] && echo "$(basename "$d"): $(find "$d" -name '*.jsonl' | wc -l) sessions"
   done
   ```

4. **Unpushed commits**: Any local commits not yet pushed?
   ```bash
   git log --oneline '@{upstream}..HEAD' 2>/dev/null
   ```

5. **Last sync**: When was the last push/pull?
   ```bash
   git log --oneline -1 '@{upstream}' 2>/dev/null
   ```

6. **Hook installed**: Is the SessionEnd hook present in this project's `.claude/settings.json`?
   ```bash
   jq -e '.hooks.SessionEnd[]?.hooks[]? | select(.command | contains("export-session.sh"))' .claude/settings.json >/dev/null 2>&1 \
     && echo "Hook: installed" || echo "Hook: NOT installed"
   ```

If not configured, suggest running `/fs-sessions setup`.
