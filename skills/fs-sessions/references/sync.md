# push / pull

Sync session transcripts with the remote.

## push

Push local session commits to the remote:

```bash
git push
```

Report how many commits were pushed. If no remote is configured, tell the user:
```bash
git remote add origin <url>
```

## pull

Pull team sessions from the remote:

```bash
git pull --rebase
```

Report new sessions received. If there are merge conflicts (unlikely with per-session files), advise the user.
