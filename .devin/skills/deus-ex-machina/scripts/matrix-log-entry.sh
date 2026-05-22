#!/usr/bin/env bash
# Write log entries to brain/state/work-process-log.yaml with proper format and rotation.
#
# Usage:
#   matrix-log-entry.sh --event-type <type> --status <status> --details <details> [--level <level>] [--user-request <request>] [event-specific-fields]
#
# Required:
#   --event-type <type>     Event type (activation, activation_step, routing_decision, specialist_invocation, specialist_completion, specialist_execution, checkpoint_write)
#   --status <status>       Status (success, error)
#   --details <details>     Human-readable description
#
# Optional:
#   --level <lvl>           Log level (ERROR, WARNING, INFO, DEBUG, TRACE). Default: INFO
#   --user-request <req>    Original user request
#   --step-number <num>     For activation_step events (deprecated - use activation instead)
#   --step-name <name>      For activation_step events (deprecated - use activation instead)
#   --specialists <list>    For routing_decision events (comma-separated)
#   --pattern <name>        For routing_decision events
#   --specialist <name>     For specialist_invocation/completion/execution events
#   --invocation-method <m> For specialist_invocation events
#   --context <ctx>         For specialist_invocation events
#   --message <msg>         For specialist_invocation events (message_summary)
#   --outcome <outcome>     For specialist_completion/execution events
#   --findings <summary>    For specialist_completion/execution events
#   --response <resp>       For specialist_completion events (response_summary)
#   --duration <seconds>    For specialist_execution events
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
    --level)
      LEVEL="$2"
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
    --message)
      MESSAGE="$2"
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
    --response)
      RESPONSE="$2"
      shift 2
      ;;
    --duration)
      DURATION="$2"
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

# Log level configuration
# Level hierarchy (lower number = higher priority):
# ERROR=0, WARNING=1, INFO=2, DEBUG=3, TRACE=4
declare -A LOG_LEVEL_VALUES=(
  ["ERROR"]=0
  ["WARNING"]=1
  ["INFO"]=2
  ["DEBUG"]=3
  ["TRACE"]=4
)

# Default log level mapping by event type
# If --level is not specified, assign based on event type
declare -A DEFAULT_EVENT_LEVELS=(
  ["activation"]="INFO"
  ["activation_step"]="DEBUG"
  ["checkpoint_write"]="DEBUG"
  ["routing_decision"]="INFO"
  ["specialist_invocation"]="INFO"
  ["specialist_completion"]="INFO"
  ["specialist_execution"]="INFO"
  ["problem"]="WARNING"
  ["validation"]="WARNING"
  ["error"]="ERROR"
)

# Set default level if not specified
if [[ -z "$LEVEL" ]]; then
  if [[ -n "${DEFAULT_EVENT_LEVELS[$EVENT_TYPE]:-}" ]]; then
    LEVEL="${DEFAULT_EVENT_LEVELS[$EVENT_TYPE]}"
  else
    LEVEL="INFO"  # Default for unknown event types
  fi
fi

# Validate log level
if [[ -z "${LOG_LEVEL_VALUES[$LEVEL]:-}" ]]; then
  echo "ERROR: Invalid log level: $LEVEL. Valid levels: ERROR, WARNING, INFO, DEBUG, TRACE" >&2
  exit 2
fi

# Centralized YAML field sanitization function
# Sanitizes user-controlled input to prevent YAML injection attacks
sanitize_yaml_field() {
  local input="$1"
  # Return empty string if input is null/empty
  if [[ -z "$input" ]]; then
    echo ""
    return
  fi
  # Remove control characters (except tab, newline) - these can break YAML parsing
  input=$(echo "$input" | sed 's/[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]//g')
  # Limit to 1000 characters to prevent DoS
  input="${input:0:1000}"
  # Remove newlines FIRST (before escaping) to keep values on single line
  input=$(echo "$input" | tr -d '\n' | tr -d '\r')
  # Escape only what's necessary for YAML double-quoted strings
  # Backslashes must be escaped first
  input=$(echo "$input" | sed 's/\\/\\\\/g')
  # Escape double quotes
  input=$(echo "$input" | sed 's/"/\\"/g')
  # Remove potential YAML document start/end markers that could break structure
  input=$(echo "$input" | sed 's/^---//g' | sed 's/^\.\.\.//g')
  echo "$input"
}

# Sanitize ALL user-controlled input fields
if [[ -n "$USER_REQUEST" ]]; then
  USER_REQUEST=$(sanitize_yaml_field "$USER_REQUEST")
fi
if [[ -n "$DETAILS" ]]; then
  DETAILS=$(sanitize_yaml_field "$DETAILS")
fi
if [[ -n "$CONTEXT" ]]; then
  CONTEXT=$(sanitize_yaml_field "$CONTEXT")
fi
if [[ -n "$STEP_NAME" ]]; then
  STEP_NAME=$(sanitize_yaml_field "$STEP_NAME")
fi
if [[ -n "$PATTERN" ]]; then
  PATTERN=$(sanitize_yaml_field "$PATTERN")
fi
if [[ -n "$FINDINGS" ]]; then
  FINDINGS=$(sanitize_yaml_field "$FINDINGS")
fi
if [[ -n "$CHECKPOINT_NOTE" ]]; then
  CHECKPOINT_NOTE=$(sanitize_yaml_field "$CHECKPOINT_NOTE")
fi
if [[ -n "$MESSAGE" ]]; then
  MESSAGE=$(sanitize_yaml_field "$MESSAGE")
fi
if [[ -n "$RESPONSE" ]]; then
  RESPONSE=$(sanitize_yaml_field "$RESPONSE")
fi

# yq binary detection with multiple fallbacks
find_yq_binary() {
  # Check environment variable first
  if [[ -n "${YQ_PATH:-}" ]] && [[ -x "$YQ_PATH" ]]; then
    echo "$YQ_PATH"
    return 0
  fi

  # Check common locations in order of preference
  local locations=(
    "$HOME/yq"
    "$HOME/.local/bin/yq"
    "/usr/local/bin/yq"
    "/usr/bin/yq"
    "./yq"
  )

  for location in "${locations[@]}"; do
    if [[ -x "$location" ]]; then
      echo "$location"
      return 0
    fi
  done

  # Check PATH
  if command -v yq &>/dev/null; then
    command -v yq
    return 0
  fi

  # yq not found
  echo ""
  return 1
}

# Calculate string similarity using Levenshtein distance algorithm
# Returns similarity percentage (0-100)
calculate_string_similarity() {
  local str1="$1"
  local str2="$2"

  # Normalize strings: lowercase, remove extra spaces
  str1=$(echo "$str1" | tr '[:upper:]' '[:lower:]' | tr -s ' ')
  str2=$(echo "$str2" | tr '[:upper:]' '[:lower:]' | tr -s ' ')

  local len1=${#str1}
  local len2=${#str2}

  # If either string is empty, similarity is 0
  if [[ $len1 -eq 0 ]] || [[ $len2 -eq 0 ]]; then
    echo 0
    return
  fi

  # For performance, use a simpler algorithm for long strings
  # If strings are very long (>200 chars), use word-based similarity
  if [[ $len1 -gt 200 ]] || [[ $len2 -gt 200 ]]; then
    # Word-based similarity: count common words
    local words1=($str1)
    local words2=($str2)
    local common=0
    for word in "${words1[@]}"; do
      if [[ " ${words2[@]} " =~ " ${word} " ]]; then
        common=$((common + 1))
      fi
    done
    local total=${#words1[@]}
    if [[ $total -eq 0 ]]; then
      echo 0
      return
    fi
    local similarity=$((common * 100 / total))
    echo $similarity
    return
  fi

  # Levenshtein distance calculation for shorter strings
  local i j cost

  # Use a simpler approach: character-by-character comparison
  local max_len=$len1
  if [[ $len2 -gt $max_len ]]; then
    max_len=$len2
  fi

  local matches=0
  for ((i=0; i<max_len; i++)); do
    if [[ $i -lt $len1 ]] && [[ $i -lt $len2 ]]; then
      if [[ "${str1:$i:1}" == "${str2:$i:1}" ]]; then
        matches=$((matches + 1))
      fi
    fi
  done

  local similarity=$((matches * 100 / max_len))
  echo $similarity
}

# File locking functions to prevent race conditions
# Uses flock with timeout to prevent deadlocks
LOCK_TIMEOUT=30  # seconds
LOCK_FD=-1

acquire_lock() {
  local lock_file="$1"
  # Open lock file for reading/writing
  exec {LOCK_FD}>"$lock_file"
  # Try to acquire exclusive lock with timeout
  if ! flock -w "$LOCK_TIMEOUT" "$LOCK_FD"; then
    echo "ERROR: Failed to acquire lock on $lock_file after ${LOCK_TIMEOUT}s" >&2
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

# Permission management functions
# Set restrictive permissions for security (600 for files, 700 for directories)
set_secure_permissions() {
  local path="$1"
  local type="$2"  # "file" or "dir"

  if [[ "$type" == "file" ]]; then
    chmod 600 "$path"
  elif [[ "$type" == "dir" ]]; then
    chmod 700 "$path"
  else
    echo "ERROR: Invalid permission type: $type" >&2
    return 1
  fi
}

validate_permissions() {
  local path="$1"
  local expected_perms="$2"

  local actual_perms=$(stat -c "%a" "$path" 2>/dev/null || stat -f "%A" "$path" 2>/dev/null)
  if [[ "$actual_perms" != "$expected_perms" ]]; then
    echo "WARNING: Permission mismatch on $path (expected: $expected_perms, actual: $actual_perms)" >&2
    return 1
  fi
  return 0
}

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

# Read configured log level from brain/config.yaml
CONFIG_FILE="$MATRIX_DIR/brain/config.yaml"
CONFIGURED_LOG_LEVEL="INFO"  # Default if not configured

if [[ -f "$CONFIG_FILE" ]]; then
  # Try to extract log_level from config using grep (yq not available yet)
  CONFIGURED_LOG_LEVEL=$(grep -E '^log_level:' "$CONFIG_FILE" 2>/dev/null | sed 's/log_level:[[:space:]]*//' | tr -d '"' | tr -d "'" || echo "INFO")
  # Validate the configured level
  if [[ -z "${LOG_LEVEL_VALUES[$CONFIGURED_LOG_LEVEL]:-}" ]]; then
    CONFIGURED_LOG_LEVEL="INFO"  # Fallback to default if invalid
  fi
fi

LOG_FILE="$MATRIX_DIR/brain/state/work-process-log.yaml"
ARCHIVE_DIR="$MATRIX_DIR/brain/state/work-process-log-archive"
LOCK_FILE="$MATRIX_DIR/brain/state/work-process-log.lock"

# Filter by log level
# Only write log if event level is <= configured level (lower number = higher priority)
EVENT_LEVEL_VALUE="${LOG_LEVEL_VALUES[$LEVEL]}"
CONFIGURED_LEVEL_VALUE="${LOG_LEVEL_VALUES[$CONFIGURED_LOG_LEVEL]}"

if [[ $EVENT_LEVEL_VALUE -gt $CONFIGURED_LEVEL_VALUE ]]; then
  # Event level is too verbose, skip writing
  exit 0
fi

# Checkpoint Intelligence: Detect and filter redundant checkpoints
check_checkpoint_similarity() {
  local current_details="$1"
  local current_specialist="${2:-}"
  local log_file="$3"
  local time_window_minutes=5

  # Only apply to checkpoint_write events
  if [[ "$EVENT_TYPE" != "checkpoint_write" ]]; then
    return 1  # Not a checkpoint, allow writing
  fi

  # Calculate timestamp threshold (5 minutes ago)
  local timestamp_threshold=$(date -d "$time_window_minutes minutes ago" -Iseconds 2>/dev/null || date -v-${time_window_minutes}M -Iseconds 2>/dev/null)
  if [[ -z "$timestamp_threshold" ]]; then
    # If date calculation fails, allow writing (fail-safe)
    return 1
  fi

  # Read recent checkpoint entries from log file
  if [[ ! -f "$log_file" ]]; then
    return 1  # No log file exists, allow writing
  fi

  # Use yq to extract recent checkpoint_write entries within time window
  # This is more reliable than grep parsing
  local yq_bin=$(find_yq_binary)
  if [[ -z "$yq_bin" ]]; then
    # Fallback to allow writing if yq not available
    return 1
  fi

  # Extract all checkpoint_write entries with their timestamps and details
  # Use yq to filter by timestamp and extract relevant fields
  local recent_checkpoints=$("$yq_bin" eval '.entries[] | select(.event_type == "checkpoint_write") | select(.timestamp >= "'"$timestamp_threshold"'")' "$log_file" 2>/dev/null || echo "")

  if [[ -z "$recent_checkpoints" ]]; then
    return 1  # No recent checkpoints found, allow writing
  fi

  # Parse each checkpoint entry and check similarity
  local entry_count=0
  local in_entry=0
  local entry_timestamp=""
  local entry_details=""
  local entry_specialist=""

  while IFS= read -r line; do
    # Detect timestamp line
    if [[ "$line" =~ ^timestamp: ]]; then
      # Process previous entry if exists
      if [[ $in_entry -eq 1 ]] && [[ -n "$entry_details" ]]; then
        # Calculate similarity
        local similarity=$(calculate_string_similarity "$current_details" "$entry_details")
        if [[ $similarity -ge 80 ]]; then
          # Check specialist match if current specialist is specified
          if [[ -z "$current_specialist" ]] || [[ "$entry_specialist" == "$current_specialist" ]]; then
            echo "SKIP: Redundant checkpoint detected (similarity: ${similarity}%, timestamp: ${entry_timestamp})" >&2
            return 0  # Skip writing this checkpoint
          fi
        fi
      fi
      # Start new entry
      entry_timestamp=$(echo "$line" | sed 's/timestamp: "\(.*\)"/\1/')
      entry_details=""
      entry_specialist=""
      in_entry=1
    # Extract details
    elif [[ "$line" =~ ^details: ]] && [[ $in_entry -eq 1 ]]; then
      entry_details=$(echo "$line" | sed 's/details: "\(.*\)"/\1/')
    # Extract specialist if present
    elif [[ "$line" =~ ^specialist: ]] && [[ $in_entry -eq 1 ]]; then
      entry_specialist=$(echo "$line" | sed 's/specialist: "\(.*\)"/\1/')
    fi
  done <<< "$recent_checkpoints"

  # Process last entry
  if [[ $in_entry -eq 1 ]] && [[ -n "$entry_details" ]]; then
    local similarity=$(calculate_string_similarity "$current_details" "$entry_details")
    if [[ $similarity -ge 80 ]]; then
      if [[ -z "$current_specialist" ]] || [[ "$entry_specialist" == "$current_specialist" ]]; then
        echo "SKIP: Redundant checkpoint detected (similarity: ${similarity}%, timestamp: ${entry_timestamp})" >&2
        return 0  # Skip writing this checkpoint
      fi
    fi
  fi

  return 1  # No similar checkpoint found, allow writing
}

# Apply checkpoint similarity check before writing
if check_checkpoint_similarity "$DETAILS" "$SPECIALIST" "$LOG_FILE"; then
  exit 0  # Skip writing redundant checkpoint
fi

# Generate timestamp
TIMESTAMP=$(date -Iseconds 2>/dev/null || date +"%Y-%m-%dT%H:%M:%S%z")

# Start building log entry
LOG_ENTRY="  - timestamp: \"$TIMESTAMP\"\n"
LOG_ENTRY+="    event_type: \"$EVENT_TYPE\"\n"
LOG_ENTRY+="    level: \"$LEVEL\"\n"
LOG_ENTRY+="    status: \"$STATUS\"\n"
LOG_ENTRY+="    details: \"$DETAILS\"\n"
# Quote user_request if present, otherwise use YAML null
if [[ -n "$USER_REQUEST" ]]; then
  LOG_ENTRY+="    user_request: \"$USER_REQUEST\"\n"
else
  LOG_ENTRY+="    user_request: null\n"
fi

# Add event-specific fields
case "$EVENT_TYPE" in
  activation)
    # No additional fields for consolidated activation event
    # All information should be in details field
    ;;
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
      # Convert comma-separated list to YAML array using robust approach
      # Use IFS to split by comma into array
      IFS=',' read -ra SPECIALIST_ITEMS <<< "$SPECIALISTS"
      SPECIALIST_ARRAY=""
      for i in "${!SPECIALIST_ITEMS[@]}"; do
        # Trim whitespace from each item
        ITEM=$(echo "${SPECIALIST_ITEMS[$i]}" | xargs)
        if [[ -n "$ITEM" ]]; then
          if [[ $i -eq 0 ]]; then
            SPECIALIST_ARRAY="\"$ITEM\""
          else
            SPECIALIST_ARRAY+=", \"$ITEM\""
          fi
        fi
      done
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
    if [[ -n "$MESSAGE" ]]; then
      LOG_ENTRY+="    message_summary: \"$MESSAGE\"\n"
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
    if [[ -n "$RESPONSE" ]]; then
      LOG_ENTRY+="    response_summary: \"$RESPONSE\"\n"
    fi
    ;;
  specialist_execution)
    if [[ -n "$SPECIALIST" ]]; then
      LOG_ENTRY+="    specialist: \"$SPECIALIST\"\n"
    fi
    if [[ -n "$INVOCATION_METHOD" ]]; then
      LOG_ENTRY+="    invocation_method: \"$INVOCATION_METHOD\"\n"
    fi
    if [[ -n "$CONTEXT" ]]; then
      LOG_ENTRY+="    context_passed: \"$CONTEXT\"\n"
    fi
    if [[ -n "$OUTCOME" ]]; then
      LOG_ENTRY+="    outcome: \"$OUTCOME\"\n"
    fi
    if [[ -n "$DURATION" ]]; then
      LOG_ENTRY+="    duration_seconds: $DURATION\n"
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
  set_secure_permissions "$LOG_FILE" "file"
fi

# Setup temp file and cleanup trap
TEMP_FILE=$(mktemp)
trap 'rm -f "$TEMP_FILE"; release_lock' EXIT

# Acquire lock before any file operations
if ! acquire_lock "$LOCK_FILE"; then
  exit 1
fi

# Find yq binary with fallbacks
YQ_BIN=$(find_yq_binary) || YQ_BIN=""
if [[ -z "$YQ_BIN" ]]; then
  echo "ERROR: yq binary not found. Please install yq or set YQ_PATH environment variable." >&2
  release_lock
  exit 1
fi

# Check log rotation (keep last 100 entries) using yq for YAML-aware counting
# Changed from >= 100 to > 100 to avoid rotation when exactly at 100
ENTRY_COUNT=$("$YQ_BIN" eval '.entries | length' "$LOG_FILE" 2>/dev/null || echo "0")
if [[ $ENTRY_COUNT -gt 100 ]]; then
  # Archive old logs
  mkdir -p "$ARCHIVE_DIR"
  set_secure_permissions "$ARCHIVE_DIR" "dir"
  ARCHIVE_DATE=$(date +"%Y-%m-%d")
  ARCHIVE_FILE="$ARCHIVE_DIR/work-process-log-$ARCHIVE_DATE.yaml"

  # Extract entries to archive (first N-100 entries) using yq
  # Keep last 100 entries, move the rest to archive
  "$YQ_BIN" eval ".entries[0:$((ENTRY_COUNT - 100))]" "$LOG_FILE" > "${ARCHIVE_FILE}.tmp"
  # Wrap the extracted entries in proper YAML structure (file is just an array)
  "$YQ_BIN" eval '. as $e | {"entries": $e}' "${ARCHIVE_FILE}.tmp" > "${ARCHIVE_FILE}.new"
  rm "${ARCHIVE_FILE}.tmp"

  # Merge with existing archive if it exists
  if [[ -f "$ARCHIVE_FILE" ]]; then
    # Use yq to merge existing archive with new entries
    "$YQ_BIN" eval '.entries as $existing | load("'"${ARCHIVE_FILE}.new"'").entries as $new | {"entries": ($existing + $new)}' "$ARCHIVE_FILE" > "${ARCHIVE_FILE}.merged"
    mv "${ARCHIVE_FILE}.merged" "$ARCHIVE_FILE"
    rm "${ARCHIVE_FILE}.new"
    set_secure_permissions "$ARCHIVE_FILE" "file"
  else
    # Create new archive file
    mv "${ARCHIVE_FILE}.new" "$ARCHIVE_FILE"
    set_secure_permissions "$ARCHIVE_FILE" "file"
  fi

  # Keep only last 100 entries in main log file using yq
  "$YQ_BIN" eval '.entries as $e | {"entries": $e[-100:]}' "$LOG_FILE" > "${LOG_FILE}.tmp"
  mv "${LOG_FILE}.tmp" "$LOG_FILE"
  set_secure_permissions "$LOG_FILE" "file"
fi

# Append new entry using atomic file operations
# Read current content, remove closing bracket, add entry, write to temp, then atomic move
{
  # Check if file is empty or only has "entries: []"
  if [[ ! -s "$LOG_FILE" ]] || [[ $(wc -l < "$LOG_FILE") -eq 1 ]]; then
    # File is empty or only has the header, start fresh with block style
    echo "entries:"
  else
    # Remove the last line (closing bracket) from existing file
    head -n -1 "$LOG_FILE"
  fi
  # Use printf to avoid extra newlines from echo -e
  # Strip trailing newline from LOG_ENTRY to avoid blank line before closing bracket
  printf "%b" "${LOG_ENTRY%\\n}"
} > "$TEMP_FILE"

# Atomic move
mv "$TEMP_FILE" "$LOG_FILE"
set_secure_permissions "$LOG_FILE" "file"

echo "OK: Log entry written"

# Optional: Trigger checkpoint cleanup if this is a checkpoint_write event
# This keeps checkpoint count manageable without requiring separate cron jobs
if [[ "$EVENT_TYPE" == "checkpoint_write" ]]; then
  CHECKPOINT_DIR="$MATRIX_DIR/brain/state/checkpoints"
  if [[ -d "$CHECKPOINT_DIR" ]]; then
    CHECKPOINT_COUNT=$(ls -1 "$CHECKPOINT_DIR"/*.yaml 2>/dev/null | wc -l)
    # Keep last 30 checkpoints, remove older ones
    if [[ $CHECKPOINT_COUNT -gt 30 ]]; then
      ls -1t "$CHECKPOINT_DIR"/*.yaml 2>/dev/null | tail -n +$((CHECKPOINT_COUNT - 30 + 1)) | xargs -r rm -f
    fi
  fi
fi

exit 0
