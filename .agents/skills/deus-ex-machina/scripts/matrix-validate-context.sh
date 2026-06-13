#!/usr/bin/env bash
# Validate .context.yaml exists and has active project set.
#
# Usage:
#   matrix-validate-context.sh [--matrix-dir <path>]
#
# Options:
#   --matrix-dir <path>   Path to matrix directory (default: script dir/../..)
#
# Exit codes:
#   0   - Context exists and active_project is set (or in Matrix workspace mode)
#   1   - Context file missing or active_project is null (when not in Matrix workspace)
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
      echo "Usage: matrix-validate-context.sh [--matrix-dir <path>]" >&2
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

CONTEXT_FILE="$MATRIX_DIR/.context.yaml"

# Check if context file exists
if [[ ! -f "$CONTEXT_FILE" ]]; then
  echo "ERROR: Context file not found: $CONTEXT_FILE" >&2
  exit 1
fi

# Matrix Workspace Mode: Check if current working directory is Matrix workspace
# If in Matrix workspace, active_project can be null - we enter Matrix workspace mode
CURRENT_DIR="$(pwd)"
if [[ "$CURRENT_DIR" == "$MATRIX_DIR" ]]; then
  echo "OK: Matrix workspace mode detected - context validation skipped (working in Matrix system root)"
  exit 0
fi

# Check if active_project is set (not null or empty)
ACTIVE_PROJECT=$(grep "^active_project:" "$CONTEXT_FILE" | sed 's/active_project:[[:space:]]*//' || echo "")
if [[ "$ACTIVE_PROJECT" == "null" ]] || [[ -z "$ACTIVE_PROJECT" ]]; then
  echo "ERROR: active_project is not set in context file" >&2
  exit 1
fi

# Context is valid
echo "OK: Context file exists and active_project is set to: $ACTIVE_PROJECT"
exit 0
