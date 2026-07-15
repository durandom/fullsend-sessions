---
name: agentsview
description: >-
  Sets up, starts, verifies, and queries a container-backed AgentsView session
  archive. Use when asked to start or stop a local S3-backed AgentsView service,
  verify its web UI, install or upgrade its host CLI, find or inspect recorded
  coding-agent sessions, search transcripts or tool calls, recover prior
  decisions, or report AgentsView health, usage, activity, or stats. Also use
  when the user invokes agentsview directly or wants to try the local container
  integration. Retrieval is evidence-only; it does not evaluate session quality
  or recommend process improvements. Requires Python 3; local service setup
  also requires Podman.
---

<cli_setup>

Resolve this skill's directory from the loaded `SKILL.md`, then run:

```bash
python scripts/preflight.py --json
```

Consume the complete JSON output. Do not pipe it through `head`, `tail`, or
`grep`. For setup, start, or installation intent, load `references/setup.md`
when `available` or `working` is false and use the supplied remediation as
diagnostic input. For every other intent, report that remediation and stop.

Record the returned absolute `binary` as `AGENTSVIEW_BIN`, `server_url` as
`AGENTSVIEW_SERVER_URL`, and an optional `server_token_file`. A successful
explicit or common path lookup does not imply that `agentsview` is on `PATH`.
The preflight honors matching environment overrides.

In each new shell invocation, assign the returned value before the command:

```bash
AGENTSVIEW_BIN='<absolute binary value from preflight>'
AGENTSVIEW_SERVER_URL='<container URL from preflight>'
export AGENTSVIEW_NO_DAEMON=1
AGENTSVIEW_SERVER_ARGS=(--server "$AGENTSVIEW_SERVER_URL")
"$AGENTSVIEW_BIN" session list "${AGENTSVIEW_SERVER_ARGS[@]}" --limit 1 --json
```

If `server_token_file` is present, append `--server-token-file <path>` to
`AGENTSVIEW_SERVER_ARGS` without reading the token into context. Host daemon
startup stays disabled because the container owns the database and indexing.

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
explicit container/session sync; use `--full` only when the user specifically
agrees to a full resync. Installing or upgrading the host CLI writes outside
the repository, so run it only after the user agrees. Creating, replacing,
starting, stopping, or removing a container is allowed only when the user
explicitly asks for that lifecycle operation or setup outcome.
</principle>

<principle name="container_authority">
Treat the container service as the only AgentsView server and data authority.
Pass the preflight's `--server` arguments to every host `session` command and
keep `AGENTSVIEW_NO_DAEMON=1`. Run commands that lack upstream `--server`
support (`projects`, `stats`, `activity`, and `usage daily`) through the
existing compose service, never against a host database.
</principle>

<principle name="runtime_secrets">
Keep AgentsView runtime configuration outside Git. Never reveal or commit
`auth_token`, `cursor_secret`, AWS credentials, or token-file contents. Pass
token-file paths to clients and preserve existing generated values during
container restarts.
</principle>

<principle name="structured_queries">
Request `--json` for machine-readable commands and synthesize from the parsed
fields. JSON prevents terminal formatting and truncation from becoming evidence.
Project only the fields needed for the answer before loading large arrays such
as usage breakdowns, activity buckets, or search context into model context.
</principle>

<principle name="traceable_evidence">
Cite session IDs for session-level facts. Cite message ordinals, or the search
result's ordinal range plus anchor, for transcript claims. Treat search snippets
as leads and inspect their surrounding message window before relying on them.
</principle>

<principle name="snapshot_state">
Treat running sessions and partial report windows as snapshots. When
`termination_status` is `tool_call_pending`, signals are pending, or a report's
`partial` field is true, state that the values may still change; do not present
them as final end-state measurements.
</principle>

<principle name="data_minimization">
Load only the messages needed to answer the question. AgentsView transcripts can
contain sensitive source, prompts, and tool output; never use `--reveal`, and do
not reproduce unrelated transcript content.
</principle>

</essential_principles>

<intake>

## What would you like to retrieve?

1. **Setup/start** — start local S3 AgentsView or connect to an existing service
2. **Status** — check the host CLI, container endpoint, and available projects
3. **Find sessions** — list and filter sessions by metadata or signals
4. **Inspect a session** — read metadata, messages, tool calls, health, or usage
5. **Search history** — find past decisions, instructions, errors, or examples
6. **Report a window** — retrieve factual stats, activity, cost, or token totals

If the user's request already identifies one of these intents, route directly
without repeating the menu. For a bare invocation or an invitation to "try",
"test", or "dogfood" AgentsView, run **Status** as the safe default and then
offer the other capabilities. Ask the menu only when the user explicitly wants
to explore options without running a check.

</intake>

<routing>

| Response or intent | Workflow |
|---|---|
| 1, "setup", "start", "stop", "install CLI", "configure container" | `references/setup.md` |
| 2, "status", "web UI", "is AgentsView running", "projects" | `references/status.md` |
| 3, "find", "list", "recent sessions", "filter sessions" | `references/find-sessions.md` |
| 4, "inspect", "read session", "transcript", "tool calls", session ID | `references/inspect-session.md` |
| 5, "search", "history", "have we done this", "why did we" | `references/search-history.md` |
| 6, "stats", "activity", "usage", "cost", "tokens", date range | `references/report-window.md` |

</routing>

<reference_index>

| Reference | Load when... |
|---|---|
| `references/setup.md` | Starting local S3 AgentsView, installing the CLI, or connecting to a service |
| `references/status.md` | Checking CLI/container readiness or discovering projects |
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
- label live sessions and partial windows as non-final snapshots;
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
- No host AgentsView daemon was started or used.
- Local setup stores generated secrets outside Git and verifies the web UI.
- Missing or unsupported data is stated rather than inferred.
- Host session commands use the preflight binary and container server URL.

</success_criteria>
