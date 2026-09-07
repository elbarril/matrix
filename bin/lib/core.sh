# Matrix CLI — core module (sourced by bin/matrix)

# Colors
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
resolve_root() {
    # 1) If a _brain symlink exists in cwd and resolves to a real directory,
    #    the Matrix root is its parent. If it is broken or points elsewhere, fall
    #    through to traversal so MATRIX_DIR is never set to garbage (e.g. ".").
    if [[ -L "_brain" ]]; then
        local brain_path; brain_path="$(readlink -f _brain 2>/dev/null || true)"
        if [[ -n "$brain_path" && -d "$brain_path" ]]; then
            dirname "$brain_path"; return 0
        fi
    fi
    # 2) Walk up from the script location until brain/ + AGENTS.md are found.
    local dir; dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
    while [[ "$dir" != "/" ]]; do
        if [[ -d "$dir/brain" && -f "$dir/AGENTS.md" ]]; then echo "$dir"; return 0; fi
        dir="$(dirname "$dir")"
    done
    # 3) MATRIX_ROOT env fallback when the filesystem markers are not discoverable.
    if [[ -n "${MATRIX_ROOT:-}" && -d "$MATRIX_ROOT/brain" ]]; then
        echo "$MATRIX_ROOT"; return 0
    fi
    # 4) Last resort: parent of bin/.
    cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd
}

MATRIX_DIR="$(resolve_root)"
REGISTRY_FILE="$MATRIX_DIR/.registry.json"
BRAIN_DIR="$MATRIX_DIR/brain"
STATE_DIR="$BRAIN_DIR/state"
CLIENTS_DIR="$MATRIX_DIR/clients"
WORKSPACE_FILE="$STATE_DIR/workspace.yaml"
ACTIVITY_LOG="$STATE_DIR/activity.log"
CHECKPOINTS_FILE="$STATE_DIR/checkpoints.jsonl"
HARDLINE_DIR="$STATE_DIR/hardline"
HARDLINE_QUEUE="$HARDLINE_DIR/queue.jsonl"
HOOKS_DIR="$MATRIX_DIR/hooks"

# The subject under which Matrix's own work is recorded (Matrix workspace mode).
MATRIX_WORKSPACE_PROJECT="matrix"

# is_workspace_target: does this dispatch/lookup target name refer to the
# Matrix workspace itself (the special, always-available, never-bound
# pseudo-project), as opposed to a real registered project? Single source
# of truth for that one question — mirrors the sentinel resolve_scope()
# already uses for the cwd-based version of the same question.
is_workspace_target() {
    [[ "$1" == "$MATRIX_WORKSPACE_PROJECT" ]]
}

to_abs_path() {
    local p="${1:-}"
    p="${p/#\~/$HOME}"
    [[ -z "$p" || "$p" == "null" ]] && { echo "$p"; return; }
    if [[ "$p" == /* ]]; then
        echo "${p%/}"
    else
        echo "${MATRIX_DIR}/${p#./}" | sed 's#//*#/#g'
    fi
}

epoch36() {
    # Convert the current Unix timestamp to a short base-36 slug.
    python3 - "$1" << 'PY'
import sys, time, string
n = int(sys.argv[1]) if sys.argv[1] else int(time.time())
chars = string.digits + string.ascii_lowercase
out = ""
while n:
    n, r = divmod(n, 36)
    out = chars[r] + out
print(out or "0")
PY
}

log_info()    { echo -e "${BLUE}[MATRIX]${NC} $1"; }
log_success() { echo -e "${GREEN}[MATRIX]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[MATRIX]${NC} $1"; }
log_error()   { echo -e "${RED}[MATRIX]${NC} $1"; }

# --- Global lock ------------------------------------------------------------
acquire_lock() {
    if [[ -n "${MATRIX_LOCKED:-}" ]]; then
        return 0
    fi
    if ! command -v flock >/dev/null 2>&1; then
        log_warning "flock not available; running without global lock"
        return 0
    fi
    mkdir -p "$STATE_DIR"
    exec 200>"$STATE_DIR/.matrix.lock"
    flock -x -w 30 200 || { log_error "Could not acquire global lock (timeout?)"; exit 1; }
    export MATRIX_LOCKED=1
}
release_lock() {
    if command -v flock >/dev/null 2>&1; then
        exec 200>&- 2>/dev/null || true
    fi
}

# --- Init -------------------------------------------------------------------
init_registry() {
    [[ -f "$REGISTRY_FILE" ]] || echo '{"projects": [], "created": "'$(date -Iseconds)'", "version": "2.0.0"}' > "$REGISTRY_FILE"
}
init_state() {
    mkdir -p "$STATE_DIR/sessions"
    [[ -f "$ACTIVITY_LOG" ]] || : > "$ACTIVITY_LOG"
    [[ -f "$CHECKPOINTS_FILE" ]] || : > "$CHECKPOINTS_FILE"
    [[ -f "$WORKSPACE_FILE" ]] || cat > "$WORKSPACE_FILE" << 'EOF'
# Matrix Workspace State — the SET of warm projects (multi-project)
active_projects: []
last_updated: null
EOF
}

# --- Link ledger ------------------------------------------------------------
# Append an event: link_append <event> <subject> <detail...>
# The ledger is one event per line (readers like show_activity/link --validate
# parse it that way), so any embedded CR/LF is flattened to a space before
# writing. Found by Smith during the workflows-lifecycle-fix gate: a caller
# that ever passed a multi-line detail directly with printf (pre-dating
# link_append) is what produced the corrupted multi-line block in
# activity.log lines 270-283. This is the one place that must never regress.
