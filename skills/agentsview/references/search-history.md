# Search Session History

Use AgentsView as an evidence source for prior decisions, instructions,
examples, errors, files, or commands. A search snippet is a lead, not an answer.

## Choose the Search Mode

| Query type | Start with |
|---|---|
| concept or paraphrased question | `--hybrid` |
| exact identifier, path, command, or short phrase | plain substring |
| tokenized message terms | `--fts` |
| structural text pattern | `--regex` |

Concept example:

```bash
"$AGENTSVIEW_BIN" session search "why use a separate worker" \
  --hybrid --scope top --context 2 --limit 8 --json
```

Exact example across messages and tool I/O:

```bash
"$AGENTSVIEW_BIN" session search "permission denied" \
  --in messages,tool_input,tool_result \
  --context 2 --limit 8 --json
```

Add project, agent, or date filters when the user supplied them. Use `--since`
for recency, remembering that `m` means calendar months. Semantic, hybrid, and
FTS searches cover messages only; substring and regex can include tool inputs
and results.

## Evidence Workflow

1. Translate the request into focused vocabulary and likely projects or dates.
2. Run at most 4-6 distinct probes. Several short exact queries are better than
   one overloaded FTS expression.
3. Read results from the top-level `matches` array and pagination from
   `next_cursor`. Triage the top matches from their `snippet`, `ordinal`,
   `ordinal_range`, and inline context.
4. Deep-read only the strongest 2-4 sessions:

   ```bash
   "$AGENTSVIEW_BIN" session messages <session-id> \
     --around <anchor> --before 8 --after 8 \
     --role user,assistant --json
   ```

5. Cite the result's full conversation-unit range and anchor as
   `<session-id>#<start>-<end> @<anchor>`. For a single-message unit, cite
   `<session-id>#<ordinal>`.
6. Treat `subordinate` hits from sidechains, forks, or subagents as supporting
   evidence. Corroborate them in `parent_session_id` before treating them as the
   governing decision.
7. Down-rank very recent echoes from the current conversation by checking the
   session timestamps.

## Semantic Fallbacks

| Failure | Action |
|---|---|
| Semantic search unavailable / HTTP 501 | Use several short FTS or substring probes; state that embeddings are unavailable |
| Semantic search temporarily unavailable / HTTP 503 | Retry once, then continue with FTS and report the transient failure |
| No convincing result | Widen the time range, remove one filter, then report the evidence gap |

Do not silently claim that no prior decision exists merely because semantic
search is unavailable.

## Output

Return:

1. applied searches and scope;
2. strongest matches with project, agent, session ID, and ordinals;
3. a factual synthesis grounded in those matches;
4. gaps and the next useful probe, if any.

Do not turn recurring patterns into coaching or process recommendations.
