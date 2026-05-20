#!/usr/bin/env bash
# Validate activation compliance and write validation report.
#
# Usage:
#   matrix-validate-activation.sh --activation-log <log_content> --user-request <request> [--matrix-dir <path>]
#
# Required:
#   --activation-log <log>   Full activation log content
#   --user-request <req>    Original user request
#
# Optional:
#   --matrix-dir <path>     Path to matrix directory (default: script dir/../..)
#
# Exit codes:
#   0   - Activation is compliant
#   1   - Activation is non-compliant
#   2   - Invalid arguments

set -euo pipefail

ACTIVATION_LOG=""
USER_REQUEST=""
MATRIX_DIR=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --activation-log)
      ACTIVATION_LOG="$2"
      shift 2
      ;;
    --user-request)
      USER_REQUEST="$2"
      shift 2
      ;;
    --matrix-dir)
      MATRIX_DIR="$2"
      shift 2
      ;;
    *)
      echo "ERROR: Unknown option: $1" >&2
      exit 2
      ;;
  esac
done

# Validate required fields
if [[ -z "$ACTIVATION_LOG" ]] || [[ -z "$USER_REQUEST" ]]; then
  echo "ERROR: Missing required fields: --activation-log, --user-request" >&2
  exit 2
fi

# Default matrix dir: scripts/ -> deus-ex-machina/ -> skills/ -> .devin/ -> matrix root
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

VALIDATION_REPORT_FILE="$MATRIX_DIR/brain/state/validation-report.yaml"

# Required enforced steps from activation protocol
REQUIRED_STEPS=(
  "Loaded configuration"
  "Loaded context"
  "Loaded routing resources"
  "Greeted user"
  "Awaiting user request"
)

MISSING_STEPS=()

# Check if each required step is in the log
for step in "${REQUIRED_STEPS[@]}"; do
  if ! echo "$ACTIVATION_LOG" | grep -q "$step"; then
    MISSING_STEPS+=("$step")
  fi
done

# Determine compliance status
if [[ ${#MISSING_STEPS[@]} -eq 0 ]]; then
  ACTIVATION_STATUS="compliant"
else
  ACTIVATION_STATUS="non-compliant"
fi

# Generate timestamp
TIMESTAMP=$(date -Iseconds 2>/dev/null || date +"%Y-%m-%dT%H:%M:%S%z")

# Write validation report
cat > "$VALIDATION_REPORT_FILE" << EOF
timestamp: "$TIMESTAMP"
activation_status: "$ACTIVATION_STATUS"
missing_steps: $(if [[ ${#MISSING_STEPS[@]} -eq 0 ]]; then echo "[]"; else echo "["; for step in "${MISSING_STEPS[@]}"; do echo "  - \"$step\""; done; echo "]"; fi)
activation_log: |
$(echo "$ACTIVATION_LOG" | sed 's/^/  /')
user_request: "$USER_REQUEST"
EOF

# Output result
if [[ "$ACTIVATION_STATUS" == "compliant" ]]; then
  echo "OK: Activation is compliant"
  exit 0
else
  echo "WARNING: Activation is non-compliant. Missing steps:" >&2
  for step in "${MISSING_STEPS[@]}"; do
    echo "  - $step" >&2
  done
  echo "Validation report written to: $VALIDATION_REPORT_FILE" >&2
  exit 1
fi
