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

For `fullsend-sessions`, start the configured S3 viewer with:

```bash
direnv exec /path/to/fullsend-sessions \
  just -d /path/to/fullsend-sessions sessions-s3
```

This uses `compose.s3.yaml`, keeps its derived index in a separate container
volume, and reads the AWS credentials from the environment. Stop it and remove
only that derived S3 index with:

```bash
direnv exec /path/to/fullsend-sessions \
  just -d /path/to/fullsend-sessions down-s3
```

To force a complete re-index, remove only the derived AgentsView index volume
before restarting. Never delete or rewrite S3 transcript objects as part of an
index rebuild.

Sessions use the configured machine segment as the AgentsView machine filter.
