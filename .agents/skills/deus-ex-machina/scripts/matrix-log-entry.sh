#!/usr/bin/env bash
# Write log entries to brain/state/work-process-log.jsonl with proper format and rotation.

set -euo pipefail

EVENT_TYPE=""
STATUS=""
DETAILS=""
LEVEL=""
USER_REQUEST=""
STEP_NUMBER=""
STEP_NAME=""
SPECIALISTS=""
PATTERN=""
SPECIALIST=""
INVOCATION_METHOD=""
CONTEXT=""
MESSAGE=""
OUTCOME=""
FINDINGS=""
RESPONSE=""
DURATION=""
CHECKPOINT_NOTE=""
MATRIX_DIR=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --event-type) EVENT_TYPE="$2"; shift 2 ;;
    --status) STATUS="$2"; shift 2 ;;
    --details) DETAILS="$2"; shift 2 ;;
    --level) LEVEL="$2"; shift 2 ;;
    --user-request) USER_REQUEST="$2"; shift 2 ;;
    --step-number) STEP_NUMBER="$2"; shift 2 ;;
    --step-name) STEP_NAME="$2"; shift 2 ;;
    --specialists) SPECIALISTS="$2"; shift 2 ;;
    --pattern) PATTERN="$2"; shift 2 ;;
    --specialist) SPECIALIST="$2"; shift 2 ;;
    --invocation-method) INVOCATION_METHOD="$2"; shift 2 ;;
    --context) CONTEXT="$2"; shift 2 ;;
    --message) MESSAGE="$2"; shift 2 ;;
    --outcome) OUTCOME="$2"; shift 2 ;;
    --findings) FINDINGS="$2"; shift 2 ;;
    --response) RESPONSE="$2"; shift 2 ;;
    --duration) DURATION="$2"; shift 2 ;;
    --checkpoint-note) CHECKPOINT_NOTE="$2"; shift 2 ;;
    --matrix-dir) MATRIX_DIR="$2"; shift 2 ;;
    *)
      echo "ERROR: Unknown option: $1" >&2
      exit 2
      ;;
  esac
done

if [[ -z "$EVENT_TYPE" ]] || [[ -z "$STATUS" ]] || [[ -z "$DETAILS" ]]; then
  echo "ERROR: Missing required fields: --event-type, --status, --details" >&2
  exit 2
fi

declare -A LOG_LEVEL_VALUES=( ["ERROR"]=0 ["WARNING"]=1 ["INFO"]=2 ["DEBUG"]=3 ["TRACE"]=4 )
declare -A DEFAULT_EVENT_LEVELS=( ["activation"]="INFO" ["activation_step"]="DEBUG" ["checkpoint_write"]="DEBUG" ["checkpoint"]="DEBUG" ["routing_decision"]="INFO" ["specialist_invocation"]="INFO" ["specialist_completion"]="INFO" ["specialist_execution"]="INFO" ["problem"]="WARNING" ["validation"]="WARNING" ["error"]="ERROR" )

if [[ -z "$LEVEL" ]]; then LEVEL="${DEFAULT_EVENT_LEVELS[$EVENT_TYPE]:-INFO}"; fi
if [[ -z "${LOG_LEVEL_VALUES[$LEVEL]:-}" ]]; then
  echo "ERROR: Invalid log level: $LEVEL" >&2
  exit 2
fi

LOCK_TIMEOUT=30
LOCK_FD=-1
acquire_lock() {
  local lock_file="$1"
  exec {LOCK_FD}>"$lock_file"
  if ! flock -w "$LOCK_TIMEOUT" "$LOCK_FD"; then
    echo "ERROR: Failed to acquire lock" >&2
    return 1
  fi
  return 0
}
release_lock() {
  if [[ $LOCK_FD -ne -1 ]]; then
    flock -u "$LOCK_FD"
    exec {LOCK_FD}>&-
    LOCK_FD=-1
  fi
}

if [[ -z "$MATRIX_DIR" ]]; then
  if [[ -L "_brain" ]]; then
    BRAIN_PATH="$(readlink -f _brain)"
    MATRIX_DIR="$(dirname "$BRAIN_PATH")"
  else
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    MATRIX_DIR="$(cd "${SCRIPT_DIR%/}/../../../.." && pwd)"
  fi
fi
MATRIX_DIR="${MATRIX_DIR%/}"

CONFIG_FILE="$MATRIX_DIR/brain/config.yaml"
CONFIGURED_LOG_LEVEL="INFO"
if [[ -f "$CONFIG_FILE" ]]; then
  CONFIGURED_LOG_LEVEL=$(grep -E '^log_level:' "$CONFIG_FILE" 2>/dev/null | sed 's/log_level:[[:space:]]*//' | tr -d '"' | tr -d "'" || echo "INFO")
  if [[ -z "${LOG_LEVEL_VALUES[$CONFIGURED_LOG_LEVEL]:-}" ]]; then CONFIGURED_LOG_LEVEL="INFO"; fi
fi

if [[ ${LOG_LEVEL_VALUES[$LEVEL]} -gt ${LOG_LEVEL_VALUES[$CONFIGURED_LOG_LEVEL]} ]]; then
  exit 0
fi

LOG_FILE="$MATRIX_DIR/brain/state/work-process-log.jsonl"
ARCHIVE_DIR="$MATRIX_DIR/brain/state/work-process-log-archive"
LOCK_FILE="$MATRIX_DIR/brain/state/work-process-log.lock"

# Fast Exact Redundancy Check
TIMESTAMP=$(date -Iseconds 2>/dev/null || date +"%Y-%m-%dT%H:%M:%S%z")

LOG_ENTRY=$(jq -n -c \
  --arg ts "$TIMESTAMP" \
  --arg type "$EVENT_TYPE" \
  --arg lvl "$LEVEL" \
  --arg st "$STATUS" \
  --arg det "$DETAILS" \
  --arg req "${USER_REQUEST:-}" \
  --arg num "${STEP_NUMBER:-}" \
  --arg name "${STEP_NAME:-}" \
  --arg specs "${SPECIALISTS:-}" \
  --arg pat "${PATTERN:-}" \
  --arg spec "${SPECIALIST:-}" \
  --arg inv "${INVOCATION_METHOD:-}" \
  --arg ctx "${CONTEXT:-}" \
  --arg msg "${MESSAGE:-}" \
  --arg out "${OUTCOME:-}" \
  --arg fnd "${FINDINGS:-}" \
  --arg rsp "${RESPONSE:-}" \
  --arg dur "${DURATION:-}" \
  --arg note "${CHECKPOINT_NOTE:-}" \
  '{
      timestamp: $ts,
      event_type: $type,
      level: $lvl,
      status: $st,
      details: $det
  }
  + (if $req != "" then {user_request: $req} else {} end)
  + (if $num != "" then {step_number: ($num|tonumber? // $num)} else {} end)
  + (if $name != "" then {step_name: $name} else {} end)
  + (if $specs != "" then {specialists_detected: ($specs | split(",") | map(sub("^\\s+"; "") | sub("\\s+$"; "")))} else {} end)
  + (if $pat != "" then {pattern_selected: $pat} else {} end)
  + (if $spec != "" then {specialist: $spec} else {} end)
  + (if $inv != "" then {invocation_method: $inv} else {} end)
  + (if $ctx != "" then {context_passed: $ctx} else {} end)
  + (if $msg != "" then {message_summary: $msg} else {} end)
  + (if $out != "" then {outcome: $out} else {} end)
  + (if $fnd != "" then {findings_summary: $fnd} else {} end)
  + (if $rsp != "" then {response_summary: $rsp} else {} end)
  + (if $dur != "" then {duration_seconds: ($dur|tonumber? // $dur)} else {} end)
  + (if $note != "" then {checkpoint_note: $note} else {} end)
')

trap 'release_lock' EXIT
if ! acquire_lock "$LOCK_FILE"; then exit 1; fi

echo "$LOG_ENTRY" >> "$LOG_FILE"
chmod 600 "$LOG_FILE"

ENTRY_COUNT=$(wc -l < "$LOG_FILE" 2>/dev/null || echo "0")
if [[ $ENTRY_COUNT -gt 1000 ]]; then
  mkdir -p "$ARCHIVE_DIR"
  chmod 700 "$ARCHIVE_DIR"
  ARCHIVE_DATE=$(date +"%Y-%m-%d")
  ARCHIVE_FILE="$ARCHIVE_DIR/work-process-log-$ARCHIVE_DATE.jsonl"
  
  head -n -100 "$LOG_FILE" >> "$ARCHIVE_FILE"
  chmod 600 "$ARCHIVE_FILE"
  
  tail -n 100 "$LOG_FILE" > "${LOG_FILE}.tmp"
  mv "${LOG_FILE}.tmp" "$LOG_FILE"
  chmod 600 "$LOG_FILE"
fi

echo "OK: Log entry written"

exit 0
