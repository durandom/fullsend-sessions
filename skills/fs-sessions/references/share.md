# Explicit share and list

List recent local Claude Code transcripts:

```bash
"$FS" list
"$FS" list --limit 50
```

Upload the most recent transcript without evaluating automatic-hook policy:

```bash
"$FS" share --last
```

Or upload a known transcript:

```bash
"$FS" share --transcript /path/to/session.jsonl --cwd /path/to/project
```

Manual share returns non-zero when any selected backend fails. With the default
S3 backend it stages the complete session family only for the duration of the
upload, then removes the temporary copy.

Objects preserve AgentsView's S3 layout:

```text
<machine>/raw/claude/<project>/
  <session-id>.jsonl
  <session-id>/
    subagents/**
    tool-results/**
    <other regular companion files>
```

The parent transcript receives synthetic AgentsView metadata. Companion files
are copied byte-for-byte, including binaries; symlinks are skipped so a session
directory cannot pull unrelated files into the bucket.
