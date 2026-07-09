#!/usr/bin/env bash
# fs-sessions — share Claude Code sessions with your team.
#
# Discovers local sessions, shows the most recent ones, and offers
# to copy+commit+push the selected session to the shared repo.
#
# Usage:
#   fs-sessions              # interactive — pick from recent sessions
#   fs-sessions --last       # share the most recent session, no prompt
#   fs-sessions --list       # list recent sessions and exit
#
# Prerequisites: jq, git

set -euo pipefail

CLAUDE_PROJECTS_DIR="${HOME}/.claude/projects"
CONFIG_FILE="${HOME}/.config/fullsend/sessions.env"

# Load repo path from config; fall back to deriving from script location
if [ -f "$CONFIG_FILE" ]; then
  # shellcheck source=/dev/null
  . "$CONFIG_FILE"
fi
if [ -n "${FULLSEND_SESSIONS_REPO:-}" ] && [ -d "$FULLSEND_SESSIONS_REPO" ]; then
  SESSIONS_REPO="$FULLSEND_SESSIONS_REPO"
else
  SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
  SESSIONS_REPO="$(cd "$SCRIPT_DIR/../../.." && pwd)"
fi
SESSIONS_DIR="${SESSIONS_REPO}/sessions"

MAX_DISPLAY=20

# --- Helpers ----------------------------------------------------------------

die() { echo "error: $*" >&2; exit 1; }

get_session_title() {
  jq -r 'select(.type == "ai-title") | .aiTitle' "$1" 2>/dev/null | tail -1 || true
}

get_session_id() {
  basename "$1" .jsonl
}

# Portable stat: detect macOS vs Linux once
if stat -f '%m' /dev/null &>/dev/null; then
  STAT_FMT=(-f '%m %N')
else
  STAT_FMT=(-c '%Y %n')
fi

get_mtime() {
  stat "${STAT_FMT[@]}" "$1" | cut -d' ' -f1
}

format_time() {
  if date -r "$1" '+%Y-%m-%d %H:%M' 2>/dev/null; then return; fi
  date -d "@$1" '+%Y-%m-%d %H:%M' 2>/dev/null || echo "unknown"
}

get_username() {
  git config user.name 2>/dev/null \
    | tr ' ' '-' | tr '[:upper:]' '[:lower:]' \
    || echo "${USER:-unknown}"
}

human_size() {
  local bytes=$1
  if [ "$bytes" -ge 1048576 ]; then
    printf '%dM' $((bytes / 1048576))
  elif [ "$bytes" -ge 1024 ]; then
    printf '%dK' $((bytes / 1024))
  else
    printf '%dB' "$bytes"
  fi
}

# --- Discover sessions ------------------------------------------------------

discover_sessions() {
  find "$CLAUDE_PROJECTS_DIR" -mindepth 2 -maxdepth 2 -name '*.jsonl' -print0 2>/dev/null \
    | xargs -0 stat "${STAT_FMT[@]}" 2>/dev/null \
    | while IFS=' ' read -r mtime path; do
        echo "${mtime}|${path}"
      done \
    | sort -t'|' -k1 -rn \
    | head -"$MAX_DISPLAY"
}

# --- Display sessions -------------------------------------------------------

display_sessions() {
  local lines=("$@")
  local i=1

  printf '\n'
  printf '  %-4s %-40s %-18s %7s %6s %s\n' "#" "PROJECT" "MODIFIED" "SIZE" "MSGS" "TITLE"
  printf '  %-4s %-40s %-18s %7s %6s %s\n' "---" "----------------------------------------" "------------------" "-------" "------" "-----"

  for line in "${lines[@]}"; do
    local mtime jsonl project_dir project title
    IFS='|' read -r mtime jsonl <<< "$line"

    project="$(basename "$(dirname "$jsonl")")"
    local cwd
    cwd="$(jq -r 'select(.cwd != null and .type == "user" and .sessionId != null) | .cwd' "$jsonl" 2>/dev/null | head -1 || true)"
    if [ -n "$cwd" ]; then
      project="$(basename "$(dirname "$cwd")")/$(basename "$cwd")"
    fi

    title="$(get_session_title "$jsonl")"
    [ -z "$title" ] && title="(untitled)"
    [ ${#title} -gt 50 ] && title="${title:0:47}..."

    local ftime fsize msg_count
    ftime="$(format_time "$mtime")"
    fsize="$(human_size "$(wc -c < "$jsonl")")"
    msg_count="$(wc -l < "$jsonl")"

    printf '  %-4s %-40s %-18s %7s %6s %s\n' "[$i]" "$project" "$ftime" "$fsize" "$msg_count" "$title"
    i=$((i + 1))
  done
  printf '\n'
}

# --- Share a session --------------------------------------------------------

share_session() {
  local jsonl="$1"
  local session_id username project_name cwd

  session_id="$(get_session_id "$jsonl")"
  username="$(get_username)"

  cwd="$(jq -r 'select(.cwd != null and .type == "user" and .sessionId != null) | .cwd' "$jsonl" 2>/dev/null | head -1 || true)"
  if [ -n "$cwd" ]; then
    project_name="$(basename "$cwd")"
  else
    project_name="$(basename "$(dirname "$jsonl")")"
    project_name="${project_name#-}"
  fi

  local dest_dir="${SESSIONS_DIR}/${username}_${project_name}"
  local dest_file="${dest_dir}/${session_id}.jsonl"

  local verb="add"
  if [ -f "$dest_file" ]; then
    local src_size dest_size
    src_size="$(wc -c < "$jsonl")"
    dest_size="$(tail -n +2 "$dest_file" | wc -c)"
    if [ "$src_size" -eq "$dest_size" ]; then
      echo "Unchanged: ${username}_${project_name}/${session_id}.jsonl"
      return 0
    fi
    verb="update"
  fi

  # Build metadata line
  local timestamp
  timestamp="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

  local meta_line
  meta_line="$(jq -nc \
    --arg project "$project_name" \
    --arg user "$username" \
    --arg ts "$timestamp" \
    --arg cwd "/sessions/${username}_${project_name}" \
    '{
      type: "user",
      timestamp: $ts,
      message: { content: ("[Session: \($project)] by \($user)\nProject: \($cwd)") },
      cwd: $cwd
    }'
  )"

  mkdir -p "$dest_dir"
  { echo "$meta_line"; cat "$jsonl"; } > "$dest_file"

  echo "Copied → sessions/${username}_${project_name}/${session_id}.jsonl"

  # Commit
  git -C "$SESSIONS_REPO" add "sessions/${username}_${project_name}/${session_id}.jsonl"
  git -C "$SESSIONS_REPO" commit -q -m "feat: ${verb} session ${username}/${project_name}/${session_id}"
  echo "Committed."

  # Push
  printf 'Push to remote? [Y/n] '
  read -r answer < /dev/tty
  if [ -z "$answer" ] || [[ "$answer" =~ ^[Yy] ]]; then
    git -C "$SESSIONS_REPO" push
    echo "Pushed."
  else
    echo "Skipped push. Run 'git push' in the sessions repo later."
  fi
}

# --- Main -------------------------------------------------------------------

main() {
  command -v jq >/dev/null 2>&1 || die "jq is required"
  [ -d "$CLAUDE_PROJECTS_DIR" ] || die "Claude projects dir not found: $CLAUDE_PROJECTS_DIR"

  local mode="interactive"
  case "${1:-}" in
    --last) mode="last" ;;
    --list) mode="list" ;;
    --help|-h) echo "Usage: fs-sessions [--last | --list | --help]"; exit 0 ;;
  esac

  echo "Scanning sessions..."
  local lines=()
  while IFS= read -r line; do
    [ -n "$line" ] && lines+=("$line")
  done < <(discover_sessions)

  if [ ${#lines[@]} -eq 0 ]; then
    die "no Claude Code sessions found in $CLAUDE_PROJECTS_DIR"
  fi

  if [ "$mode" = "list" ]; then
    display_sessions "${lines[@]}"
    exit 0
  fi

  if [ "$mode" = "last" ]; then
    local jsonl
    IFS='|' read -r _ jsonl <<< "${lines[0]}"
    share_session "$jsonl"
    exit 0
  fi

  # Interactive mode
  display_sessions "${lines[@]}"

  printf '  Share which session? [1] '
  read -r choice < /dev/tty
  [ -z "$choice" ] && choice=1

  if ! [[ "$choice" =~ ^[0-9]+$ ]] || [ "$choice" -lt 1 ] || [ "$choice" -gt ${#lines[@]} ]; then
    die "invalid choice: $choice"
  fi

  local selected="${lines[$((choice - 1))]}"
  local jsonl
  IFS='|' read -r _ jsonl <<< "$selected"

  share_session "$jsonl"
}

main "$@"
