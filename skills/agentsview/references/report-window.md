# Report a Time Window

Use this workflow to retrieve aggregate facts. It reports stored measurements;
it does not assess productivity, effectiveness, or session quality.

## Pick the Smallest Matching Report

| User asks for | Command |
|---|---|
| workspace/session shape, tools, models, outcomes | `"$AGENTSVIEW_BIN" stats` |
| active/idle minutes, concurrency, per-session activity | `"$AGENTSVIEW_BIN" activity report` |
| daily tokens and cost | `"$AGENTSVIEW_BIN" usage daily` |
| one session's tokens and cost | `"$AGENTSVIEW_BIN" session usage <id>` |

## Workspace Stats

```bash
"$AGENTSVIEW_BIN" stats \
  --since 28d \
  --include-project example-project \
  --timezone Europe/Berlin \
  --json
```

Use repeated `--include-project` or `--exclude-project` flags for project scope.
Use `--agent` for an agent scope. `stats` has no machine filter.

Add `--include-git-outcomes` only when the user asks for commit, LOC, or changed
file totals. Add `--include-github-outcomes` only when the user asks for PR
totals; it invokes local `gh` authentication and implies git outcomes.

The `outcomes` and grade distribution are AgentsView heuristics. Git and GitHub
totals are derived correlations, not proof that a particular session produced a
specific change.

Read the effective scope from `window` and `filters`, session/message counts
from `totals`, and heuristic grades/outcomes from `outcomes`; these values are
not top-level scalar fields.

## Activity

```bash
"$AGENTSVIEW_BIN" activity report \
  --preset week \
  --date 2026-07-14 \
  --timezone Europe/Berlin \
  --project example-project \
  --json
```

Use `--preset day|week|month`, or `--preset custom --from <RFC3339> --to
<RFC3339>`. Filters exist for project, agent, and machine. The JSON timeline
contains active minutes, idle minutes, agent minutes, peak concurrency, tokens,
cost, and breakdowns. These are activity estimates, not human time tracking.
Read the effective interval from `range_start`, `range_end`, and `effective_end`,
measurements from `totals`, and concurrency from `peak`. If `partial` is true,
label the report as an in-progress window.

## Daily Usage

```bash
"$AGENTSVIEW_BIN" usage daily \
  --since 28d \
  --timezone Europe/Berlin \
  --json
```

`usage daily` supports agent filtering but not project or machine filtering. If
the user needs project-scoped cost, use the activity report's project filter or
sum the relevant per-session usage rows; state which method was used. Missing
token telemetry is not zero consumption.

Read aggregate values from `totals`, counts from `sessionCounts`, and rows from
`daily`. Project identity metadata can be large; omit the top-level `projects`
object unless identity resolution is relevant to the request.

## Output

- State the exact date range, timezone, and filters.
- Name the report source (`stats`, `activity`, or `usage`).
- Preserve units and distinguish measured zero from unavailable telemetry.
- Attribute health/outcome figures to AgentsView's heuristic classifier.
- Do not rank people, projects, or agents by productivity.
