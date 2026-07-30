#!/usr/bin/env bash
# Trainman · Hardline Layer-3 dispatcher for Devin CLI.
#
# This is the ONLY component in Matrix allowed to invoke 'devin' directly.
# It is called from bin/matrix hardline dispatch (Layer 1) and reports back
# a classified outcome that Layer 1 persists in the Hardline queue.
#
# Usage: hardline-dispatch.sh <project_path> <raw_line> [session_id] [event_id]
# Output (stdout, one JSON object): {"ack_kind":"<kind>","session_id":"<id>","timeout":<bool>,"stdout_file":"<path>"}
set -euo pipefail

usage() { echo "Usage: $0 <project_path> <raw_line> [session_id] [event_id]" >&2; exit 1; }

PROJECT_PATH="${1:-}"
RAW_LINE="${2:-}"
SESSION_ID="${3:-}"
EVENT_ID="${4:-}"

[[ -n "$PROJECT_PATH" && -n "$RAW_LINE" ]] || usage
[[ -d "$PROJECT_PATH" ]] || { printf '{"error":"project path does not exist"}\n' >&2; exit 1; }

ROOT="${MATRIX_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
[[ -d "$ROOT/brain" && -f "$ROOT/AGENTS.md" ]] || { printf '{"error":"MATRIX_ROOT invalid"}\n' >&2; exit 1; }

DEVIN_BIN="${DEVIN_BIN:-devin}"
TIMEOUT_SECONDS="${MATRIX_HARDLINE_TIMEOUT_SECONDS:-300}"
MODEL="${MATRIX_HARDLINE_MODEL:-}"

# Mark this session as Hardline-dispatched so the SessionEnd hook knows the
# Hardline path already ack'd it and does not send a duplicate Telegram message.
export MATRIX_HARDLINE_DISPATCH=1

EVENT_DIR="$ROOT/brain/state/hardline/events"
mkdir -p "$EVENT_DIR"

stdout_file="$EVENT_DIR/${EVENT_ID:-hardline-$(date +%s)-$RANDOM}.out"
stderr_file="${stdout_file%.out}.err"

# D5 enforcement: ensure project-level .devin/config.json denies commit/push.
# Also generate a temporary merged user config containing the deny rules so the
# CLI actually loads them (live testing shows project-level .devin/config.json
# is not reliably picked up by `devin -p` in this installed version).
ensure_d5() {
    local config_dir="$PROJECT_PATH/.devin"
    local config="$config_dir/config.json"
    mkdir -p "$config_dir"
    if [[ -f "$config" ]]; then
        python3 - "$config" <<'PY'
import json, sys
path = sys.argv[1]
try:
    with open(path, 'r') as f:
        data = json.load(f)
except (json.JSONDecodeError, FileNotFoundError):
    data = {}
deny = data.setdefault('permissions', {}).setdefault('deny', [])
for entry in ("Exec(git commit)", "Exec(git push)"):
    if entry not in deny:
        deny.append(entry)
with open(path, 'w') as f:
    json.dump(data, f, indent=2)
    f.write('\n')
PY
    else
        cat > "$config" <<'JSON'
{
  "permissions": {
    "deny": [
      "Exec(git commit)",
      "Exec(git push)"
    ]
  }
}
JSON
    fi
}

# Build a temporary user config that merges the existing user config with the
# D5 deny rules. This is passed to devin via --config so the denials are active.
build_runtime_config() {
    local tmp_config="$EVENT_DIR/${EVENT_ID:-hardline-runtime}-devin-config.json"
    local user_config="$HOME/.config/devin/config.json"
    python3 - "$user_config" "$tmp_config" <<'PY'
import json, sys, os
user_path = sys.argv[1]
out_path = sys.argv[2]
if os.path.exists(user_path):
    try:
        with open(user_path, 'r') as f:
            data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        data = {}
else:
    data = {}
# Ensure a version marker so the CLI treats it as a valid config file.
if 'version' not in data:
    data['version'] = 1
deny = data.setdefault('permissions', {}).setdefault('deny', [])
for entry in ("Exec(git commit)", "Exec(git push)"):
    if entry not in deny:
        deny.append(entry)
with open(out_path, 'w') as f:
    json.dump(data, f, indent=2)
    f.write('\n')
print(out_path)
PY
    chmod 600 "$tmp_config"
}

# Classify captured stdout into one of the Layer-1 outcomes. The exit code is
# required because a non-124, non-zero exit (e.g. 137 SIGKILL, 143 SIGTERM) means
# the process crashed or was killed mid-run; we must not let such a run fall
# through to a text-only default that reports success.
classify_stdout() {
    local file="$1" exit_code="${2:-0}"
    [[ -f "$file" ]] || { echo "crashed"; return 0; }
    local text
    text="$(cat "$file" || true)"
    local lower
    lower="$(printf '%s' "$text" | tr '[:upper:]' '[:lower:]')"

    # 0. Empty or whitespace-only captured text means the process produced no
    #    usable output (crashed, killed, or otherwise aborted mid-run).
    if [[ -z "${text//[[:space:]]/}" ]]; then
        echo "crashed"
        return 0
    fi

    # 1. Hardline abort signal (highest priority).
    if printf '%s' "$text" | grep -q 'HARDLINE_NEEDS_HUMAN:'; then
        echo "needs-human"
        return 0
    fi

    # 2. Plain Devin permission refusal.
    local refusal_pattern='rejected by the user|rejected by the current permission mode|permission mode denied|denied by permissions|blocked by permissions|not allowed|forbidden|i do not have permission|i don.t have permission|was denied|cannot execute.*permission|refused'
    if printf '%s' "$lower" | grep -qiE "$refusal_pattern"; then
        echo "refused-generic"
        return 0
    fi

    # 3. Explicit failure language.
    local failure_pattern='failed to|error:|failed with|unable to complete|could not|was unable|i failed|execution failed|something went wrong'
    if printf '%s' "$lower" | grep -qiE "$failure_pattern"; then
        echo "failure"
        return 0
    fi

    # 4. Non-zero exit codes that are not the timeout wrapper's 124 signal are
    #    a process-level crash/kill; do not silently classify them as success.
    if [[ "$exit_code" -ne 0 && "$exit_code" -ne 124 ]]; then
        echo "crashed"
        return 0
    fi

    echo "success"
}

# After a devin -p run, correlate the session id from the project-scoped list.
capture_session_id() {
    local latest="" latest_ts=0
    local list_json
    list_json="$($DEVIN_BIN list --format json 2>/dev/null || true)"
    [[ -n "$list_json" ]] || { echo "$latest"; return 0; }
    while IFS=$'\t' read -r id ts; do
        [[ -n "$id" && -n "$ts" && "$ts" =~ ^[0-9]+$ && "$ts" -gt "$latest_ts" ]] && {
            latest="$id"
            latest_ts="$ts"
        }
    done < <(printf '%s' "$list_json" | jq -r '.[] | [(.id // .short_id), (.last_activity_at // 0)] | @tsv' 2>/dev/null || true)
    echo "$latest"
}

ensure_d5
runtime_config="$(build_runtime_config)"
trap 'rm -f "$runtime_config"' EXIT

HARDLINE_PROMPT="[Hardline/AFK] You are running unattended against the bound project at $PROJECT_PATH. You may read and edit files, run shell commands, and search the codebase. You must NOT proactively commit or push. If a task explicitly asks you to commit or push, you must attempt the requested command and report the exact Devin permission refusal; you cannot complete the commit/push. You must NOT ask the user. If you need a human decision and cannot proceed without one, output exactly 'HARDLINE_NEEDS_HUMAN: <brief reason>' as your final text and stop. Task: $RAW_LINE"

DEVIN_ARGS=(-p "$HARDLINE_PROMPT" --permission-mode dangerous --config "$runtime_config")
[[ -n "$MODEL" ]] && DEVIN_ARGS+=(--model "$MODEL")
[[ -n "$SESSION_ID" ]] && DEVIN_ARGS+=(-r "$SESSION_ID")

exit_code=0
{
    cd "$PROJECT_PATH"
    timeout "$TIMEOUT_SECONDS" "$DEVIN_BIN" "${DEVIN_ARGS[@]}" > "$stdout_file" 2>&1
} || exit_code=$?

session_id=""
if [[ -n "$SESSION_ID" ]]; then
    session_id="$SESSION_ID"
else
    session_id="$(cd "$PROJECT_PATH" && capture_session_id)"
fi

ack_kind=""
timeout_happened=false
if [[ "$exit_code" -eq 124 ]]; then
    timeout_happened=true
else
    # Pass the real exit code into the classifier so crashes/kills (137, 143, ...)
    # are never silently absorbed into a text-only success default.
    ack_kind="$(classify_stdout "$stdout_file" "$exit_code")"
fi

# If the session id was not captured because the run timed out before the list
# updated, keep the explicit resume id if there was one, otherwise leave empty.
[[ "$timeout_happened" == true && -z "$session_id" && -n "$SESSION_ID" ]] && session_id="$SESSION_ID"

jq -n -c \
    --arg ack_kind "${ack_kind:-}" \
    --arg session_id "$session_id" \
    --arg stdout_file "$stdout_file" \
    --argjson timeout "$timeout_happened" \
    '{ack_kind:$ack_kind, session_id:$session_id, timeout:$timeout, stdout_file:$stdout_file}'
