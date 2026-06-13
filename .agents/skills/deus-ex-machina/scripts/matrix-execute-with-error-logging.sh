#!/usr/bin/env bash
# Execute commands with error logging and retry support.
#
# This script provides a wrapper for executing commands/scripts with automatic
# error logging to brain/state/system-errors.log. It supports retry attempts
# and logs each failure with detailed information.
#
# Usage:
#   matrix-execute-with-error-logging.sh --command <cmd> [--max-retries <n>] [--script-name <name>] [--matrix-dir <path>]
#
# Required:
#   --command <cmd>       Command to execute (can be a script path or any shell command)
#
# Optional:
#   --max-retries <n>     Maximum number of retry attempts (default: 3)
#   --script-name <name>  Name of the script being executed (for logging, default: command)
#   --matrix-dir <path>   Path to matrix directory (default: script dir/../..)
#   --context <ctx>       Additional context information for error logging
#
# Exit codes:
#   0   - Command executed successfully
#   1   - Command failed after all retries
#   2   - Invalid arguments
#
# Example:
#   matrix-execute-with-error-logging.sh --command "./bin/matrix checkpoint 'test'" --max-retries 2 --script-name "matrix-checkpoint"

set -euo pipefail

# File locking configuration
LOCK_TIMEOUT=30
LOCK_FD=-1
LOCK_FILE=""

# Acquire file lock using flock
acquire_lock() {
  local lock_file="$1"
  LOCK_FILE="$lock_file"
  # Open lock file for reading/writing
  exec {LOCK_FD}>"$lock_file"
  # Try to acquire exclusive lock with timeout
  if ! flock -w "$LOCK_TIMEOUT" "$LOCK_FD"; then
    echo "ERROR: Failed to acquire lock on $lock_file after ${LOCK_TIMEOUT}s" >&2
    return 1
  fi
  return 0
}

# Release file lock
release_lock() {
  if [[ $LOCK_FD -ne -1 ]]; then
    flock -u "$LOCK_FD"
    exec {LOCK_FD}>&-
    LOCK_FD=-1
  fi
  LOCK_FILE=""
}

# Cleanup function for trap handlers
cleanup() {
  local exit_code=$?
  release_lock
  exit $exit_code
}

# Trap signals for graceful cleanup
trap cleanup EXIT INT TERM

COMMAND=""
MAX_RETRIES=3
SCRIPT_NAME=""
MATRIX_DIR=""
CONTEXT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --command)
      COMMAND="$2"
      shift 2
      ;;
    --max-retries)
      MAX_RETRIES="$2"
      shift 2
      ;;
    --script-name)
      SCRIPT_NAME="$2"
      shift 2
      ;;
    --matrix-dir)
      MATRIX_DIR="$2"
      shift 2
      ;;
    --context)
      CONTEXT="$2"
      shift 2
      ;;
    *)
      echo "ERROR: Unknown option: $1" >&2
      echo "Usage: matrix-execute-with-error-logging.sh --command <cmd> [--max-retries <n>] [--script-name <name>] [--matrix-dir <path>]" >&2
      exit 2
      ;;
  esac
done

# Validate required fields
if [[ -z "$COMMAND" ]]; then
  echo "ERROR: Missing required field: --command" >&2
  exit 2
fi

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

# Default script name if not provided
if [[ -z "$SCRIPT_NAME" ]]; then
  SCRIPT_NAME="$COMMAND"
fi

# Error log file path
ERROR_LOG_FILE="$MATRIX_DIR/brain/state/system-errors.log"
ERROR_LOG_ARCHIVE_DIR="$MATRIX_DIR/brain/state/system-errors-archive"
MAX_LOG_SIZE_MB=10

# Ensure directories exist
mkdir -p "$(dirname "$ERROR_LOG_FILE")" 2>/dev/null || true
mkdir -p "$ERROR_LOG_ARCHIVE_DIR" 2>/dev/null || true

# Ensure error log exists
if [[ ! -f "$ERROR_LOG_FILE" ]]; then
  touch "$ERROR_LOG_FILE"
  chmod 600 "$ERROR_LOG_FILE"
fi

# Function to validate log file format (graceful degradation)
validate_log_format() {
  local log_file="$1"
  local corrupt_lines=0
  local total_lines=0

  # If file is empty or doesn't exist, it's valid
  if [[ ! -s "$log_file" ]]; then
    return 0
  fi

  # Check each line for expected format
  while IFS= read -r line; do
    total_lines=$((total_lines + 1))
    # Expected format: [timestamp] :: field :: field :: ...
    # Basic check: must start with [ and contain :: delimiter
    if [[ ! "$line" =~ ^\[.*\]\ *:: ]]; then
      corrupt_lines=$((corrupt_lines + 1))
    fi
  done < "$log_file"

  # Report corruption if found, but don't fail (graceful degradation)
  if [[ $corrupt_lines -gt 0 ]]; then
    echo "WARNING: Found $corrupt_lines corrupt lines out of $total_lines in $log_file (graceful degradation)" >&2
  fi

  return 0
}

# Function to rotate log if size exceeds limit
rotate_log_if_needed() {
  local log_file="$1"
  local max_size_mb="$2"
  local archive_dir="$3"

  # Check if file exists and get size in bytes
  if [[ ! -f "$log_file" ]]; then
    return 0
  fi

  local file_size_bytes=$(stat -f%z "$log_file" 2>/dev/null || stat -c%s "$log_file" 2>/dev/null || echo 0)
  local max_size_bytes=$((max_size_mb * 1024 * 1024))

  # Rotate if size exceeds limit
  if [[ $file_size_bytes -gt $max_size_bytes ]]; then
    local timestamp=$(date +"%Y%m%d_%H%M%S" 2>/dev/null || echo "unknown")
    local archive_name="system-errors_${timestamp}.log"
    local archive_path="$archive_dir/$archive_name"

    # Move to archive
    if mv "$log_file" "$archive_path" 2>/dev/null; then
      chmod 600 "$archive_path" 2>/dev/null || true
      # Create new empty log file
      touch "$log_file"
      chmod 600 "$log_file"
      echo "Rotated log file: $archive_path" >&2
    else
      echo "WARNING: Failed to rotate log file" >&2
    fi
  fi
}

# Validate log format on startup
validate_log_format "$ERROR_LOG_FILE"

# Rotate log if needed on startup
rotate_log_if_needed "$ERROR_LOG_FILE" "$MAX_LOG_SIZE_MB" "$ERROR_LOG_ARCHIVE_DIR"

# Function to log error with file locking
log_error() {
  local attempt="$1"
  local exit_code="$2"
  local error_output="$3"
  local timestamp=$(date -Iseconds 2>/dev/null || date +"%Y-%m-%dT%H:%M:%S%z")

  # Sanitize COMMAND and CONTEXT (remove newlines, tabs, limit length)
  local sanitized_command=$(echo "$COMMAND" | tr -d '\n' | tr -d '\r' | tr -d '\t' | head -c 200)
  local sanitized_context=""
  if [[ -n "$CONTEXT" ]]; then
    sanitized_context=$(echo "$CONTEXT" | tr -d '\n' | tr -d '\r' | tr -d '\t' | head -c 200)
  fi

  # Sanitize error output (remove newlines, limit length)
  error_output=$(echo "$error_output" | tr -d '\n' | tr -d '\r' | head -c 500)

  # Build log entry with explicit :: delimiter
  # Format: [timestamp] :: SCRIPT_NAME :: ATTEMPT:X/Y :: EXIT_CODE:N :: CONTEXT:val :: COMMAND :: ERROR:msg
  local log_entry="[$timestamp] :: $SCRIPT_NAME :: ATTEMPT:$attempt/$MAX_RETRIES :: EXIT_CODE:$exit_code"
  if [[ -n "$sanitized_context" ]]; then
    log_entry+=" :: CONTEXT:$sanitized_context"
  fi
  log_entry+=" :: COMMAND:$sanitized_command"
  if [[ -n "$error_output" ]]; then
    log_entry+=" :: ERROR:$error_output"
  fi

  # Acquire lock before writing to error log
  local lock_file="$ERROR_LOG_FILE.lock"
  if acquire_lock "$lock_file"; then
    echo "$log_entry" >> "$ERROR_LOG_FILE" 2>/dev/null || true
    chmod 600 "$ERROR_LOG_FILE" 2>/dev/null || true
    release_lock
  fi
}

# Execute command with retries
attempt=1
while [[ $attempt -le $MAX_RETRIES ]]; do
  # Execute command and capture output using bash -c (safer than eval)
  if OUTPUT=$(bash -c "$COMMAND" 2>&1); then
    # Success
    exit 0
  else
    # Failure
    EXIT_CODE=$?
    log_error "$attempt" "$EXIT_CODE" "$OUTPUT"

    # If this was the last attempt, exit with failure
    if [[ $attempt -eq $MAX_RETRIES ]]; then
      # Check if log write was successful before referencing it
      if [[ -w "$ERROR_LOG_FILE" ]] && [[ -s "$ERROR_LOG_FILE" ]]; then
        echo "ERROR: Command failed after $MAX_RETRIES attempts. See $ERROR_LOG_FILE for details." >&2
      else
        echo "ERROR: Command failed after $MAX_RETRIES attempts. Error log unavailable." >&2
      fi
      exit 1
    fi

    # Wait before retry (exponential backoff: 1s, 2s, 4s, ...) with max 30s
    wait_time=$((2 ** (attempt - 1)))
    # Cap wait time at 30 seconds
    if [[ $wait_time -gt 30 ]]; then
      wait_time=30
    fi
    sleep "$wait_time"
  fi

  attempt=$((attempt + 1))
done

# Should never reach here, but just in case
exit 1
