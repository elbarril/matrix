#!/usr/bin/env bash
# Run all pre-activation checks sequentially.
#
# This script runs all pre-activation validation and initialization scripts
# in the correct order to ensure the Matrix system is ready for activation.
#
# Usage:
#   matrix-pre-activation-checks.sh [--matrix-dir <path>]
#
# Options:
#   --matrix-dir <path>   Path to matrix directory (default: script dir/../..)
#
# Exit codes:
#   0   - All pre-activation checks passed
#   1   - One or more pre-activation checks failed
#   2   - Invalid arguments

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MATRIX_DIR=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --matrix-dir)
      MATRIX_DIR="$2"
      shift 2
      ;;
    *)
      echo "ERROR: Unknown option: $1" >&2
      echo "Usage: matrix-pre-activation-checks.sh [--matrix-dir <path>]" >&2
      exit 2
      ;;
  esac
done

# Default matrix dir: scripts/ -> deus-ex-machina/ -> skills/ -> .devin/ -> matrix root
if [[ -z "$MATRIX_DIR" ]]; then
  # Check if _brain symlink exists in current directory (active project)
  if [[ -L "_brain" ]]; then
    # Use _brain symlink to find matrix root (readlink to get brain path, then go up one level)
    BRAIN_PATH="$(readlink -f _brain)"
    MATRIX_DIR="$(dirname "$BRAIN_PATH")"
  else
    # Fallback to dynamic resolution from script location
    # Strip trailing slashes to prevent double slash issues in path concatenation
    SCRIPT_DIR="${SCRIPT_DIR%/}"
    MATRIX_DIR="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
  fi
fi

# Strip trailing slashes to prevent double slash issues in path concatenation
MATRIX_DIR="${MATRIX_DIR%/}"

# Define script paths
VALIDATE_CONFIG="$SCRIPT_DIR/matrix-validate-config.sh"
VALIDATE_CONTEXT="$SCRIPT_DIR/matrix-validate-context.sh"
VALIDATE_ROUTING="$SCRIPT_DIR/matrix-validate-routing-resources.sh"
INIT_BRAIN_STATE="$SCRIPT_DIR/matrix-init-brain-state.sh"

# Track overall status
OVERALL_STATUS=0
FAILED_CHECKS=()

echo "=== Matrix Pre-Activation Checks ===" >&2
echo "Matrix directory: $MATRIX_DIR" >&2
echo "" >&2

# Run validate-config
echo "[1/4] Validating configuration..." >&2
if "$VALIDATE_CONFIG" --matrix-dir "$MATRIX_DIR"; then
  echo "✓ Configuration validation passed" >&2
else
  echo "✗ Configuration validation failed" >&2
  OVERALL_STATUS=1
  FAILED_CHECKS+=("validate-config")
fi
echo "" >&2

# Run validate-context
echo "[2/4] Validating context..." >&2
if "$VALIDATE_CONTEXT" --matrix-dir "$MATRIX_DIR"; then
  echo "✓ Context validation passed" >&2
else
  echo "✗ Context validation failed" >&2
  OVERALL_STATUS=1
  FAILED_CHECKS+=("validate-context")
fi
echo "" >&2

# Run validate-routing-resources
echo "[3/4] Validating routing resources..." >&2
if "$VALIDATE_ROUTING" --matrix-dir "$MATRIX_DIR"; then
  echo "✓ Routing resources validation passed" >&2
else
  echo "✗ Routing resources validation failed" >&2
  OVERALL_STATUS=1
  FAILED_CHECKS+=("validate-routing-resources")
fi
echo "" >&2

# Run init-brain-state
echo "[4/4] Initializing brain state structure..." >&2
if "$INIT_BRAIN_STATE" --matrix-dir "$MATRIX_DIR"; then
  echo "✓ Brain state initialization passed" >&2
else
  echo "✗ Brain state initialization failed" >&2
  OVERALL_STATUS=1
  FAILED_CHECKS+=("init-brain-state")
fi
echo "" >&2

# Report overall status
if [[ $OVERALL_STATUS -eq 0 ]]; then
  echo "=== All Pre-Activation Checks Passed ===" >&2
  exit 0
else
  echo "=== Pre-Activation Checks Failed ===" >&2
  echo "Failed checks: ${FAILED_CHECKS[*]}" >&2
  exit 1
fi
