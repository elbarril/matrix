#!/usr/bin/env bash
# Validate that routing resources exist.
#
# Usage:
#   matrix-validate-routing-resources.sh [--matrix-dir <path>]
#
# Options:
#   --matrix-dir <path>   Path to matrix directory (default: script dir/../..)
#
# Exit codes:
#   0   - All routing resources exist
#   1   - One or more routing resources missing
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
      echo "Usage: matrix-validate-routing-resources.sh [--matrix-dir <path>]" >&2
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
    MATRIX_DIR="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
  fi
fi

# Strip trailing slashes to prevent double slash issues in path concatenation
MATRIX_DIR="${MATRIX_DIR%/}"

# SCRIPT_DIR is still needed for routing resources (relative to script location)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Strip trailing slashes to prevent double slash issues in path concatenation
SCRIPT_DIR="${SCRIPT_DIR%/}"
ROUTING_DIR="$SCRIPT_DIR/../resources/assets/routing"

# Check if routing directory exists
if [[ ! -d "$ROUTING_DIR" ]]; then
  echo "ERROR: Routing directory not found: $ROUTING_DIR" >&2
  exit 1
fi

# Required routing resource files
REQUIRED_FILES=(
  "specialist-triggers.md"
  "coordination-patterns.md"
  "routing-rules.md"
  "rules/specialist-specific-rules.md"
)

MISSING_FILES=()

for file in "${REQUIRED_FILES[@]}"; do
  FILE_PATH="$ROUTING_DIR/$file"
  if [[ ! -f "$FILE_PATH" ]]; then
    MISSING_FILES+=("$file")
  fi
done

# Report missing files
if [[ ${#MISSING_FILES[@]} -gt 0 ]]; then
  echo "ERROR: Missing routing resources:" >&2
  for file in "${MISSING_FILES[@]}"; do
    echo "  - $ROUTING_DIR/$file" >&2
  done
  exit 1
fi

# Required specialist agent files
REQUIRED_AGENTS=(
  "oracle"
  "sion"
  "smith"
  "morpheus"
  "trinity"
  "architect"
  "sentinel"
  "keymaker"
  "wachowski"
)

MISSING_AGENTS=()

for agent in "${REQUIRED_AGENTS[@]}"; do
  AGENT_FILE="$MATRIX_DIR/.agents/agents/$agent/AGENT.md"
  if [[ ! -f "$AGENT_FILE" ]]; then
    MISSING_AGENTS+=("$agent")
  fi
done

if [[ ${#MISSING_AGENTS[@]} -gt 0 ]]; then
  echo "ERROR: Missing specialist agent files (routing will fail):" >&2
  for agent in "${MISSING_AGENTS[@]}"; do
    echo "  - .agents/agents/$agent/AGENT.md" >&2
  done
  exit 1
fi

# All routing resources and specialist agents exist
echo "OK: All routing resources exist"
exit 0
