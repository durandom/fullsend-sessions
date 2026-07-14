# Inspect One Session

Use this workflow for a known session ID or after selecting one candidate. It
retrieves facts without evaluating the session's quality.

## 1. Resolve Metadata and Signals

```bash
agentsview session get <session-id> --json
```

Capture the canonical ID, project, agent, machine, branch, working directory,
timestamps, message counts, relationship to parent sessions, and stored signal
fields. AgentsView accepts a bare UUID for many non-Claude sessions and retries
known agent prefixes automatically.

When present, report these explicitly as AgentsView heuristics:

- `health_score`, `health_grade`, `health_score_basis`, `health_penalties`
- `outcome`, `outcome_confidence`
- tool failures, retries, edit churn, and failure streaks
- compactions, mid-task compactions, and context pressure
- grouped `quality_signals`

Do not translate the grade or outcome into an independent conclusion.

## 2. Read Only the Needed Messages

For an opening or complete linear view:

```bash
agentsview session messages <session-id> \
  --from 0 --limit 50 --direction asc --role user,assistant --json
```

For the end of a session:

```bash
agentsview session messages <session-id> \
  --limit 20 --direction desc --role user,assistant --json
```

For evidence around a known ordinal:

```bash
agentsview session messages <session-id> \
  --around <ordinal> --before 8 --after 8 \
  --role user,assistant --json
```

Paginate a requested full transcript with `last_ordinal + 1`. An explicit
`--from 0` is meaningful; omitting `--from` in descending mode starts at the
newest page. Do not combine `--around` with `--from` or `--direction`.

## 3. Retrieve Tool or Usage Facts When Requested

```bash
agentsview session tool-calls <session-id> --json
agentsview session usage <session-id> --json
```

Tool-call rows expose ordinal, name, category, input JSON, inferred skill name,
subagent ID, and result length. They do not expose every tool result body or
status. If that missing content is essential, state the limitation and use a
targeted `session search` only when there is a concrete string or pattern to
search for.

`session usage` may exit with code 3 when the session has neither token nor cost
data. Treat that as unsupported/missing telemetry, not as zero usage.

## Output

Summarize only the requested dimensions. Cite message claims as
`<session-id>#<ordinal>`. If the inspected session is a child, fork, teammate,
or subagent session, state the relationship and parent session ID when present.
Do not dump the full transcript unless the user explicitly asks for it.
