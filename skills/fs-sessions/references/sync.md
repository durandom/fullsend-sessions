# Explicit legacy Git synchronization

The default S3 backend needs no push or pull. Objects become available after a
successful upload and AgentsView discovers them through polling.

Use this workflow only when `config show` explicitly lists the legacy `git`
backend. Resolve `repos.sessions`, then synchronize inside that repository:

```bash
git -C /path/to/session-repository pull --rebase
git -C /path/to/session-repository push
```

Do not add Git merely because an old repository exists. Do not resolve
transcript conflicts by editing content; preserve both source transcripts or
ask the user when paths collide.
