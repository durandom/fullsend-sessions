# Set Up AgentsView

Use this workflow to start a local S3-backed service, connect to an existing
service, or install its host client. Keep the container as the only database and
index authority.

## Confirm mutations

Before changing the machine, state which actions are needed and ask once for
approval. Possible mutations are:

- downloading and installing the verified host CLI;
- creating a private runtime directory and `config.toml` outside Git;
- pulling, creating, replacing, starting, stopping, or removing a container.

Do not ask again for each action already covered by that approval.

## Connect to an existing service

Use `AGENTSVIEW_SERVER_URL` or the explicit URL supplied by the user. For an
authenticated endpoint, use `AGENTSVIEW_SERVER_TOKEN_FILE` or
`--server-token-file`; never read the token into context.

Proceed to **Install the host client** and **Verify the web UI and client**.

## Start a local S3-backed service

### 1. Discover the exporter configuration

Resolve the installed `fs-sessions` CLI at the first existing location:

```text
~/.agents/skills/fs-sessions/scripts/fs-sessions
~/.claude/skills/fs-sessions/scripts/fs-sessions
```

Run its read-only gates with the user's current credential environment:

```bash
"$FS_SESSIONS" s3 check
"$FS_SESSIONS" s3 roots
```

Stop if bucket access fails or no root exists. Do not read credential files or
print credential values. Use every returned `s3://.../raw/claude` root.

### 2. Create private runtime configuration

Use `~/.local/share/fullsend-agentsview` unless the user specifies another
directory. Create it with mode `0700`; create `config.toml` with mode `0600`.
Set `claude_project_dirs` to the discovered roots.

If the file already exists, preserve unrelated fields and generated
`auth_token` or `cursor_secret` values. Never place this file inside a Git
repository. Do not set `CLAUDE_PROJECTS_DIR`, which overrides the root array.

### 3. Start the container

Require Podman and the same AWS credential environment used by `s3 check`.
Start `ghcr.io/kenn-io/agentsview:latest` as container `agentsview`, persist the
runtime directory at `/data`, and publish only `127.0.0.1:8081:8080` by default.
Pass:

```text
--host 0.0.0.0
--no-browser
--public-url http://127.0.0.1:8081
```

Pass AWS values by environment name, not literal command arguments. Include
`AWS_REGION`, optional `AWS_SESSION_TOKEN`, and optional `AWS_S3_ENDPOINT`.

If a container named `agentsview` already exists, inspect it first. Start it
when stopped and compatible. Replace it only after the user approved replacement
and its `/data` mount points at the intended persistent runtime directory.

For shared network exposure, stop and explain that it requires an authenticated
operator deployment with a stable public URL and TLS or a trusted private
network. Do not expose an unauthenticated service beyond loopback.

## Install the host client

If preflight reports no usable host CLI, explain that the installer downloads
the official AgentsView release, verifies it against `SHA256SUMS`, and writes
`~/.local/bin/agentsview`. After approval, run from this skill directory:

```bash
python scripts/install_cli.py --json
```

Consume the complete JSON. Use `--force` only for an explicit upgrade or
replacement and `--version <tag>` only for a requested release.

The installer never starts a host daemon, syncs sessions, or modifies the
container database.

## Verify the web UI and client

Verify all of the following:

1. the container is running;
2. an HTTP request to the exact public URL succeeds;
3. preflight reports `available`, `working`, and `server_working` as true;
4. `host_daemon_disabled` is true;
5. one bounded remote `session list` call succeeds, including a zero count.

For authenticated endpoints, pass only the token-file path. A `403` mentioning
the Host allowlist means the client URL differs from `--public-url`; use the
exact configured URL or restart with the intended one.

Report the verified web UI URL, host CLI path/version, container connectivity,
and the preflight's `server_session_count`. Do not infer the archive total from
the length of a bounded session list. An empty archive is a valid service state.

## Lifecycle requests

For explicit start, stop, restart, logs, or removal requests, operate only on
the `agentsview` container. Removing the container must preserve its external
runtime directory. Never remove or rewrite S3 transcripts as part of container
or index maintenance.
