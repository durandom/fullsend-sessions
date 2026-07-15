# fullsend-sessions

Share selected Claude Code sessions with your team through S3, then browse and
query them with [AgentsView](https://github.com/kenn-io/agentsview).

Two skills make up the user workflow:

- `fs-sessions` configures S3, repository privacy rules, and the global
  `SessionEnd` upload hook.
- `agentsview` finds, reads, and searches sessions exposed by your team's
  AgentsView service.

You do not need to clone this repository.

## Install

Prerequisites are Node.js/npm, Python 3.10 or newer, and boto3:

```bash
python3 -c 'import boto3' 2>/dev/null || python3 -m pip install --user boto3
```

Install both skills globally for Claude Code and Codex:

```bash
npx skills add -g git@github.com:durandom/fullsend-sessions.git \
  --skill fs-sessions agentsview \
  --agent claude-code codex \
  --copy -y
```

Start a new agent session after installation. Confirm the installed skills with:

```bash
npx skills list -g --json
```

## Set up session sharing

The simplest setup is agent-guided. Load your S3 environment, open Claude Code
or Codex, and ask:

> Use fs-sessions to configure S3 session sharing from my current environment.
> Keep the policy default-deny, verify the bucket and machine name, allow this
> repository, upload one test session, and install exactly one global hook.

The skill will ask for or verify:

- an existing S3 bucket and region;
- boto3-compatible AWS credentials;
- a stable, non-secret machine name used as the AgentsView user filter;
- which Git repositories may upload sessions;
- one successful test upload before the automatic hook is enabled.

AWS credentials stay in the standard boto3 credential chain. The skill stores
only non-secret bucket metadata and policy rules in
`~/.config/rhdh-skill/config.json`.

### Configure S3 manually

Resolve the installed CLI and load your environment:

```bash
FS_SESSIONS="$HOME/.agents/skills/fs-sessions/scripts/fs-sessions"

export S3_BUCKET=team-agent-sessions
export S3_REGION=eu-central-1
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
# export AWS_SESSION_TOKEN=...   # only for temporary credentials
```

An AWS profile can replace exported keys:

```bash
export AWS_PROFILE=team-sessions
```

Initialize and verify the S3 backend:

```bash
"$FS_SESSIONS" config init --machine alice-laptop
"$FS_SESSIONS" config show
"$FS_SESSIONS" s3 check
```

Your AWS identity needs `s3:ListBucket`, `s3:GetObject`, and `s3:PutObject` for
the configured bucket or prefix. The skill does not create cloud resources.

## Choose which repositories may upload

The repository policy is the privacy boundary checked before every automatic
upload. The recommended model is a whitelist:

- `default deny` keeps every unmatched repository private.
- `allow` opts in trusted repositories or organizations.
- Rules are evaluated from top to bottom; the last matching rule wins.

Allow an organization by normalized Git origin:

```bash
"$FS_SESSIONS" policy default deny
"$FS_SESSIONS" policy allow --origin 'github.com/example-org/*'
"$FS_SESSIONS" policy check /absolute/path/to/repository
```

Use path rules for local-only repositories or exceptions:

```bash
"$FS_SESSIONS" policy allow --path '/work/*'
"$FS_SESSIONS" policy deny --path '/work/customer-*'
"$FS_SESSIONS" policy allow --path '/work/customer-sanitized-demo'
```

The sanitized demo is allowed because its rule is the last match. Inspect and
manage the ordered rules with:

```bash
"$FS_SESSIONS" policy rules
"$FS_SESSIONS" policy check /work/customer-sanitized-demo
"$FS_SESSIONS" policy remove 3
```

A blacklist uses `default allow` and denies only matching repositories. This
shares every otherwise-unmatched Git repository, so use it only when that broad
export is intentional:

```bash
"$FS_SESSIONS" policy default allow
"$FS_SESSIONS" policy deny --path '/work/customer-*'
```

A repository cannot grant itself permission to upload. It can only opt out with
this `.rhdh/config.json`:

```json
{"sessions":{"enabled":false}}
```

## Verify and install the hook

Check the intended repository and upload one session explicitly:

```bash
"$FS_SESSIONS" policy check /absolute/path/to/repository
"$FS_SESSIONS" share --last
"$FS_SESSIONS" s3 roots
```

When those checks succeed, install the global Claude Code `SessionEnd` hook:

```bash
"$FS_SESSIONS" hook install
"$FS_SESSIONS" hook status
"$FS_SESSIONS" status
```

The hook lives in `~/.claude/settings.json`. It uploads allowed sessions and
their subagents, tool results, and companion files when Claude Code exits.
Denied or unchanged sessions remain quiet.

Remove it with:

```bash
"$FS_SESSIONS" hook uninstall
```

## Use session sharing

The hook handles normal uploads automatically. You can also ask the skill to
inspect or change the setup:

Check the current repository:

> Use fs-sessions to explain whether the current repository may upload and
> show the matching policy rule.

Allow an organization:

> Use fs-sessions to allow all repositories from
> `github.com/example-org/*`, then verify the current repository.

Inspect without changing anything:

> Use fs-sessions to show S3 access, hook status, and available AgentsView
> roots without changing anything.

Manual commands are available when needed:

```bash
"$FS_SESSIONS" list
"$FS_SESSIONS" share --last
"$FS_SESSIONS" status
```

## Start AgentsView

You can run AgentsView locally against the shared S3 bucket without cloning
this repository. You need Podman and the same read credentials used by
`fs-sessions`.

Discover the uploaded machine roots:

```bash
"$FS_SESSIONS" s3 check
"$FS_SESSIONS" s3 roots
```

Create a private data directory outside any Git repository:

```bash
export AGENTSVIEW_DATA="$HOME/.local/share/fullsend-agentsview"
install -d -m 700 "$AGENTSVIEW_DATA"
${EDITOR:-vi} "$AGENTSVIEW_DATA/config.toml"
```

Add every returned root to `config.toml`:

```toml
claude_project_dirs = [
  "s3://team-agent-sessions/alice-laptop/raw/claude",
  "s3://team-agent-sessions/bob-workstation/raw/claude",
]
```

Protect the configuration and start AgentsView on loopback:

```bash
chmod 600 "$AGENTSVIEW_DATA/config.toml"

podman run -d --name agentsview --pull=always \
  -p 127.0.0.1:8081:8080 \
  -e AWS_ACCESS_KEY_ID \
  -e AWS_SECRET_ACCESS_KEY \
  -e AWS_SESSION_TOKEN \
  -e AWS_REGION="$S3_REGION" \
  -e AWS_S3_ENDPOINT \
  -v "$AGENTSVIEW_DATA:/data" \
  ghcr.io/kenn-io/agentsview:latest \
  --host 0.0.0.0 \
  --no-browser \
  --public-url http://127.0.0.1:8081
```

Open <http://127.0.0.1:8081>. Stop or restart the same container with:

```bash
podman stop agentsview
podman start agentsview
podman logs -f agentsview
```

The bucket remains the source of truth. `$AGENTSVIEW_DATA` contains only the
runtime configuration and a replaceable derived index. AgentsView may add an
`auth_token` and `cursor_secret` to `config.toml`; keep that file outside Git.

See [Hosting AgentsView](docs/agentsview-hosting.md) when exposing the service
to other users over a network.

## Query AgentsView with the skill

Make the local URL available to the shell that starts your agent:

```bash
export AGENTSVIEW_SERVER_URL=http://127.0.0.1:8081
```

For a shared authenticated service, use the URL and token file provided by its
operator:

```bash
export AGENTSVIEW_SERVER_URL=https://agentsview.example.com
export AGENTSVIEW_SERVER_TOKEN_FILE="$HOME/.config/agentsview/token"
```

Then ask Claude Code or Codex naturally:

Check readiness:

> Use agentsview to check the service and list the available projects.

Find sessions:

> Use agentsview to find the latest sessions for project `service-catalog`.

Inspect one session:

> Use agentsview to inspect session `<session-id>` and cite the relevant message
> ordinals.

Search historical evidence:

> Use agentsview to search past sessions for the decision to use S3 instead of
> Git and cite the matching evidence.

The skill is read-only by default and connects its host CLI to the team
container; it does not start a second AgentsView database. If the host CLI is
missing, the skill explains the verified installation and asks before writing
it to `~/.local/bin/agentsview`.

## Update

```bash
npx skills update -g fs-sessions agentsview
```

Start a new agent session afterward so it loads the updated instructions.

## Troubleshooting

```bash
"$FS_SESSIONS" config show
"$FS_SESSIONS" s3 check
"$FS_SESSIONS" s3 roots
"$FS_SESSIONS" policy check .
"$FS_SESSIONS" hook status
"$FS_SESSIONS" status
```

- `AccessDenied` during `s3 check`: verify `s3:ListBucket` for the active AWS
  identity.
- Upload failure: verify `s3:PutObject` for the configured bucket or prefix.
- Missing AgentsView sessions: verify `s3:GetObject`, compare the configured
  roots with `s3 roots`, and upload one test session.
- A repository does not upload: inspect the last matching policy rule.

## Development

Repository contributors can clone the project and run:

```bash
uv sync
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
```
