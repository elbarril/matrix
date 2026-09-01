# Matrix CLI — hardline module (sourced by bin/matrix)

init_hardline() {
    mkdir -p "$HARDLINE_DIR"
    touch "$HARDLINE_QUEUE"
}

hardline_replace_event() {
    local event_json="$1" queue_fd tmp
    init_hardline
    exec {queue_fd}>"$HARDLINE_DIR/.queue.lock"
    flock -x "$queue_fd"
    tmp="$(mktemp "$HARDLINE_DIR/queue.jsonl.XXXXXX")"
    jq -s -c --argjson event "$event_json" \
        'if any(.[]; .event_id == $event.event_id) then map(if .event_id == $event.event_id then $event else . end) else . + [$event] end | .[]' \
        "$HARDLINE_QUEUE" > "$tmp"
    mv "$tmp" "$HARDLINE_QUEUE"
    exec {queue_fd}>&-
}

# Heuristic: does the input look like it contains a secret (token, password, etc.)?
# Shared by hardline_dispatch and hardline_reject so early rejects never persist
# secret-looking text to queue.jsonl.
_hardline_looks_like_secret() {
    printf '%s' "$1" | grep -qiE '\b(token|password|secret|api[_-]?key)([[:space:]]+[[:alnum:]_.-]+){0,2}[[:space:]]*[:=][[:space:]]*[^[:space:]]+'
}

# Build and append an acked-refused-generic row to queue.jsonl for an
# early-rejected hardline event, with the same dedupe_key calculation a normal
# dispatch would use. Secrets are redacted before writing, reusing the existing
# secret heuristic. Pure queue write: no link_append/log call of its own, so
# callers that already have their own Link event/log line don't get a duplicate.
_hardline_write_reject_row() {
    local project="$1" raw_line="$2" reason="$3"
    local event_id dedupe_key now safe_line event_json queue_fd tmp
    init_hardline
    event_id="hardline-$(epoch36 "$(date +%s)")-$$-$RANDOM"
    dedupe_key="$(printf '%s\0%s' "$project" "$raw_line" | sha256sum | cut -d' ' -f1)"
    now="$(date -Iseconds)"
    safe_line="$raw_line"
    _hardline_looks_like_secret "$raw_line" && safe_line="[REDACTED]"

    event_json="$(jq -n -c \
        --arg id "$event_id" --arg project "$project" --arg line "$safe_line" \
        --arg key "$dedupe_key" --arg now "$now" --arg reason "$reason" \
        '{event_id:$id,project:$project,raw_line:$line,dedupe_key:$key,
          state:"acked-refused-generic",session_id:null,queued_at:$now,
          dispatched_at:null,acked_at:$now,ack_kind:"refused-generic",
          reject_reason:$reason}')"

    exec {queue_fd}>"$HARDLINE_DIR/.queue.lock"
    flock -x "$queue_fd"
    tmp="$(mktemp "$HARDLINE_DIR/queue.jsonl.XXXXXX")"
    cat "$HARDLINE_QUEUE" > "$tmp" 2>/dev/null || true
    printf '%s\n' "$event_json" >> "$tmp"
    mv "$tmp" "$HARDLINE_QUEUE"
    exec {queue_fd}>&-
    printf '%s' "$event_id"
}

# Persist an early-rejected hardline event to queue.jsonl as acked-refused-generic,
# plus its own Link event and log line. Thin wrapper over
# _hardline_write_reject_row for callers (hardline_dispatch's early validation,
# and the `matrix hardline reject` subcommand) that don't already emit their own
# Link event for this rejection.
hardline_reject() {
    local project="$1" raw_line="$2" reason="$3"
    local event_id
    event_id="$(_hardline_write_reject_row "$project" "$raw_line" "$reason")"
    link_append "hardline:reject" "$project" "[$event_id] state=acked-refused-generic reason=$reason"
    log_error "$reason"
}

hardline_dispatch() {
    local project="${1:-}" raw_line="${2:-}"
    [[ $# -eq 2 && -n "$project" && -n "$raw_line" ]] || {
        log_error 'Usage: matrix hardline dispatch <project> "<line>"'; return 1; }
    [[ "$project" =~ ^[A-Za-z0-9._-]+$ ]] || {
        hardline_reject "$project" "$raw_line" "Invalid project '$project' (allowed: letters, numbers, dot, underscore, hyphen)"; return 1; }
    [[ "$raw_line" != *$'\n'* && "$raw_line" != *$'\r'* ]] || {
        hardline_reject "$project" "$raw_line" "Hardline events must be a single line"; return 1; }

    local project_path
    if is_workspace_target "$project"; then
        project_path="$MATRIX_DIR"
    else
        get_project_path "$project" >/dev/null 2>&1 || {
            hardline_reject "$project" "$raw_line" "Project '$project' not found"; return 1; }
        is_bound "$project" || {
            hardline_reject "$project" "$raw_line" "Project '$project' is not bound"; return 1; }
        project_path="$(get_project_path "$project")"
    fi

    local event_id dedupe_key now event_json queue_fd existing tmp max_depth open_count
    event_id="hardline-$(epoch36 "$(date +%s)")-$$-$RANDOM"
    dedupe_key="$(printf '%s\0%s' "$project" "$raw_line" | sha256sum | cut -d' ' -f1)"
    max_depth="${MATRIX_HARDLINE_MAX_DEPTH:-20}"

    if _hardline_looks_like_secret "$raw_line"; then
        _hardline_write_reject_row "$project" "$raw_line" \
            "contenido con forma de secreto detectado antes de despachar; evento descartado sin ejecutar" >/dev/null
        link_append "hardline:skip-secret" "$project" "[$event_id] event_id=$event_id marker=[REDACTED]"
        log_warning "Skipped secret-looking Hardline event $event_id (redacted)"
        return 0
    fi

    init_hardline
    exec {queue_fd}>"$HARDLINE_DIR/.queue.lock"
    flock -x "$queue_fd"
    existing="$(jq -r --arg key "$dedupe_key" '
        select(.dedupe_key == $key and (.state == "queued" or .state == "dispatched" or .state == "orphaned" or .state == "resumed" or .state == "requeued")) | .event_id
    ' "$HARDLINE_QUEUE" 2>/dev/null | tail -n 1)"
    if [[ -n "$existing" ]]; then
        exec {queue_fd}>&-
        link_append "hardline:deduped" "$project" "[$event_id] duplicate_of=$existing"
        log_warning "Duplicate event; existing open event: $existing"
        return 0
    fi

    # Backpressure: bounded FIFO per project. Refuse new inbound when the project
    # already has max_depth open events; never silently drop or evict existing.
    open_count="$(jq -s -r --arg project "$project" '
        [ .[] | select(.project == $project and (.state == "queued" or .state == "dispatched" or .state == "orphaned" or .state == "resumed" or .state == "requeued")) ] | length
    ' "$HARDLINE_QUEUE" 2>/dev/null || echo 0)"
    if [[ "$open_count" -ge "$max_depth" ]]; then
        exec {queue_fd}>&-
        _hardline_write_reject_row "$project" "$raw_line" \
            "el proyecto ya tiene $open_count eventos abiertos (límite $max_depth); rechazado para no acumular backlog sin límite" >/dev/null
        link_append "hardline:backpressure-refused" "$project" "[$event_id] reason=max_depth open=$open_count max=$max_depth"
        log_warning "Hardline backpressure: project '$project' has $open_count open events (max $max_depth); event $event_id refused"
        return 1
    fi

    now="$(date -Iseconds)"
    event_json="$(jq -n -c \
        --arg id "$event_id" --arg project "$project" --arg line "$raw_line" \
        --arg key "$dedupe_key" --arg queued "$now" \
        '{event_id:$id,project:$project,raw_line:$line,dedupe_key:$key,state:"queued",session_id:null,queued_at:$queued,dispatched_at:null,acked_at:null,ack_kind:null}')"
    tmp="$(mktemp "$HARDLINE_DIR/queue.jsonl.XXXXXX")"
    cat "$HARDLINE_QUEUE" > "$tmp"
    printf '%s\n' "$event_json" >> "$tmp"
    mv "$tmp" "$HARDLINE_QUEUE"
    exec {queue_fd}>&-
    link_append "hardline:dispatch" "$project" "[$event_id] state=queued"
    printf '[hardline] %s queued project=%s event=%s\n' "$(date +%s.%N)" "$project" "$event_id"

    local project_fd hold_seconds="${MATRIX_HARDLINE_TEST_HOLD_SECONDS:-0}"
    exec {project_fd}>"$HARDLINE_DIR/$project.lock"
    if ! flock -n "$project_fd"; then
        printf '[hardline] %s waiting project=%s event=%s\n' "$(date +%s.%N)" "$project" "$event_id"
        flock -x "$project_fd"
    fi
    printf '[hardline] %s acquired project=%s event=%s\n' "$(date +%s.%N)" "$project" "$event_id"

    now="$(date -Iseconds)"
    event_json="$(jq -c --arg ts "$now" '.state = "dispatched" | .dispatched_at = $ts' <<< "$event_json")"
    hardline_replace_event "$event_json"
    link_append "hardline:dispatch" "$project" "[$event_id] state=dispatched layer3=pending"

    if [[ "$hold_seconds" =~ ^[0-9]+([.][0-9]+)?$ ]] && [[ "$hold_seconds" != "0" ]]; then
        sleep "$hold_seconds"
    fi

    printf '[hardline] %s ready project=%s event=%s layer3=invoking\n' "$(date +%s.%N)" "$project" "$event_id"

    local adapter_json adapter_out adapter_err ack_kind session_id timeout_happened ack_state now2
    adapter_out="$(mktemp "$HARDLINE_DIR/adapter.out.XXXXXX")"
    adapter_err="$HARDLINE_DIR/events/$event_id.adapter.err"
    mkdir -p "$HARDLINE_DIR/events"
    if MATRIX_ROOT="$MATRIX_DIR" MATRIX_HARDLINE_TIMEOUT_SECONDS="${MATRIX_HARDLINE_TIMEOUT_SECONDS:-300}" \
       "$MATRIX_DIR/adapters/devin/hardline-dispatch.sh" "$project_path" "$raw_line" "" "$event_id" > "$adapter_out" 2> "$adapter_err"; then
        : # adapter executed
    else
        printf '[hardline] %s adapter-internal-error project=%s event=%s\n' "$(date +%s.%N)" "$project" "$event_id" >&2
    fi
    adapter_json="$(cat "$adapter_out" || true)"
    rm -f "$adapter_out"

    ack_kind="$(printf '%s' "$adapter_json" | jq -r '.ack_kind // "failure"')"
    timeout_happened="$(printf '%s' "$adapter_json" | jq -r '.timeout // false')"
    session_id="$(printf '%s' "$adapter_json" | jq -r '.session_id // ""')"

    now2="$(date -Iseconds)"
    if [[ "$timeout_happened" == "true" ]]; then
        ack_state="orphaned"
        event_json="$(jq -c --arg ts "$now2" --arg sid "$session_id" '.state = "orphaned" | .acked_at = $ts | .session_id = $sid' <<< "$event_json")"
        link_append "hardline:orphaned" "$project" "[$event_id] session_id=$session_id reason=timeout"
    else
        ack_state="acked-$ack_kind"
        event_json="$(jq -c --arg state "$ack_state" --arg ts "$now2" --arg kind "$ack_kind" --arg sid "$session_id" '.state = $state | .acked_at = $ts | .ack_kind = $kind | .session_id = $sid' <<< "$event_json")"
        link_append "hardline:ack" "$project" "[$event_id] state=$ack_state session_id=$session_id"
    fi
    hardline_replace_event "$event_json"
    printf '[hardline] %s ack project=%s event=%s state=%s session_id=%s\n' "$(date +%s.%N)" "$project" "$event_id" "$ack_state" "$session_id"

    exec {project_fd}>&-
}

hardline_status() {
    local project="${1:-}"
    [[ $# -le 1 ]] || { log_error "Usage: matrix hardline status [project]"; return 1; }
    init_hardline
    jq -r --arg project "$project" '
        select(($project == "" or .project == $project) and
               (.state == "queued" or .state == "dispatched" or .state == "orphaned" or .state == "resumed" or .state == "requeued")) |
        [.event_id, .project, .state, .queued_at, (.session_id // "-")] | @tsv
    ' "$HARDLINE_QUEUE"
}

hardline_resume() {
    local event_id="${1:-}"
    [[ $# -eq 1 && -n "$event_id" ]] || { log_error "Usage: matrix hardline resume <event_id>"; return 1; }
    init_hardline
    jq -e --arg id "$event_id" 'select(.event_id == $id)' "$HARDLINE_QUEUE" >/dev/null || {
        log_error "Hardline event '$event_id' not found"; return 1; }
    log_warning "Hardline resume is not yet implemented — full session recovery remains an open gap (Fase 4 closed without it; not owned by any currently active phase, see hardline-afk plan)"
    return 2
}

hardline_reject_cmd() {
    # Project and line may legitimately be empty here: the empty-field branch in
    # hardline-monitor.sh calls this exact subcommand precisely because one of
    # them came out empty after splitting on '|'. Only the reason is required.
    [[ $# -eq 3 && -n "$3" ]] || {
        log_error 'Usage: matrix hardline reject <project> "<line>" "<reason>"'; return 1; }
    hardline_reject "$1" "$2" "$3"
}

hardline_cmd() {
    case "${1:-}" in
        dispatch) shift; hardline_dispatch "$@" ;;
        reject)   shift; hardline_reject_cmd "$@" ;;
        status)   shift; hardline_status "$@" ;;
        resume)   shift; hardline_resume "$@" ;;
        queue)    shift; [[ $# -eq 0 ]] || { log_error "Usage: matrix hardline queue"; return 1; }
                  init_hardline; cat "$HARDLINE_QUEUE" ;;
        *)        log_error 'Usage: matrix hardline dispatch <project> "<line>" | reject <project> "<line>" "<reason>" | status [project] | resume <event_id> | queue'; return 1 ;;
    esac
}

# --- Adapter template helpers ------------------------------------------------
