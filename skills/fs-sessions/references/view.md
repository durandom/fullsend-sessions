# View in AgentsView

Discover the exact S3 roots before configuring AgentsView:

```bash
"$FS" s3 check
"$FS" s3 roots
```

Set `claude_project_dirs` in AgentsView's `config.toml` to the returned roots.
Pass the same boto3 credential environment to the container and remove
`CLAUDE_PROJECTS_DIR`, because that environment variable overrides the root
array.

Use the deterministic writer to preserve generated secrets and unrelated
settings while updating only the root array:

```bash
"$FS" s3 agentsview-config \
  --data-dir "$HOME/.local/share/fullsend-agentsview"
```

For a `fullsend-sessions` checkout, start the configured S3 viewer with:

```bash
direnv exec /path/to/fullsend-sessions just -d /path/to/fullsend-sessions up
```

This uses the private `AGENTSVIEW_DATA` directory and reads AWS credentials from
the environment. Stop it while preserving the derived index with:

```bash
direnv exec /path/to/fullsend-sessions just -d /path/to/fullsend-sessions down
```

To force a complete re-index, follow the AgentsView setup workflow and remove
only derived index files from the private runtime directory. Never delete or
rewrite S3 transcript objects as part of an index rebuild.

Interactive sessions use the configured user identity as the machine filter;
Fullsend sessions use `fs-<agent>`.
