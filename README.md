# fullsend-sessions

Share Claude Code session transcripts with your team through S3, and browse or
query them with [AgentsView](https://github.com/kenn-io/agentsview).

The setup has two skills:

- `fs-sessions` configures S3, repository privacy rules, and the global
  `SessionEnd` hook that uploads allowed sessions.
- `agentsview` provides read-only, evidence-based access to the sessions indexed
  by an AgentsView service.

You do not need to clone this repository to use either skill.

## 1. Install the skills

You need Node.js/npm for the skill installer and Python 3.10 or newer for the
`fs-sessions` CLI. Install boto3 into that Python environment if it is not
already available:

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

Start a new Claude Code or Codex session after installation so the agent loads
the new skill instructions. Verify the installation with:

```bash
npx skills list -g --json
```

The deterministic `fs-sessions` CLI is installed with the skill:

```bash
FS_SESSIONS="$HOME/.agents/skills/fs-sessions/scripts/fs-sessions"
"$FS_SESSIONS" --help
```

You can run these commands yourself, or ask the agent to use `fs-sessions` for
the same workflow.

## 2. Configure the S3 bucket

You need an existing S3 bucket and an AWS identity that can access it. The skill
does not create cloud resources.

Required permissions are:

| Permission | Purpose |
| --- | --- |
| `s3:ListBucket` | Validate access and discover AgentsView roots |
| `s3:GetObject` | Let AgentsView read transcripts |
| `s3:PutObject` | Upload transcripts |

Provide credentials through boto3's standard credential chain. For example,
load them with direnv or another secret-aware environment manager:

```bash
export S3_BUCKET=team-agent-sessions
export S3_REGION=eu-central-1
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
# export AWS_SESSION_TOKEN=...   # only for temporary credentials
```

An AWS profile also works:

```bash
export S3_BUCKET=team-agent-sessions
export S3_REGION=eu-central-1
export AWS_PROFILE=team-sessions
```

Initialize the S3 backend with a stable, non-secret machine name. This name is
also the user/machine filter shown in AgentsView:

```bash
"$FS_SESSIONS" config init --machine alice-laptop
"$FS_SESSIONS" config show
"$FS_SESSIONS" s3 check
```

Alternatively, pass non-secret deployment metadata explicitly:

```bash
"$FS_SESSIONS" config init \
  --bucket team-agent-sessions \
  --region eu-central-1 \
  --profile team-sessions \
  --machine alice-laptop
```

The configuration is stored in `~/.config/rhdh-skill/config.json`. It contains
the bucket, region, machine name, and repository policy, but never AWS access or
secret keys.

## 3. Decide which repositories may share sessions

The repository policy is the privacy boundary. Before every automatic upload,
the global hook checks the Git repository against this policy.

The recommended policy is a whitelist:

- `default deny` means unmatched repositories are private.
- `allow` rules opt in only trusted repositories or organizations.
- Rules are evaluated from top to bottom; the last matching rule wins.

Origin rules work across different checkout paths. SSH and HTTPS remotes are
normalized to values such as `github.com/example-org/service`:

```bash
"$FS_SESSIONS" policy default deny
"$FS_SESSIONS" policy allow --origin 'github.com/example-org/*'
"$FS_SESSIONS" policy check /absolute/path/to/repository
```

Path rules are useful for local-only repositories or narrow exceptions:

```bash
"$FS_SESSIONS" policy allow --path '/work/*'
"$FS_SESSIONS" policy deny --path '/work/customer-*'
"$FS_SESSIONS" policy allow --path '/work/customer-sanitized-demo'
```

In this example, `/work/customer-sanitized-demo` is allowed because its rule is
the last match. Inspect or remove rules with:

```bash
"$FS_SESSIONS" policy rules
"$FS_SESSIONS" policy check /work/customer-sanitized-demo
"$FS_SESSIONS" policy remove 3
```

A blacklist reverses the model: `default allow` shares every otherwise
unmatched Git repository. Use it only when that broad automatic export is
intentional:

```bash
"$FS_SESSIONS" policy default allow
"$FS_SESSIONS" policy deny --path '/work/customer-*'
```

A checked-out repository cannot grant itself upload permission. It can only opt
out by adding the following local configuration to `.rhdh/config.json`:

```json
{"sessions":{"enabled":false}}
```

## 4. Verify an upload and install the hook

Test the selected repository before enabling automatic sharing:

```bash
"$FS_SESSIONS" policy check /absolute/path/to/repository
"$FS_SESSIONS" share --last
"$FS_SESSIONS" s3 roots
```

When the policy decision and upload are correct, install exactly one global
Claude Code `SessionEnd` hook:

```bash
"$FS_SESSIONS" hook install
"$FS_SESSIONS" hook status
"$FS_SESSIONS" status
```

The hook is stored in `~/.claude/settings.json`. Installation is idempotent and
replaces older managed session-export hooks while preserving unrelated
settings. After each allowed Claude Code session ends, it uploads the transcript
and its companion files under:

```text
<machine>/raw/claude/<project>/
  <session-id>.jsonl
  <session-id>/
    subagents/**
    tool-results/**
    <other companion files>
```

Denied, unchanged, or malformed sessions are skipped silently. A successful
upload produces a short Claude Code system message.

To remove the global hook later:

```bash
"$FS_SESSIONS" hook uninstall
```

## 5. Use `fs-sessions` through your agent

Examples for Claude Code or Codex:

Initial setup:

> Use fs-sessions to configure S3 session sharing from my current environment.
> Keep the policy default-deny, verify bucket access and the machine name, allow
> this repository, upload one test session, and install exactly one global hook.

Allow an organization:

> Use fs-sessions to allow all repositories from
> `github.com/example-org/*`. Show the ordered rules and explain the decision
> for the current repository afterward.

Deny a sensitive path:

> Use fs-sessions to deny session sharing for `/work/customer-*`, then verify
> that the current repository cannot upload.

Inspect without changing anything:

> Use fs-sessions to show the current S3 configuration, repository-policy
> decision, hook status, and AgentsView roots without changing anything.

Manual CLI operations remain available:

```bash
"$FS_SESSIONS" list
"$FS_SESSIONS" share --last
"$FS_SESSIONS" share \
  --transcript /path/to/session.jsonl \
  --cwd /path/to/project
```

## 6. Start AgentsView from S3

This step is needed once for the person or service hosting the shared web UI.
Other users only need its URL. No checkout of this repository is required.

First discover the exact S3 roots:

```bash
"$FS_SESSIONS" s3 check
"$FS_SESSIONS" s3 roots
```

Create a persistent AgentsView data directory and add every returned root to
its configuration:

```bash
export AGENTSVIEW_DATA="$HOME/.local/share/fullsend-agentsview"
mkdir -p "$AGENTSVIEW_DATA"
${EDITOR:-vi} "$AGENTSVIEW_DATA/config.toml"
```

Example `config.toml`:

```toml
claude_project_dirs = [
  "s3://team-agent-sessions/alice-laptop/raw/claude",
  "s3://team-agent-sessions/bob-workstation/raw/claude",
]
```

Start the published AgentsView container on loopback:

```bash
podman run -d --name agentsview --pull=always \
  -p 127.0.0.1:8081:8080 \
  -e AWS_ACCESS_KEY_ID \
  -e AWS_SECRET_ACCESS_KEY \
  -e AWS_SESSION_TOKEN \
  -e AWS_REGION="$S3_REGION" \
  -e AWS_S3_ENDPOINT \
  -v "$AGENTSVIEW_DATA:/data" \
  ghcr.io/kenn-io/agentsview:latest
```

Open <http://127.0.0.1:8081>. The S3 objects remain the source of truth;
`$AGENTSVIEW_DATA` contains only AgentsView configuration and its derived index.

Container lifecycle commands:

```bash
podman logs -f agentsview
podman stop agentsview
podman start agentsview
podman rm -f agentsview
```

For AWS profiles instead of exported keys, mount the AWS configuration
read-only and pass the profile name:

```bash
-e AWS_PROFILE=team-sessions -v "$HOME/.aws:/root/.aws:ro"
```

Keep the default loopback binding unless you deliberately configure AgentsView
authentication and a public URL for remote access.

## 7. Query sessions with the `agentsview` skill

Point the skill at the running container endpoint:

```bash
export AGENTSVIEW_SERVER_URL=http://127.0.0.1:8081
```

The skill is read-only by default. It can find sessions, inspect messages and
tool calls, search historical decisions, and report stored usage or activity.
Ask naturally from Claude Code or Codex:

Check readiness:

> Use agentsview to check whether the container is healthy and list the
> available projects.

Find sessions:

> Use agentsview to find the latest sessions for project `service-catalog`.

Inspect one session:

> Use agentsview to inspect session `<session-id>` and show the relevant tool
> calls with message evidence.

Search historical evidence:

> Use agentsview to search past sessions for the decision to use S3 instead of
> Git and cite the matching session IDs and message ordinals.

The skill connects its host CLI to the container and does not start a second
AgentsView database. If the host CLI is missing, it will explain the verified
installation and ask before writing it to `~/.local/bin/agentsview`.

## Update the skills

```bash
npx skills update -g fs-sessions agentsview
```

Start a new agent session afterward so updated instructions are loaded.

## Troubleshooting

```bash
"$FS_SESSIONS" config show    # saved non-secret configuration
"$FS_SESSIONS" s3 check       # bucket and ListBucket access
"$FS_SESSIONS" s3 roots       # uploaded machine roots
"$FS_SESSIONS" policy check . # final policy decision for this repository
"$FS_SESSIONS" hook status    # installed global hook
"$FS_SESSIONS" status         # combined status
```

Common causes:

- `AccessDenied` during `s3 check`: the active identity lacks `s3:ListBucket`.
- Upload failure: verify `s3:PutObject` for the configured bucket or prefix.
- AgentsView shows no sessions: verify `s3:GetObject`, compare `config.toml`
  with `s3 roots`, then upload one test session.
- A repository does not upload: run `policy check` and inspect the last matching
  rule.

## Development

Repository contributors can clone the project and run:

```bash
uv sync
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
```
