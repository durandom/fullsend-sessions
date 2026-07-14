# Set Up the Host CLI

Use this workflow when the local CLI is missing, outdated, or not connected to
the container. AgentsView continues to run and own its data inside the existing
compose service; this setup installs only a host client.

## 1. Confirm the Mutation

Explain that setup downloads the official AgentsView release, verifies it
against the release `SHA256SUMS`, and writes the executable to
`~/.local/bin/agentsview` by default. Ask before running it because this changes
the user's home directory and uses the network.

## 2. Install

After approval, run from the skill directory:

```bash
python scripts/install_cli.py --json
```

Consume the complete JSON. If a CLI is already present, the script succeeds
without replacing it. Use `--force` only when the user asked to upgrade or
replace it. Use `--version <tag>` only when a particular release is required.

The installer supports macOS, Linux, and Windows release archives and never
starts AgentsView, syncs sessions, or modifies its database.

## 3. Connect to the Container

Rerun the preflight from `SKILL.md`. It resolves the endpoint in this order:

1. `--server <url>`
2. `AGENTSVIEW_SERVER_URL`
3. the running `agentsview` compose service's `--public-url`
4. the rendered compose configuration's `--public-url`

For authenticated endpoints, pass `--server-token-file <path>` or set
`AGENTSVIEW_SERVER_TOKEN_FILE`. Keep only the path in context; the CLI reads the
token directly.

The preflight proves connectivity with a bounded `session list --server` call
while setting `AGENTSVIEW_NO_DAEMON=1`. A 403 mentioning the Host allowlist
means the URL does not match the container's `--public-url`; use that exact
public URL or restart the compose service with the intended one.

## Success Criteria

- preflight returns `available: true`, `working: true`, and
  `server_working: true`;
- `binary` is an absolute host path;
- `server_url` is the container's public URL;
- `host_daemon_disabled` is true;
- a remote session count is returned, including zero for an empty archive.
