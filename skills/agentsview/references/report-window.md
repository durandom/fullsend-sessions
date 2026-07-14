# Report a Time Window

Use this workflow to retrieve aggregate facts. It reports stored measurements;
it does not assess productivity, effectiveness, or session quality.

## Pick the Smallest Matching Report

| User asks for | Command |
|---|---|
| workspace/session shape, tools, models, outcomes | `agentsview stats` |
| active/idle minutes, concurrency, per-session activity | `agentsview activity report` |
| daily tokens and cost | `agentsview usage daily` |
| one session's tokens and cost | `agentsview session usage <id>` |

## Workspace Stats

```bash
agentsview stats \
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

## Activity

```bash
agentsview activity report \
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

## Daily Usage

```bash
agentsview usage daily \
  --since 28d \
  --timezone Europe/Berlin \
  --json
```

`usage daily` supports agent filtering but not project or machine filtering. If
the user needs project-scoped cost, use the activity report's project filter or
sum the relevant per-session usage rows; state which method was used. Missing
token telemetry is not zero consumption.

## Output

- State the exact date range, timezone, and filters.
- Name the report source (`stats`, `activity`, or `usage`).
- Preserve units and distinguish measured zero from unavailable telemetry.
- Attribute health/outcome figures to AgentsView's heuristic classifier.
- Do not rank people, projects, or agents by productivity.
