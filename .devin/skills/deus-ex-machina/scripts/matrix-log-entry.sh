#!/usr/bin/env bash
# Write log entries to brain/state/work-process-log.yaml with proper format and rotation.
#
# Usage:
#   matrix-log-entry.sh --event-type <type> --status <status> --details <details> [--user-request <request>] [event-specific-fields]
#
# Required:
#   --event-type <type>     Event type (activation_step, routing_decision, specialist_invocation, specialist_completion, checkpoint_write)
#   --status <status>       Status (success, error)
#   --details <details>     Human-readable description
#
# Optional:
#   --user-request <req>    Original user request
#   --step-number <num>     For activation_step events
#   --step-name <name>      For activation_step events
#   --specialists <list>    For routing_decision events (comma-separated)
#   --pattern <name>        For routing_decision events
#   --specialist <name>     For specialist_invocation/completion events
#   --invocation-method <m> For specialist_invocation events
#   --context <ctx>         For specialist_invocation events
#   --outcome <outcome>     For specialist_completion events
#   --findings <summary>    For specialist_completion events
#   --checkpoint-note <n>   For checkpoint_write events
#   --matrix-dir <path>     Path to matrix directory (default: script dir/../..)
#
# Exit codes:
#   0   - Log entry written successfully
#   1   - Failed to write log entry
#   2   - Invalid arguments

set -euo pipefail

EVENT_TYPE=""
STATUS=""
DETAILS=""
USER_REQUEST=""
STEP_NUMBER=""
STEP_NAME=""
SPECIALISTS=""
PATTERN=""
SPECIALIST=""
INVOCATION_METHOD=""
CONTEXT=""
OUTCOME=""
FINDINGS=""
CHECKPOINT_NOTE=""
MATRIX_DIR=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --event-type)
      EVENT_TYPE="$2"
      shift 2
      ;;
    --status)
      STATUS="$2"
      shift 2
      ;;
    --details)
      DETAILS="$2"
      shift 2
      ;;
    --user-request)
      USER_REQUEST="$2"
      shift 2
      ;;
    --step-number)
      STEP_NUMBER="$2"
      shift 2
      ;;
    --step-name)
      STEP_NAME="$2"
      shift 2
      ;;
    --specialists)
      SPECIALISTS="$2"
      shift 2
      ;;
    --pattern)
      PATTERN="$2"
      shift 2
      ;;
    --specialist)
      SPECIALIST="$2"
      shift 2
      ;;
    --invocation-method)
      INVOCATION_METHOD="$2"
      shift 2
      ;;
    --context)
      CONTEXT="$2"
      shift 2
      ;;
    --outcome)
      OUTCOME="$2"
      shift 2
      ;;
    --findings)
      FINDINGS="$2"
      shift 2
      ;;
    --checkpoint-note)
      CHECKPOINT_NOTE="$2"
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
if [[ -z "$EVENT_TYPE" ]] || [[ -z "$STATUS" ]] || [[ -z "$DETAILS" ]]; then
  echo "ERROR: Missing required fields: --event-type, --status, --details" >&2
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

LOG_FILE="$MATRIX_DIR/brain/state/work-process-log.yaml"
ARCHIVE_DIR="$MATRIX_DIR/brain/state/work-process-log-archive"

# Generate timestamp
TIMESTAMP=$(date -Iseconds 2>/dev/null || date +"%Y-%m-%dT%H:%M:%S%z")

# Start building log entry
LOG_ENTRY="  - timestamp: \"$TIMESTAMP\"\n"
LOG_ENTRY+="    event_type: \"$EVENT_TYPE\"\n"
LOG_ENTRY+="    status: \"$STATUS\"\n"
LOG_ENTRY+="    details: \"$DETAILS\"\n"
LOG_ENTRY+="    user_request: ${USER_REQUEST:-null}\n"

# Add event-specific fields
case "$EVENT_TYPE" in
  activation_step)
    if [[ -n "$STEP_NUMBER" ]]; then
      LOG_ENTRY+="    step_number: $STEP_NUMBER\n"
    fi
    if [[ -n "$STEP_NAME" ]]; then
      LOG_ENTRY+="    step_name: \"$STEP_NAME\"\n"
    fi
    ;;
  routing_decision)
    if [[ -n "$SPECIALISTS" ]]; then
      # Convert comma-separated list to YAML array
      SPECIALIST_ARRAY=$(echo "$SPECIALISTS" | sed 's/,/, /g' | sed 's/\([^,]*\)/"\1"/g')
      LOG_ENTRY+="    specialists_detected: [$SPECIALIST_ARRAY]\n"
    fi
    if [[ -n "$PATTERN" ]]; then
      LOG_ENTRY+="    pattern_selected: \"$PATTERN\"\n"
    fi
    ;;
  specialist_invocation)
    if [[ -n "$SPECIALIST" ]]; then
      LOG_ENTRY+="    specialist: \"$SPECIALIST\"\n"
    fi
    if [[ -n "$INVOCATION_METHOD" ]]; then
      LOG_ENTRY+="    invocation_method: \"$INVOCATION_METHOD\"\n"
    fi
    if [[ -n "$CONTEXT" ]]; then
      LOG_ENTRY+="    context_passed: \"$CONTEXT\"\n"
    fi
    ;;
  specialist_completion)
    if [[ -n "$SPECIALIST" ]]; then
      LOG_ENTRY+="    specialist: \"$SPECIALIST\"\n"
    fi
    if [[ -n "$OUTCOME" ]]; then
      LOG_ENTRY+="    outcome: \"$OUTCOME\"\n"
    fi
    if [[ -n "$FINDINGS" ]]; then
      LOG_ENTRY+="    findings_summary: \"$FINDINGS\"\n"
    fi
    ;;
  checkpoint_write)
    if [[ -n "$CHECKPOINT_NOTE" ]]; then
      LOG_ENTRY+="    checkpoint_note: \"$CHECKPOINT_NOTE\"\n"
    fi
    ;;
esac

# Ensure log file exists
if [[ ! -f "$LOG_FILE" ]]; then
  echo "entries: []" > "$LOG_FILE"
fi

# Check log rotation (keep last 100 entries)
ENTRY_COUNT=$(grep -c "^  - timestamp:" "$LOG_FILE" 2>/dev/null || echo "0")
if [[ $ENTRY_COUNT -ge 100 ]]; then
  # Archive old logs
  mkdir -p "$ARCHIVE_DIR"
  ARCHIVE_DATE=$(date +"%Y-%m-%d")
  ARCHIVE_FILE="$ARCHIVE_DIR/work-process-log-$ARCHIVE_DATE.yaml"
  
  # Move entries beyond last 100 to archive
  # This is a simple rotation - move all but last 100
  head -n $((100 + 1)) "$LOG_FILE" > "${LOG_FILE}.tmp"
  tail -n +$((100 + 2)) "$LOG_FILE" >> "$ARCHIVE_FILE"
  mv "${LOG_FILE}.tmp" "$LOG_FILE"
fi

# Append new entry
# Remove the closing "[]" and add entry, then close again
sed -i '$ d' "$LOG_FILE" 2>/dev/null || true
echo -e "$LOG_ENTRY" >> "$LOG_FILE"
echo "]" >> "$LOG_FILE"

echo "OK: Log entry written"
exit 0
