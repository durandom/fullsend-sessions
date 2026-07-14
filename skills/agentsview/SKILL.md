---
name: agentsview
description: >-
  Retrieves factual information from local AgentsView session archives. Use
  when asked to find, list, or read recorded coding-agent sessions, inspect
  transcripts or tool calls, recover prior decisions, report AgentsView health,
  usage, activity, or stats, or check whether local AgentsView is available.
  Also use when the user asks what happened in a past agent session. This skill
  retrieves evidence; it does not evaluate session quality or recommend process
  improvements.
compatibility: Requires a local agentsview CLI with the session command group.
---

<cli_setup>

Resolve this skill's directory from the loaded `SKILL.md`, then run:

```bash
python scripts/preflight.py --json
```

Consume the complete JSON output. Do not pipe it through `head`, `tail`, or
`grep`. If `available` or `working` is false, report the supplied remediation
and stop. The preflight deliberately does not inspect or start the daemon;
normal read commands may start it as part of AgentsView's standard transport
behavior.

</cli_setup>

<essential_principles>

<principle name="evidence_not_analysis">
Retrieve and summarize what AgentsView records. Do not judge whether a session
was good, efficient, or successful, and do not recommend prompt, skill, or
workflow changes. Those conclusions belong to a later session-analysis skill.
</principle>

<principle name="heuristics_are_labels">
Report health scores, outcomes, confidence, and penalties as AgentsView-derived
heuristics. Attribute them explicitly to AgentsView and do not convert them into
ground truth about delivery success.
</principle>

<principle name="read_only_default">
Use read commands only. Do not run `prune`, `import`, `update`, PostgreSQL or
DuckDB writes, secret reveal, or other administrative commands. Ask before an
explicit `agentsview sync`; use `--full` only when the user specifically agrees
to a full resync.
</principle>

<principle name="structured_queries">
Request `--json` for machine-readable commands and synthesize from the parsed
fields. JSON prevents terminal formatting and truncation from becoming evidence.
</principle>

<principle name="traceable_evidence">
Cite session IDs for session-level facts. Cite message ordinals, or the search
result's ordinal range plus anchor, for transcript claims. Treat search snippets
as leads and inspect their surrounding message window before relying on them.
</principle>

<principle name="data_minimization">
Load only the messages needed to answer the question. AgentsView transcripts can
contain sensitive source, prompts, and tool output; never use `--reveal`, and do
not reproduce unrelated transcript content.
</principle>

</essential_principles>

<intake>

## What would you like to retrieve?

1. **Status** — check the local CLI, daemon state, and available projects
2. **Find sessions** — list and filter sessions by metadata or signals
3. **Inspect a session** — read metadata, messages, tool calls, health, or usage
4. **Search history** — find past decisions, instructions, errors, or examples
5. **Report a window** — retrieve factual stats, activity, cost, or token totals

If the user's request already identifies one of these intents, route directly
without repeating the menu. Otherwise ask them to choose and wait.

</intake>

<routing>

| Response or intent | Workflow |
|---|---|
| 1, "status", "is AgentsView running", "projects" | `references/status.md` |
| 2, "find", "list", "recent sessions", "filter sessions" | `references/find-sessions.md` |
| 3, "inspect", "read session", "transcript", "tool calls", session ID | `references/inspect-session.md` |
| 4, "search", "history", "have we done this", "why did we" | `references/search-history.md` |
| 5, "stats", "activity", "usage", "cost", "tokens", date range | `references/report-window.md` |

</routing>

<reference_index>

| Reference | Load when... |
|---|---|
| `references/status.md` | Checking CLI/daemon readiness or discovering projects |
| `references/find-sessions.md` | Selecting sessions from metadata, dates, or stored signals |
| `references/inspect-session.md` | Reading one known session in detail |
| `references/search-history.md` | Searching content across multiple sessions |
| `references/report-window.md` | Retrieving aggregate facts for a date window |

Load only the routed reference. Each workflow is self-contained after the
preflight and the principles above.

</reference_index>

<output_contract>

Default to a concise human-readable answer:

- state the applied scope or filters;
- report only facts needed for the request;
- label stored health/outcome fields as AgentsView heuristics;
- cite session evidence as `<session-id>#<ordinal>` or
  `<session-id>#<start>-<end> @<anchor>`;
- list gaps when AgentsView lacks the requested data.

Show raw JSON or the full command transcript only when the user asks for it.

</output_contract>

<success_criteria>

- The answer came from current local AgentsView CLI output, not memory.
- Every transcript claim has a session ID and ordinal evidence.
- Heuristic fields are attributed to AgentsView and not independently judged.
- No explicit sync or administrative mutation ran without approval.
- Missing or unsupported data is stated rather than inferred.

</success_criteria>
