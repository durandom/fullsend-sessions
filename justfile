compose := if `command -v podman 2>/dev/null || true` != "" { "podman compose" } else { "docker compose" }

[private]
start-viewer runs="./runs":
    {{ compose }} -f docker-compose.fullsend.yaml up -d
    @echo "AgentsView: http://$(hostname).local:${AGENTSVIEW_PORT:-8081}"

# Download fullsend runs from GitHub Actions
fetch:
    ./scripts/fetch-fullsend-runs.sh

# Fetch runs + start AgentsView container
up: fetch
    @just start-viewer

# Import local fullsend run(s) + start AgentsView (only local runs shown)
local dir="":
    ./scripts/import-local-run.sh {{ if dir != "" { dir } else { "" } }}
    AGENTSVIEW_RUNS=./runs-local {{ compose }} -f docker-compose.fullsend.yaml up -d
    @echo "AgentsView: http://$(hostname).local:${AGENTSVIEW_PORT:-8081}"

# Browse shared team sessions in AgentsView
sessions:
    AGENTSVIEW_RUNS=./sessions {{ compose }} -f docker-compose.fullsend.yaml up -d
    @echo "AgentsView: http://$(hostname).local:${AGENTSVIEW_PORT:-8081}"

# Start AgentsView without fetching (use after manual imports)
viewer:
    @just start-viewer

# Stop AgentsView container
down:
    {{ compose }} -f docker-compose.fullsend.yaml down -v
