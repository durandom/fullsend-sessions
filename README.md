# fullsend-sessions

Share selected Claude Code sessions and Fullsend agent runs through S3, then
browse and query them with
[AgentsView](https://github.com/kenn-io/agentsview).

This repository provides two agent skills:

- `fs-sessions` configures sharing, repository policy, automatic uploads, and
  Fullsend imports.
- `agentsview` starts and queries the local S3-backed session viewer.

You install the skills once. After that, use them by asking your agent for the
outcome you want. You do not need to locate or invoke their internal CLIs.

## Install

Install the skills globally for Claude Code and Codex:

```bash
npx skills add -g git@github.com:durandom/fullsend-sessions.git \
  --skill fs-sessions agentsview \
  --agent claude-code codex \
  --copy -y
```

Start a new agent session after installation so the skills are available.
Python 3.10 or newer and `boto3` are required. Running the local viewer also
requires Podman.

## Set up session sharing

Load your S3 credentials into the environment before starting the agent. Do
not paste credentials into chat or store them in this repository.

Then ask:

> Set up fs-sessions for this repository using the S3 configuration and AWS
> credentials already available in my environment. Keep sharing default-deny,
> allow this repository, verify one upload, and install exactly one global
> SessionEnd hook.

The agent validates S3 access, stores only non-secret bucket metadata, creates
the global repository policy, resolves a stable machine identity, tests an
upload, and installs the hook.

To check an existing installation, ask:

> Check whether session sharing is correctly configured for this repository.
> Verify S3 access, explain the matching policy rule, inspect the global hook,
> and tell me whether the next completed session will upload.

## Choose what gets shared

Sharing is controlled by a global, ordered policy. The safe default is to deny
everything and explicitly allow trusted repositories or organizations.

Example requests:

> Allow session sharing for every repository in `github.com/example-org/*`,
> then show me the resulting policy.

> Stop sharing sessions from this repository without changing the rules for
> other repositories.

> Explain why the current repository is allowed or denied. Do not change the
> policy.

A checked-out repository cannot grant itself permission to upload. It can only
opt out by setting this in `.rhdh/config.json`:

```json
{"sessions":{"enabled":false}}
```

## Share and find sessions

The global hook uploads an allowed session when it ends. It preserves the
parent transcript, nested subagents, tool results, and companion files.

You can also ask for an explicit upload:

> Share my most recent Claude Code session now and verify that its complete
> session family is present in S3.

To browse the archive, ask:

> Start the local S3-backed AgentsView service, verify it is healthy, and give
> me the viewer URL.

Once it is running, use natural requests such as:

> Find the most recent sessions for the `rhdh-plugins` repository.

> Show me the parent, subagents, message count, and completion status for this
> AgentsView session: `<session-id>`.

> Search our recorded sessions for the decision about S3 project and machine
> naming. Cite the sessions and messages that support the answer.

AgentsView is read-only by default. Rebuilding its disposable local index does
not alter the source transcripts in S3.

## Import Fullsend runs

Fullsend artifacts are downloaded from GitHub on demand, converted into native
AgentsView sessions, and uploaded directly to S3. Ask the agent to preview
before importing:

> Preview Fullsend session artifacts from the last seven days. Group the
> result by repository and Fullsend agent, and do not write to S3 yet.

Then import the desired scope:

> Import the previewed Fullsend artifacts into S3 and report the numbers of
> parent sessions, subagents, skipped artifacts, and failures.

You can also target a repository or workflow run:

> Import Fullsend run `123456789` from
> `redhat-developer/rhdh-agentic`, then verify it appears in AgentsView.

Repeated imports are idempotent. A forced schema migration regenerates derived
sessions while preserving the archived GitHub artifact and provenance; it may
require scoped S3 delete permission for obsolete derived objects.

## How sessions are grouped

AgentsView exposes project, agent, and machine dimensions. This repository uses
them consistently:

| AgentsView field | Meaning |
|---|---|
| `project` | Git repository, such as `rhdh-plugins` |
| `agent` | Session format/runtime, normally `claude` |
| `machine` | Producing user identity inferred from Git, or a Fullsend agent such as `fs-code` |

AgentsView normalizes dashes to underscores in project labels, so
`rhdh-plugins` appears as `rhdh_plugins` in the UI.

Fullsend machine names are derived from the artifact agent:

```text
fullsend-code   -> fs-code
fullsend-review -> fs-review
fullsend-triage -> fs-triage
```

S3 is the only transcript backend. Git is used only to identify repositories
for policy checks and to retrieve GitHub Actions artifacts. Runtime secrets,
AgentsView configuration, and transcript content stay outside this repository.

## Common requests

> Show me the current sharing status.

> List the repositories allowed to upload sessions.

> Share my latest session.

> Preview recent Fullsend runs.

> Start AgentsView and give me its URL.

> Rebuild the local AgentsView index from S3.

> Find sessions for this repository from `fs-review`.

> Stop AgentsView without deleting its S3 data.
