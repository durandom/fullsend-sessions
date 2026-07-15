# Hosting AgentsView

This guide covers exposing a shared AgentsView service beyond one user's
loopback interface. For a local S3-backed container and normal queries, follow
the start and query sections in the project README.

AgentsView treats S3 transcripts as read-only inputs and stores its derived
index locally. No checkout of this repository is required.

## Prerequisites

You need:

- a running S3 session-sharing deployment;
- `s3:ListBucket` and `s3:GetObject` access to its bucket or prefix;
- Podman;
- the globally installed `fs-sessions` skill;
- a stable URL for every client that will access the service.

Resolve the installed CLI:

```bash
FS_SESSIONS="$HOME/.agents/skills/fs-sessions/scripts/fs-sessions"
```

## Keep runtime configuration out of Git

AgentsView's generated configuration may contain:

- `auth_token`, a bearer token for authenticated API access;
- `cursor_secret`, an HMAC key used to sign pagination cursors;
- optional third-party API keys.

Treat these values as secrets. Store the real `config.toml`, token files, and
credential environment outside every repository. Never commit a generated
AgentsView configuration. A tracked example may contain only placeholders and
non-sensitive defaults.

Create a private runtime directory:

```bash
export AGENTSVIEW_DATA="$HOME/.local/share/fullsend-agentsview"
install -d -m 700 "$AGENTSVIEW_DATA"
```

Load AWS credentials through a secret-aware environment manager. Do not put
them in `config.toml`:

```bash
export S3_REGION=eu-central-1
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
# export AWS_SESSION_TOKEN=...   # only for temporary credentials
```

## Configure the S3 roots

Discover every uploaded machine root:

```bash
"$FS_SESSIONS" s3 check
"$FS_SESSIONS" s3 roots
```

Add the complete output roots to `$AGENTSVIEW_DATA/config.toml`:

```toml
claude_project_dirs = [
  "s3://team-agent-sessions/alice-laptop/raw/claude",
  "s3://team-agent-sessions/bob-workstation/raw/claude",
]
```

Protect the file before starting the service:

```bash
chmod 600 "$AGENTSVIEW_DATA/config.toml"
```

Do not set `CLAUDE_PROJECTS_DIR` in the container. That single-directory
environment variable overrides the `claude_project_dirs` array.

## Expose an authenticated team service

Do not expose an unauthenticated AgentsView service beyond loopback. For LAN,
VPN, or reverse-proxy access:

1. choose the exact browser-facing HTTPS or trusted private-network URL;
2. create a high-entropy bearer token and store it outside the repository;
3. pass the token through `AGENTSVIEW_AUTH_TOKEN`;
4. start AgentsView with `--require-auth` and the exact `--public-url`.

Example environment expected by the container:

```bash
export AGENTSVIEW_PUBLIC_URL=https://agentsview.example.com
export AGENTSVIEW_AUTH_TOKEN=... # load from a secret manager
```

Start the service behind the intended TLS endpoint or trusted private network:

```bash
podman run -d --name agentsview --pull=always \
  -p 0.0.0.0:8081:8080 \
  -e AWS_ACCESS_KEY_ID \
  -e AWS_SECRET_ACCESS_KEY \
  -e AWS_SESSION_TOKEN \
  -e AWS_REGION="$S3_REGION" \
  -e AWS_S3_ENDPOINT \
  -e AGENTSVIEW_AUTH_TOKEN \
  -v "$AGENTSVIEW_DATA:/data" \
  ghcr.io/kenn-io/agentsview:latest \
  --host 0.0.0.0 \
  --no-browser \
  --require-auth \
  --public-url "$AGENTSVIEW_PUBLIC_URL"
```

Plain HTTP on an untrusted network exposes transcript content and bearer
tokens. Terminate TLS at a trusted reverse proxy or keep the service on a
private network.

## Configure clients

Distribute the URL and bearer token through approved secret channels. Each
client stores the token in a private file:

```bash
install -d -m 700 "$HOME/.config/agentsview"
install -m 600 /dev/null "$HOME/.config/agentsview/token"
${EDITOR:-vi} "$HOME/.config/agentsview/token"

export AGENTSVIEW_SERVER_URL=https://agentsview.example.com
export AGENTSVIEW_SERVER_TOKEN_FILE="$HOME/.config/agentsview/token"
```

The `agentsview` skill passes the file path to the host CLI without reading the
token into agent context.

## AWS profiles and S3-compatible endpoints

For an AWS profile, mount the AWS configuration read-only and pass the profile:

```bash
-e AWS_PROFILE=team-sessions -v "$HOME/.aws:/root/.aws:ro"
```

For S3-compatible storage, set `AWS_S3_ENDPOINT` in both the exporter and
AgentsView environments.

## Lifecycle

```bash
podman logs -f agentsview
podman stop agentsview
podman start agentsview
podman rm -f agentsview
```

Removing the container does not remove `$AGENTSVIEW_DATA`. To rebuild the
derived index, stop AgentsView and remove only its index data while preserving
`config.toml` and token material. Never delete or rewrite S3 transcript objects
as part of an index rebuild.

To upgrade, remove the stopped container and rerun the applicable `podman run`
command with `--pull=always`.

## Verification

Verify the service from a configured agent session:

> Use agentsview to check the container endpoint and list available projects.

Verify the exporter side independently:

```bash
"$FS_SESSIONS" s3 check
"$FS_SESSIONS" s3 roots
"$FS_SESSIONS" status
```

An empty project list is valid before the first allowed transcript is uploaded
and indexed.
