#!/usr/bin/env bash
# Validate brain/config.yaml exists and is valid YAML.
#
# Usage:
#   matrix-validate-config.sh [--matrix-dir <path>]
#
# Options:
#   --matrix-dir <path>   Path to matrix directory (default: script dir/../..)
#
# Exit codes:
#   0   - Config exists and is valid YAML
#   1   - Config file missing or invalid
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
      echo "Usage: matrix-validate-config.sh [--matrix-dir <path>]" >&2
      exit 2
      ;;
  esac
done

# Default matrix dir: scripts/ -> deus-ex-machina/ -> skills/ -> .agents/ -> matrix root
if [[ -z "$MATRIX_DIR" ]]; then
  # Check if _brain symlink exists in current directory (active project)
  if [[ -L "_brain" ]]; then
    # Use _brain symlink for path resolution (portable access from active projects)
    CONFIG_FILE="_brain/config.yaml"
  else
    # Fallback to dynamic resolution from script location
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    # Strip trailing slashes to prevent double slash issues in path concatenation
    SCRIPT_DIR="${SCRIPT_DIR%/}"
    MATRIX_DIR="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
    # Strip trailing slashes to prevent double slash issues in path concatenation
    MATRIX_DIR="${MATRIX_DIR%/}"
    CONFIG_FILE="$MATRIX_DIR/brain/config.yaml"
  fi
else
  # Strip trailing slashes to prevent double slash issues in path concatenation
  MATRIX_DIR="${MATRIX_DIR%/}"
  CONFIG_FILE="$MATRIX_DIR/brain/config.yaml"
fi

# Check if config file exists
if [[ ! -f "$CONFIG_FILE" ]]; then
  echo "ERROR: Config file not found: $CONFIG_FILE" >&2
  exit 1
fi

# Validate YAML by attempting to parse it
# Using python3 if available, otherwise basic check
if command -v python3 >/dev/null 2>&1; then
  if ! python3 -c "import yaml; yaml.safe_load(open('$CONFIG_FILE'))" 2>/dev/null; then
    echo "ERROR: Config file is not valid YAML: $CONFIG_FILE" >&2
    exit 1
  fi
else
  # Fallback: basic syntax check (not comprehensive)
  # Check for common YAML syntax errors
  if grep -qE '^\s*-\s*$' "$CONFIG_FILE"; then
    # Allow list items
    :
  fi
  # Check for tabs (YAML forbids tabs for indentation)
  if grep -q $'\t' "$CONFIG_FILE"; then
    echo "ERROR: Config file contains tabs (invalid in YAML): $CONFIG_FILE" >&2
    exit 1
  fi
fi

# Config is valid
echo "OK: Config file exists and is valid YAML"
exit 0
