# Matrix CLI — link module (sourced by bin/matrix)

link_append() {
    init_state
    local event="$1"; shift
    local subject="${1:-matrix}"; shift || true
    # Explicit attribution flags are stripped from the detail and appended as
    # structural tokens. project= is appended ONLY when --project= is passed
    # (never with a default); session_id= resolution is explicit flag >
    # MATRIX_SESSION_ID > current_session_id() (D2). Callers that pass no flags
    # produce byte-identical lines to before.
    local project="" sid_explicit=""
    local parts=()
    for arg in "$@"; do
        case "$arg" in
            --project=*) project="${arg#*=}" ;;
            --session=*) sid_explicit="${arg#*=}" ;;
            *) parts+=("$arg") ;;
        esac
    done
    local detail="${parts[*]}"
    event="$(printf '%s' "$event" | tr '\r\n' '  ')"
    subject="$(printf '%s' "$subject" | tr '\r\n' '  ')"
    detail="$(printf '%s' "$detail" | tr '\r\n' '  ')"
    if [[ "${detail##* }" != session_id=* ]]; then
        local sid="${sid_explicit:-}"
        [[ -z "$sid" ]] && sid="${MATRIX_SESSION_ID:-}"
        [[ -z "$sid" ]] && sid="$(current_session_id || true)"
        sid="$(printf '%s' "$sid" | tr '\r\n' '  ')"
        [[ -n "$sid" ]] && detail="${detail} session_id=${sid}"
    fi
    if [[ -n "$project" ]]; then
        project="$(printf '%s' "$project" | tr '\r\n' '  ')"
        detail="${detail} project=${project}"
    fi
    printf '%s | %-12s | %-16s | %s\n' "$(date -Iseconds)" "$event" "$subject" "$detail" >> "$ACTIVITY_LOG"
}

current_session_id() {
    MATRIX_ROOT="$MATRIX_DIR" python3 - "$HOOKS_DIR" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
import _common as c
sid = c.current_session_id()
print(sid if sid is not None else "")
PY
}

link_cmd() {
    if [[ "${1:-}" == "--validate" ]]; then
        init_state
        local invalid=0
        while IFS= read -r line; do
            if [[ ! "$line" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}[+-][0-9]{2}:[0-9]{2}[[:space:]]\|[[:space:]][^[:space:]\|]+[[:space:]]*\|[[:space:]][^[:space:]\|]+[[:space:]]*\| ]]; then
                printf '%s\n' "$line"
                invalid=1
            fi
        done < "$ACTIVITY_LOG"
        return "$invalid"
    fi

    local event="" subject="" ref="" project="" sid=""
    if [[ $# -lt 2 ]]; then
        log_error "Usage: matrix link <event> <subject> [--ref=<id>] [--project=<name>] [--session=<sid>] [detail...]"
        return 1
    fi
    event="$1"; subject="$2"; shift 2

    local details=()
    for arg in "$@"; do
        case "$arg" in
            --ref=*) ref="${arg#*=}" ;;
            --ref)   log_error "--ref requires a value"; return 1 ;;
            --project=*) project="${arg#*=}"
                [[ -n "$project" ]] || { log_error "--project requires a value"; return 1; } ;;
            --project)   log_error "--project requires a value"; return 1 ;;
            --session=*) sid="${arg#*=}"
                [[ -n "$sid" ]] || { log_error "--session requires a value"; return 1; } ;;
            --session)   log_error "--session requires a value"; return 1 ;;
            --*)     log_error "Unknown flag '$arg'"; return 1 ;;
            *)       details+=("$arg") ;;
        esac
    done

    case "$event" in
        route|decision|handoff) : ;;   # eventos bare documentados (AGENTS.md §7)
        *)
            if [[ ! "$event" =~ ^[a-z][a-z0-9-]*:[a-z][a-z0-9-]*$ ]]; then
                log_error "Invalid event '$event'. Must be <namespace>:<name> or one of: route, decision, handoff (lowercase, hyphenated)."
                return 1
            fi
            ;;
    esac

    local ns="${event%%:*}"
    if [[ "$event" == "phase:path-decision" ]]; then
        ns=""
    fi
    case "$ns" in
        project|build|install|harden|checkpoint|phase)
            log_error "Event namespace '$ns' is reserved for Layer 1 infrastructure."
            return 1
            ;;
    esac

    if [[ -z "$ref" ]]; then
        local slug; slug="${event//:/-}"
        ref="${slug}-$(epoch36 "")"
    fi

    if [[ -n "$project" ]]; then
        local resolved; resolved="$(resolve_project_arg "$project" 2>/dev/null || true)"
        [[ -n "$resolved" ]] || { log_error "Unknown project '$project' — pass a registered project or the reserved name 'matrix'"; return 1; }
        project="$resolved"
    fi

    local detail="[${ref}] ${details[*]}"
    local link_args=("$detail")
    [[ -n "$project" ]] && link_args+=(--project="$project")
    [[ -n "$sid" ]] && link_args+=(--session="$sid")
    link_append "$event" "$subject" "${link_args[@]}"
    echo "$ref"
}

