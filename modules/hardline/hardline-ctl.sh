#!/bin/bash
# The Hardline — control script for the long-running monitor and Telegram bridge.
# Purpose: start/stop/status/restart both hardline-monitor.sh and telegram-bridge.py
# as detached background processes, with PID files and logs under brain/state/hardline/.
#
# Design choices:
# - PID files are the primary identity: brain/state/hardline/monitor.pid and
#   brain/state/hardline/telegram-bridge.pid. status/stop always verify the
#   recorded PID is actually alive and still belongs to the expected process by
#   reading /proc/<pid>/cmdline, so a recycled PID never fools us.
# - A pgrep cross-check is used by start() to refuse starting if the processes are
#   already alive even when PID files are missing (defensive, not authoritative).
# - The Telegram bridge needs the secrets file; the monitor does not. If the file is
#   missing, start() still launches the monitor and prints a clear error, then skips
#   the bridge. This lets users test the monitor locally without a bot token.
# - Neither child process is ever started with the token on a command line. The token
#   is sourced into the bridge's environment only; the monitor never sees it.
# - Logs are rotated by overwriting on start so they never grow unbounded. They must
#   never contain the bot token; if either subprocess ever changes to log secrets,
#   that subprocess must be fixed, not this script.
set -uo pipefail

ROOT="${MATRIX_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
MODULE_DIR="$ROOT/modules/hardline"
STATE_DIR="$ROOT/brain/state/hardline"
SECRETS_FILE="${HOME}/.config/devin/hardline/telegram.env"

MONITOR_PIDFILE="$STATE_DIR/monitor.pid"
BRIDGE_PIDFILE="$STATE_DIR/telegram-bridge.pid"
MONITOR_LOG="$STATE_DIR/monitor.log"
BRIDGE_LOG="$STATE_DIR/telegram-bridge.log"

MONITOR_CMD="$MODULE_DIR/hardline-monitor.sh"
BRIDGE_CMD="$MODULE_DIR/telegram-bridge.py"

WEBAPP_PIDFILE="$STATE_DIR/webapp.pid"
WEBAPP_LOG="$STATE_DIR/webapp.log"
WEBAPP_CMD="$MODULE_DIR/status-webapp.py"

mkdir -p "$STATE_DIR"

usage() {
    cat <<EOF
Usage: $(basename "$0") {start|stop|status|restart|webapp-start|webapp-stop|webapp-status}

  start         Start the monitor (always) and the Telegram bridge (if secrets file exists).
  stop          Stop both processes gracefully, clean up stale PID files.
  status        Report whether each process is currently running (monitor, bridge, webapp).
  status --json Machine-readable status of monitor and bridge.
  restart       Stop, then start.
  webapp-start  Start the read-only status webapp.
  webapp-stop   Stop the status webapp.
  webapp-status Show whether the status webapp is running.
EOF
    exit 1
}

_log() {
    echo "[hardline-ctl] $*"
}

# Return 0 if a process with the given PID is alive and its cmdline matches the
# expected marker (script name). This defeats recycled-PID false positives.
_pid_alive() {
    local pid="$1"
    local marker="$2"
    [[ -n "$pid" ]] && [[ "$pid" =~ ^[0-9]+$ ]] && [[ -d "/proc/$pid" ]] && \
        ( tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null | grep -qF "$marker" ) 2>/dev/null
}

# Read the PID from a PID file, or empty if the file is missing/empty.
_read_pid() {
    local pidfile="$1"
    if [[ -f "$pidfile" ]]; then
        cat "$pidfile" 2>/dev/null | tr -d '[:space:]'
    fi
}

# Cross-check via pgrep for the expected command name. Used only by start() as a
# defensive guard when PID files are stale/missing; the PID file is still the
# authoritative source for stop/status.
_pgrep_any() {
    local pattern="$1"
    pgrep -f "$pattern" >/dev/null 2>&1
}

# Stop a single managed process. Always idempotent: handles stale PID files by
# simply removing them. Sends SIGTERM, waits briefly, then SIGKILL if necessary.
_stop_one() {
    local name="$1"
    local pidfile="$2"
    local pid
    pid="$(_read_pid "$pidfile")"

    if [[ -z "$pid" ]]; then
        _log "$name: no PID file (already stopped)."
        rm -f "$pidfile"
        return 0
    fi

    if ! _pid_alive "$pid" "$name"; then
        _log "$name: PID $pid is not running (stale PID file)."
        rm -f "$pidfile"
        return 0
    fi

    _log "$name: stopping PID $pid (SIGTERM to process group)..."
    # Both children are started with setsid, so their PID equals their process group ID.
    # Killing the group catches any pipeline children (e.g., the monitor's tail subshell).
    kill -TERM -"$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true

    local waited=0
    while (( waited < 10 )) && _pid_alive "$pid" "$name"; do
        sleep 0.5
        waited=$((waited + 1))
    done

    if _pid_alive "$pid" "$name"; then
        _log "$name: PID $pid did not exit; sending SIGKILL to process group."
        kill -KILL -"$pid" 2>/dev/null || kill -KILL "$pid" 2>/dev/null || true
        sleep 0.5
    fi

    if _pid_alive "$pid" "$name"; then
        _log "$name: WARNING: PID $pid still alive after SIGKILL."
        return 1
    fi

    rm -f "$pidfile"
    _log "$name: stopped."
    return 0
}

# Start the monitor. Always safe to call; refuses if already running.
_start_monitor() {
    if _pid_alive "$(_read_pid "$MONITOR_PIDFILE")" "hardline-monitor.sh"; then
        _log "monitor: already running (PID $(_read_pid "$MONITOR_PIDFILE"))."
        return 1
    fi

    if _pgrep_any "hardline-monitor.sh"; then
        _log "monitor: detected an existing hardline-monitor.sh process (no PID file). Refusing to start."
        return 1
    fi

    rm -f "$MONITOR_PIDFILE"
    : > "$MONITOR_LOG"

    # setsid creates a new session so the child survives the caller's terminal.
    # nohup makes it ignore SIGHUP. The monitor needs no special environment.
    MATRIX_ROOT="$ROOT" nohup setsid "$MONITOR_CMD" > "$MONITOR_LOG" 2>&1 &
    local pid=$!
    disown "$pid" 2>/dev/null || true

    # Give the process a moment to fail on startup (e.g., missing inbox.log parent dir).
    sleep 0.3
    if ! _pid_alive "$pid" "hardline-monitor.sh"; then
        _log "monitor: failed to start (see $MONITOR_LOG)."
        rm -f "$MONITOR_PIDFILE"
        return 1
    fi

    echo "$pid" > "$MONITOR_PIDFILE"
    _log "monitor: started PID $pid (log: $MONITOR_LOG)."
    return 0
}

# Start the Telegram bridge. Requires the secrets file to be present and readable.
_start_bridge() {
    if _pid_alive "$(_read_pid "$BRIDGE_PIDFILE")" "telegram-bridge.py"; then
        _log "bridge: already running (PID $(_read_pid "$BRIDGE_PIDFILE"))."
        return 1
    fi

    if _pgrep_any "telegram-bridge.py"; then
        _log "bridge: detected an existing telegram-bridge.py process (no PID file). Refusing to start."
        return 1
    fi

    if [[ ! -f "$SECRETS_FILE" ]]; then
        _log "bridge: secrets file not found at $SECRETS_FILE"
        _log "bridge: create it with two lines:"
        _log "  export MATRIX_HARDLINE_TELEGRAM_BOT_TOKEN='your-token'"
        _log "  export MATRIX_HARDLINE_TELEGRAM_ALLOWED_CHAT_ID='your-chat-id'"
        _log "bridge: refusing to start without token. (monitor is running independently)."
        return 1
    fi

    if [[ ! -r "$SECRETS_FILE" ]]; then
        _log "bridge: secrets file $SECRETS_FILE is not readable."
        return 1
    fi

    rm -f "$BRIDGE_PIDFILE"
    : > "$BRIDGE_LOG"

    # Source the secrets into the bridge's environment only. The token is never placed
    # on a command line and never reaches the monitor log.
    (
        set -a
        # shellcheck source=/dev/null
        . "$SECRETS_FILE"
        set +a
        nohup setsid "$BRIDGE_CMD" > "$BRIDGE_LOG" 2>&1 &
        echo $! > "$BRIDGE_PIDFILE"
    )
    local pid
    pid="$(_read_pid "$BRIDGE_PIDFILE")"
    disown "$pid" 2>/dev/null || true

    sleep 0.3
    if ! _pid_alive "$pid" "telegram-bridge.py"; then
        _log "bridge: failed to start (see $BRIDGE_LOG)."
        rm -f "$BRIDGE_PIDFILE"
        return 1
    fi

    _log "bridge: started PID $pid (log: $BRIDGE_LOG)."
    return 0
}

# Start the read-only webapp. Unlike _start_monitor/_start_bridge, returning 0
# when the webapp is already running is intentional: the primary consumer is an
# idempotent alias, and "already running" means the desired state is satisfied.
_start_webapp() {
    if _pid_alive "$(_read_pid "$WEBAPP_PIDFILE")" "status-webapp.py"; then
        _log "webapp: already running (PID $(_read_pid "$WEBAPP_PIDFILE"))."
        return 0
    fi

    if _pgrep_any "status-webapp.py"; then
        _log "webapp: detected an existing status-webapp.py process (no PID file). Refusing to start."
        return 1
    fi

    rm -f "$WEBAPP_PIDFILE"
    : > "$WEBAPP_LOG"

    MATRIX_ROOT="$ROOT" nohup setsid python3 "$WEBAPP_CMD" > "$WEBAPP_LOG" 2>&1 &
    local pid=$!
    disown "$pid" 2>/dev/null || true

    sleep 0.3
    if ! _pid_alive "$pid" "status-webapp.py"; then
        _log "webapp: failed to start (see $WEBAPP_LOG — check for 'Address already in use')."
        rm -f "$WEBAPP_PIDFILE"
        return 1
    fi

    echo "$pid" > "$WEBAPP_PIDFILE"
    _log "webapp: started PID $pid on http://127.0.0.1:${MATRIX_HARDLINE_WEBAPP_PORT:-8765}/ (log: $WEBAPP_LOG)."
    return 0
}

cmd_webapp_start() { _start_webapp; }
cmd_webapp_stop()  { _stop_one "webapp" "$WEBAPP_PIDFILE"; }
cmd_webapp_status() {
    local pid; pid="$(_read_pid "$WEBAPP_PIDFILE")"
    if _pid_alive "$pid" "status-webapp.py"; then
        echo "webapp:  running (PID $pid, log $WEBAPP_LOG)"
    elif [[ -n "$pid" ]]; then
        echo "webapp:  stopped (stale PID $pid in $WEBAPP_PIDFILE)"
    else
        echo "webapp:  stopped"
    fi
}

cmd_start() {
    # Refuse to start if either process is already running. Use restart to recover
    # from a partial or stale state, or stop to clean up first.
    if _pid_alive "$(_read_pid "$MONITOR_PIDFILE")" "hardline-monitor.sh" || _pgrep_any "hardline-monitor.sh"; then
        _log "monitor: already running. Refusing to start; use restart or stop first."
        return 1
    fi
    if _pid_alive "$(_read_pid "$BRIDGE_PIDFILE")" "telegram-bridge.py" || _pgrep_any "telegram-bridge.py"; then
        _log "bridge: already running. Refusing to start; use restart or stop first."
        return 1
    fi

    _log "starting Hardline services..."
    local rc=0

    _start_monitor || rc=1
    _start_bridge || rc=1

    if (( rc == 0 )); then
        _log "all services started."
    else
        _log "one or more services could not start (see errors above)."
    fi
    return $rc
}

cmd_stop() {
    _log "stopping Hardline services..."
    local rc=0
    _stop_one "monitor" "$MONITOR_PIDFILE" || rc=1
    _stop_one "bridge" "$BRIDGE_PIDFILE" || rc=1
    if (( rc == 0 )); then
        _log "all services stopped."
    else
        _log "one or more services had trouble stopping."
    fi
    return $rc
}

cmd_status() {
    local json=""
    [[ "${1:-}" == "--json" ]] && json=1
    local monitor_pid bridge_pid
    monitor_pid="$(_read_pid "$MONITOR_PIDFILE")"
    bridge_pid="$(_read_pid "$BRIDGE_PIDFILE")"

    if [[ -n "$json" ]]; then
        local m_run=false b_run=false
        _pid_alive "$monitor_pid" "hardline-monitor.sh" && m_run=true
        _pid_alive "$bridge_pid" "telegram-bridge.py" && b_run=true
        jq -n \
            --argjson m_run "$m_run" --arg m_pid "$monitor_pid" --arg m_log "$MONITOR_LOG" \
            --argjson b_run "$b_run" --arg b_pid "$bridge_pid" --arg b_log "$BRIDGE_LOG" \
            '{monitor:{running:$m_run,pid:($m_pid|select(length>0)),log:$m_log},
              bridge:{running:$b_run,pid:($b_pid|select(length>0)),log:$b_log}}'
        return
    fi

    if _pid_alive "$monitor_pid" "hardline-monitor.sh"; then
        echo "monitor: running (PID $monitor_pid, log $MONITOR_LOG)"
    elif [[ -n "$monitor_pid" ]]; then
        echo "monitor: stopped (stale PID $monitor_pid in $MONITOR_PIDFILE)"
    else
        echo "monitor: stopped"
    fi

    if _pid_alive "$bridge_pid" "telegram-bridge.py"; then
        echo "bridge:  running (PID $bridge_pid, log $BRIDGE_LOG)"
    elif [[ -n "$bridge_pid" ]]; then
        echo "bridge:  stopped (stale PID $bridge_pid in $BRIDGE_PIDFILE)"
    else
        echo "bridge:  stopped"
    fi

    local webapp_pid
    webapp_pid="$(_read_pid "$WEBAPP_PIDFILE")"
    if _pid_alive "$webapp_pid" "status-webapp.py"; then
        echo "webapp:  running (PID $webapp_pid, log $WEBAPP_LOG)"
    elif [[ -n "$webapp_pid" ]]; then
        echo "webapp:  stopped (stale PID $webapp_pid in $WEBAPP_PIDFILE)"
    else
        echo "webapp:  stopped"
    fi
}

cmd_restart() {
    cmd_stop
    cmd_start
}

main() {
    [[ $# -ge 1 ]] || usage
    case "$1" in
        start) cmd_start ;;
        stop) cmd_stop ;;
        status) shift; cmd_status "$@" ;;
        restart) cmd_restart ;;
        webapp-start) _start_webapp ;;
        webapp-stop) cmd_webapp_stop ;;
        webapp-status) cmd_webapp_status ;;
        *) usage ;;
    esac
}

main "$@"
