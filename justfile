compose := "podman compose"
agentsview_data := env_var_or_default("AGENTSVIEW_DATA", home_directory() / ".local/share/fullsend-agentsview")
fs := "./skills/fs-sessions/scripts/fs-sessions"

[private]
ensure-podman:
    #!/usr/bin/env bash
    if command -v podman &>/dev/null; then
      if ! podman machine inspect --format '{{"{{.State}}"}}' 2>/dev/null | grep -q running; then
        echo "Starting podman machine..."
        podman machine start
      fi
    fi

# Start the S3-backed AgentsView container from its private runtime directory
up: ensure-podman
    #!/usr/bin/env bash
    set -euo pipefail
    test -f "{{ agentsview_data }}/config.toml" || {
      echo "error: missing {{ agentsview_data }}/config.toml" >&2
      echo "Use the agentsview skill to create the private runtime configuration." >&2
      exit 1
    }
    AGENTSVIEW_DATA="{{ agentsview_data }}" AGENTSVIEW_HOST=$(hostname).local \
      {{ compose }} -f compose.yaml up -d --pull always
    echo "AgentsView: http://$(hostname).local:${AGENTSVIEW_PORT:-8081}"

# Download recent Fullsend artifacts and upload converted sessions to S3
fullsend since="7d":
    {{ fs }} fullsend import --since {{ since }}

# Preview recent Fullsend imports without writing S3
fullsend-dry-run since="7d":
    {{ fs }} fullsend import --since {{ since }} --dry-run

# One-time import of an old rhdh-fullsend artifact cache
fullsend-cache cache dry_run="true":
    {{ fs }} fullsend import --cache-dir "{{ cache }}" {{ if dry_run == "true" { "--dry-run" } else { "" } }}

# Stop AgentsView while preserving its private runtime index
down:
    AGENTSVIEW_DATA="{{ agentsview_data }}" {{ compose }} -f compose.yaml down
