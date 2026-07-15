# S3-first setup or migration

Use this workflow for a new installation or migration from Git-backed sharing.
Load `references/s3.md` directly from `SKILL.md` for credential and IAM gates.
The skill configures an existing bucket; it does not provision cloud resources.
If no bucket or authorized identity exists, ask the user to obtain them from
their cloud administrator before continuing.

## 1. Resolve the machine name

Use a stable, non-secret user or workstation label such as `alice-laptop`.
Prefer an existing `FS_SESSIONS_MACHINE`; otherwise normalize
`git config user.name` to lowercase hyphenated form. Confirm it with the user
when it is ambiguous because it becomes the AgentsView machine filter.

## 2. Initialize S3 configuration

With `S3_BUCKET`, `S3_REGION`, and boto3 credentials already in the environment:

```bash
"$FS" config init --machine alice-laptop
```

Or pass non-secret deployment metadata explicitly:

```bash
"$FS" config init \
  --bucket team-agent-sessions \
  --region eu-central-1 \
  --machine alice-laptop \
  --profile team-sessions
```

This sets `backends: ["s3"]`, keeps the policy default-deny, preserves unrelated
global configuration, and never stores access keys or secret keys.

## 3. Pass the S3 gates

```bash
"$FS" config show
"$FS" s3 check
```

Stop if configuration contains a Git backend, credentials appear in the saved
JSON, or `s3 check` cannot list the configured bucket. Use the error to identify
the missing environment/profile or IAM permission before installing the hook.

## 4. Add the initial allow rule

Prefer an origin rule for team repositories and a path rule for local-only
repositories:

```bash
"$FS" policy allow --origin 'github.com/example-org/*'
# or
"$FS" policy allow --path '/absolute/path/to/repository'
"$FS" policy check /absolute/path/to/repository
```

Continue only when the check reports `allow` and the expected rule number.

## 5. Install the global hook

```bash
"$FS" hook install
"$FS" hook status
```

The installer preserves unrelated settings and replaces earlier managed or
legacy session hooks.

## 6. Verify a real upload

```bash
"$FS" share --last
"$FS" s3 roots
"$FS" status
```

Setup is complete when the explicit share reports S3 success, the expected
machine root appears, the intended repository is allowed, and exactly one
global managed hook exists.

## Explicit legacy Git mode

Use Git storage only when the user requests it:

```bash
"$FS" config init --backend git --repo /absolute/path/to/session-repository
```

Do not silently combine Git and S3; dual writes require an explicit config edit
and a stated retention reason.
