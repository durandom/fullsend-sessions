# Status and diagnosis

Run:

```bash
"$FS" status
"$FS" s3 check
```

Status reports S3 storage, stable user machine name, non-secret S3
configuration, enabled state, repository policy, and global hook. `s3 check`
separately proves the active boto3 identity can list the bucket.

For a repository-specific diagnosis, also run:

```bash
"$FS" policy check /path/to/repository
```

Interpret common denial reasons:

| Reason | Meaning | Action |
|---|---|---|
| `not_git_repository` | `cwd` has no Git root | No automatic export; use explicit share if intended |
| `globally_disabled` | `sessions.enabled` is false | Enable globally only after user confirmation |
| `project_opt_out` | `.rhdh/config.json` disables sharing | Preserve the opt-out unless the user owns and changes it |
| `default_deny` | No allow rule matched | Add the narrowest suitable origin/path allow rule |
| `matched_rule` | An ordered rule decided | Report its one-based index and selector |

If the hook is installed but no upload occurs, check policy first, then S3
configuration, boto3 availability, credential presence, `s3:PutObject`, and the
user machine name. Do not switch SDKs or copy credentials into config to work around
an IAM denial.
