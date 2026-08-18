---
name: fs-sessions
description: |
  Manage and share Claude Code, Cursor, and Fullsend transcripts through an S3-only, policy-controlled global hook and AgentsView. Use when asked to configure an S3 session bucket or credentials, install or migrate session sharing, whitelist or blacklist repositories, diagnose missing uploads, share or list sessions, import Fullsend GitHub Actions artifacts, discover AgentsView S3 roots, or start the team transcript viewer. Also use for fs-sessions, session export, transcript privacy, SessionEnd hooks, or Cursor sessionEnd hooks.
---

# fs-sessions

Share Claude Code and Cursor transcripts to S3 through a global, fail-closed repository policy.

<cli_setup>

Resolve the CLI relative to this file and use it for every deterministic operation:

```bash
FS="<skill-directory>/scripts/fs-sessions"
"$FS" --help
```

Consume complete command output. Do not reimplement JSON or Claude settings edits manually.

</cli_setup>

<essential_principles>

- **Global policy grants access** — only `~/.config/rhdh-skill/config.json` may allow export. A repository's `.rhdh/config.json` may set `sessions.enabled: false`, but cannot opt itself in; this prevents checked-out code from authorizing transcript upload.
- **Fail closed** — malformed/missing config, non-Git directories, unmatched repositories under `default: deny`, and export errors all skip silently in the SessionEnd hook.
- **Rules are ordered** — the last matching `allow` or `deny` rule wins. This supports whitelist, blacklist, and narrow exceptions with one explainable model.
- **One global hook per editor** — Claude Code uses `~/.claude/settings.json` (`hook install`). Cursor uses `~/.cursor/hooks.json` (`cursor-hook install`). Install Cursor only when the user explicitly asks after base S3 setup. After verifying each hook, remove legacy project-local `export-session.sh` hooks so a session cannot be exported twice.
- **S3 is the only transcript backend** — setup stores only non-secret bucket metadata in the global config. Git remains only for repository-origin policy discovery and GitHub artifact retrieval.
- **Credentials stay outside skill config** — use the standard boto3 environment/profile chain because secrets copied into config or conversation context are easy to leak.
- **Export the complete session family** — preserve the main transcript plus nested subagents, tool results, and regular companion files. Claude lands in `<machine>/raw/claude/<project>/...`; Cursor in `<machine>/raw/cursor/<project>/...`. Project is the repository and machine is the producing user or Fullsend agent such as `fs-code`.
- **Treat transcripts as append-only source records** — the exporter may refresh an object when its source grows, but do not manually alter shared transcript content.

</essential_principles>

<intake>

## What would you like to do?

1. **Setup or migrate** — configure S3, credentials, safe policy, and editor hook(s)
2. **Policy** — allow, deny, list rules, or explain a repository decision
3. **Hook** — install, inspect, or uninstall the global Claude SessionEnd hook
4. **Cursor hook** — install, inspect, or uninstall the global Cursor sessionEnd hook
5. **Status** — inspect configuration, hooks, policy, and stored sessions
6. **Share/list** — explicitly export or list local sessions
7. **S3** — validate access or discover AgentsView roots
8. **View** — start or stop AgentsView
9. **Fullsend** — import GitHub Actions artifacts into S3

If the user already stated an operation, route directly without repeating this menu. Otherwise wait for their selection.

</intake>

<routing>

| Response | Reference |
|----------|-----------|
| 1, "setup", "migrate", "global install" | `references/setup.md` + `references/s3.md` |
| 2, "policy", "allow", "deny", "whitelist", "blacklist" | `references/policy.md` |
| 3, "hook", "SessionEnd", "install hook" | `references/hook.md` |
| 4, "cursor", "cursor hook", "cursor-hook" | `references/cursor-hook.md` |
| 5, "status", "configured?", "why not exporting?" | `references/status.md` |
| 6, "share", "export", "list sessions" | `references/share.md` |
| 7, "S3", "bucket", "credentials", "roots" | `references/s3.md` |
| 8, "view", "AgentsView", "browse sessions" | `references/view.md` + `references/s3.md` |
| 9, "Fullsend", "GitHub artifact", "fs-code", "fs-review" | `references/fullsend.md` + `references/s3.md` |

</routing>

<reference_index>

| Reference | Load when | Path |
|-----------|-----------|------|
| setup | First installation or legacy-hook migration | `references/setup.md` |
| S3 | Credential gates, access checks, AgentsView roots | `references/s3.md` |
| policy | Editing or explaining repository rules | `references/policy.md` |
| hook | Claude hook-only lifecycle work | `references/hook.md` |
| cursor-hook | Cursor hook-only lifecycle work | `references/cursor-hook.md` |
| status | Diagnosing the current state | `references/status.md` |
| share | Explicit manual export/list | `references/share.md` |
| view | AgentsView lifecycle | `references/view.md` |
| Fullsend | On-demand GitHub artifact import | `references/fullsend.md` |

</reference_index>

<success_criteria>

- Configuration uses only S3, preserves unrelated `rhdh-skill` keys, and stores no credentials.
- `s3 check` confirms bucket listing and `s3 roots` returns every uploaded machine.
- `policy check <repo>` reports the intended action and matching rule.
- Exactly one managed hook exists per installed editor; legacy local hooks are absent after migration.
- A denied repository produces no object; an allowed repository uploads its complete session family without unrelated files.
- Fullsend imports map repository to project and `fullsend-<agent>` to machine `fs-<agent>`, archive provenance, and write their completion manifest last.

</success_criteria>
