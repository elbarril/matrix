#!/usr/bin/env bash
# Initialize brain/state/ directory structure if it doesn't exist.
#
# Usage:
#   matrix-init-brain-state.sh [--matrix-dir <path>]
#
# Options:
#   --matrix-dir <path>   Path to matrix directory (default: script dir/../..)
#
# Exit codes:
#   0   - Brain state structure initialized (or already exists)
#   1   - Failed to create directories
#   2   - Invalid arguments

set -euo pipefail

MATRIX_DIR=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --matrix-dir)
      MATRIX_DIR="$2"
      shift 2
      ;;
    *)
      echo "ERROR: Unknown option: $1" >&2
      echo "Usage: matrix-init-brain-state.sh [--matrix-dir <path>]" >&2
      exit 2
      ;;
  esac
done

# Default matrix dir: scripts/ -> deus-ex-machina/ -> skills/ -> .agents/ -> matrix root
if [[ -z "$MATRIX_DIR" ]]; then
  # Check if _brain symlink exists in current directory (active project)
  if [[ -L "_brain" ]]; then
    # Use _brain symlink to find matrix root (readlink to get brain path, then go up one level)
    BRAIN_PATH="$(readlink -f _brain)"
    MATRIX_DIR="$(dirname "$BRAIN_PATH")"
  else
    # Fallback to dynamic resolution from script location
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    # Strip trailing slashes to prevent double slash issues in path concatenation
    SCRIPT_DIR="${SCRIPT_DIR%/}"
    MATRIX_DIR="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
  fi
fi

# Strip trailing slashes to prevent double slash issues in path concatenation
MATRIX_DIR="${MATRIX_DIR%/}"

BRAIN_STATE_DIR="$MATRIX_DIR/brain/state"
SESSIONS_DIR="$BRAIN_STATE_DIR/sessions"
WORKSPACE_FILE="$BRAIN_STATE_DIR/workspace.yaml"
ARCHIVE_DIR="$BRAIN_STATE_DIR/work-process-log-archive"

# Create directories if they don't exist
mkdir -p "$SESSIONS_DIR" "$ARCHIVE_DIR" 2>/dev/null || {
  echo "ERROR: Failed to create brain state directories" >&2
  exit 1
}

# Create workspace.yaml if it doesn't exist
if [[ ! -f "$WORKSPACE_FILE" ]]; then
  cat > "$WORKSPACE_FILE" << 'EOF'
# Matrix Workspace State
# Tracks active projects and system state

active_projects: []
last_updated: null
session_count: 0
EOF
fi

# Create checkpoints.jsonl if it doesn't exist
CHECKPOINTS_FILE="$BRAIN_STATE_DIR/checkpoints.jsonl"
if [[ ! -f "$CHECKPOINTS_FILE" ]]; then
  touch "$CHECKPOINTS_FILE"
  chmod 600 "$CHECKPOINTS_FILE"
fi

# Create work-process-log.jsonl if it doesn't exist
LOG_FILE="$BRAIN_STATE_DIR/work-process-log.jsonl"
if [[ ! -f "$LOG_FILE" ]]; then
  touch "$LOG_FILE"
  chmod 600 "$LOG_FILE"
fi

# Brain state structure initialized
echo "OK: Brain state structure initialized"
exit 0
