---
name: meeting-transcripts
description: Download Google Meet transcripts from calendar events using gog CLI. Use when asked to fetch, download, sync, or check meeting transcripts.
---

## Purpose

Fetch Google Meet transcripts attached to calendar events and save them locally to `meetings/transcripts/`.

## Prerequisites

- `gog` CLI installed and authenticated (`gog auth list --check` must show `calendar` and `drive` scopes)
- If auth fails with `insufficientPermissions`, the user must run `gog auth login` interactively to grant scopes

## Workflow

### 1. Find events with transcripts

Search for calendar events in the desired time range. Transcripts are Google Docs attached to the event.

```bash
gog cal events list --from "<start-date>" --to "<end-date>" --query "<meeting name>" --json
```

Useful time shortcuts: `--today`, `--tomorrow`, `--days=N`

Look for events that have an `attachments` array — each attachment with `mimeType: "application/vnd.google-apps.document"` and a title containing "Transcript" is a meeting transcript. Extract the `fileId` from each.

Events without `attachments` have no transcript (meeting hasn't happened yet, or transcription was off).

### 2. Download transcripts

Export each Google Doc as plain text using its `fileId`:

```bash
gog docs export <fileId> --format txt --out meetings/transcripts/<date>-<slug>.txt
```

**Naming convention**: `YYYY-MM-DD-transcript[-N].txt` where N is a counter when multiple transcripts exist for the same date. Derive the date from the event's `start.dateTime`.

Supported formats: `txt`, `md`, `pdf`, `docx`, `html`

### 3. Verify

After downloading, check file sizes — transcripts under 1 KB are likely fragments (e.g., from a briefly started/restarted recording) and should be noted to the user.

```bash
wc -l meetings/transcripts/*.txt
```

## Browsing all calendars

To find meetings across all calendars (not just primary):

```bash
gog cal events list --all --from "<date>" --to "<date>" --json
```

## Example: fetch this week's transcripts for a recurring meeting

```bash
# Monday = start of week
gog cal events list --from "2026-07-06" --to "2026-07-11" --query "standup" --json
# Parse attachments, then for each fileId:
gog docs export <fileId> --format txt --out meetings/transcripts/2026-07-07-standup.txt
```

## Output directory

All transcripts go to `meetings/transcripts/` relative to the project root. Create the directory if it doesn't exist:

```bash
mkdir -p meetings/transcripts
```
