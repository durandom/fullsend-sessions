compose := "podman compose"
sessions_env := home_directory() / ".config/fullsend/sessions.env"

[private]
start-viewer runs="./runs":
    AGENTSVIEW_HOST=$(hostname).local AGENTSVIEW_RUNS={{ runs }} {{ compose }} -f compose.yaml up -d
    @echo "AgentsView: http://$(hostname).local:${AGENTSVIEW_PORT:-8081}"

[private]
ensure-podman:
    #!/usr/bin/env bash
    if command -v podman &>/dev/null; then
      if ! podman machine inspect --format '{{"{{.State}}"}}' 2>/dev/null | grep -q running; then
        echo "Starting podman machine..."
        podman machine start
      fi
    fi

# Download fullsend runs from GitHub Actions
fetch:
    ./scripts/fetch-fullsend-runs.sh

# Fetch runs + start AgentsView container
up: ensure-podman fetch
    @just start-viewer

# Import local fullsend run(s) + start AgentsView (only local runs shown)
local dir="": ensure-podman
    ./scripts/import-local-run.sh {{ if dir != "" { dir } else { "" } }}
    @just start-viewer "./runs-local"

# Browse shared team sessions in AgentsView
sessions: ensure-podman
    #!/usr/bin/env bash
    sessions_dir="./sessions"
    if [ -f "{{ sessions_env }}" ]; then
      source "{{ sessions_env }}"
      if [ -n "${FULLSEND_SESSIONS_REPO:-}" ] && [ -d "${FULLSEND_SESSIONS_REPO}/sessions" ]; then
        sessions_dir="${FULLSEND_SESSIONS_REPO}/sessions"
      fi
    fi
    just start-viewer "$sessions_dir"

# Browse shared team sessions directly from S3
sessions-s3: ensure-podman
    #!/usr/bin/env bash
    set -euo pipefail
    AGENTSVIEW_HOST=$(hostname).local \
      {{ compose }} -f compose.yaml -f compose.s3.yaml up -d --pull always --force-recreate
    echo "AgentsView: http://$(hostname).local:${AGENTSVIEW_PORT:-8081}"

# Start AgentsView without fetching (use after manual imports)
viewer: ensure-podman
    @just start-viewer

# Stop AgentsView container
down:
    {{ compose }} -f compose.yaml down -v

# Stop the S3-backed viewer and remove only its derived index
down-s3:
    {{ compose }} -f compose.yaml -f compose.s3.yaml down
    podman volume rm fullsend-sessions_agentsview-s3-data 2>/dev/null || true
