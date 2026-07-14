# Find Sessions

Use this workflow when the user wants candidate sessions selected by metadata,
time, stored health signals, or recent activity. Use `search-history.md` instead
when selection depends on transcript content.

## Start Narrow

Translate stated constraints into `session list` flags. Resolve user-facing
repository names against the container projects command from `status.md` before
applying a `--project` filter; indexed project names may normalize punctuation
such as hyphens to underscores. Useful flags
include:

| Intent | Flag |
|---|---|
| recent activity | `--since 14d` |
| exact start date | `--date YYYY-MM-DD` |
| date window | `--date-from ... --date-to ...` |
| project or agent | `--project ...`, `--agent ...` |
| meaningful interaction | `--min-user-messages 2` |
| stored outcome or grade | `--outcome ...`, `--health-grade ...` |
| tool-failure threshold | `--min-tool-failures N` |
| children or automation | `--include-children`, `--include-automated` |

`--since 3m` means three calendar months, not three minutes. One-shot,
automated, and child sessions are excluded unless their include flags are set.

Example:

```bash
"$AGENTSVIEW_BIN" session list \
  "${AGENTSVIEW_SERVER_ARGS[@]}" \
  --since 14d \
  --project example-project \
  --min-user-messages 2 \
  --sort recent \
  --json
```

## Pagination and Sorting

1. Start with `--limit 20` unless the user requests a broader inventory.
2. Follow `next_cursor` only when more results are needed. Pass it back with
   `--cursor` and do not combine it with changed filters.
3. Use a relevant sort rather than downloading everything. Available sort keys
   include `recent`, `started`, `messages`, `user-messages`, `output-tokens`,
   `peak-context`, `failures`, `retries`, `edit-churn`, `compactions`,
   `context-pressure`, `health`, `secrets`, and `id`.
4. If the user names a branch, inspect `git_branch` in the returned JSON and
   filter the candidate rows locally; `session list` has no plain branch flag.

## Result Handling

- Present the smallest useful candidate set with full session IDs.
- Include project, agent, time, message count, branch, and title when present.
- Label health grade and outcome as AgentsView heuristics when shown.
- Mark `termination_status: tool_call_pending`, pending signals, or a missing
  end time as a live/non-final snapshot.
- Do not infer why a session matched from its title alone.
- When one candidate clearly matches, continue with `inspect-session.md` only if
  the user also asked to read its contents.

## No Results

Relax one constraint at a time: widen the date window, remove project aliases,
then include one-shot or automated sessions only if they are relevant. State
which constraint was relaxed. Do not run a full sync as a search fallback.
