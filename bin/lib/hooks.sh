# Matrix CLI — hooks module (sourced by bin/matrix)

run_hook() {
    local name="${1:-}"
    if [[ -z "$name" || "$name" == "--help" || "$name" == "-h" ]]; then
        hooks_help
        [[ -n "$name" ]] && return 0 || return 1
    fi
    shift || true
    if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
        hook_help "$name"
        return 0
    fi
    local hook="$HOOKS_DIR/$name.py"
    [[ -f "$hook" ]] || {
        log_error "Hook '$name' not found at $hook — see 'matrix hooks --help' or docs/SYSTEM_TRUTH.md."
        return 1
    }
    if [[ -z "${1:-}" ]] && [[ -t 0 ]] && hook_requires_payload "$name"; then
        hook_help "$name"
        return 1
    fi
    MATRIX_ROOT="$MATRIX_DIR" python3 "$hook" "$@"
}

hook_requires_payload() {
    case "$1" in
        validate_phase_close|validate_routing_signal|session_close|post_run_audit|audit_event)
            return 0 ;;
        *) return 1 ;;
    esac
}

phase_schema_help() {
    cat <<'EOF'
Copyable JSON payload (phase develop):
{"phase":"develop","e2e":true,"evidence":"ran ./suite.sh; 12/12 passed","session_id":"<sid>"}

Field rules (outside the JSON):
  phase      spec|develop|test|eval  (required)
  e2e        JSON boolean true; required for develop/test/eval (spec may omit)
  evidence   string; non-trivial proof
  lesson     required when phase == eval (or reasoned N/A)
  session_id optional string; audit attribution
  plan, step optional strings; advisory only (precheck)
EOF
}

phase_help() {
    echo "Usage: matrix phase {close|precheck} '<json>'"
    echo "  close     reality gate; persists PASS/BLOCK to the Link ledger"
    echo "  precheck  dry-run; does NOT persist phase:close"
    echo "Schema and examples:  matrix phase close --help   (or precheck --help)"
}

phase_examples_help() {
    cat <<'EOF'

Examples (precheck accepts the same payloads; dry-run):
  matrix phase close '{"phase":"develop","e2e":true,"evidence":"ran ./suite.sh; 12/12 passed"}'
  matrix phase close '{"phase":"spec","evidence":"brain/output/plans/myplan.md"}'
  matrix phase close '{"phase":"eval","e2e":true,"evidence":"e2e suite + gate Smith PASS","lesson":"N/A - no new lesson"}'
EOF
}

phase_close_help() {
    echo "Usage: matrix phase close '<json>' — reality gate; persists PASS/BLOCK to the Link ledger."
    phase_schema_help
    phase_examples_help
}

phase_precheck_help() {
    echo "Usage: matrix phase precheck '<json>' — dry-run; does NOT persist phase:close."
    phase_schema_help
    phase_examples_help
}

session_close_help() {
    cat <<'EOF'
Usage: matrix session close '[<json>]'

Audits the session protocol (session_start, pre_activation_check, phase_close,
smith_gate) and appends a session:close ledger entry. Audits the PROCESS; it
does NOT replace 'phase close' (reality gate).

Copyable JSON payload: {"session_id":"<sid>"}
session_id is optional; falls back to the current session marker.

Examples:
  matrix session close '{"session_id":"vine-pastry"}'
  matrix session close
EOF
}

hooks_help() {
    cat <<'EOF'
Usage: matrix hooks <name> [json]

Runs a Seraph hook directly (low-level). It does NOT register phase:close or
session:close ledger entries. For the normal workflow use:
  matrix phase close / phase precheck
  matrix session close

Per-hook help:  matrix hooks <name> --help

Available hooks:
EOF
    local f
    for f in "$HOOKS_DIR"/*.py; do
        [[ -f "$f" ]] || continue
        local hname; hname="$(basename "$f" .py)"
        [[ "$hname" == _* ]] && continue
        echo "  $hname"
    done
}

hook_help() {
    local name="$1"
    echo "Usage: matrix hooks $name [json] — low-level; does NOT register phase:close/session:close."
    case "$name" in
        validate_phase_close|precheck_phase_close)
            phase_schema_help
            ;;
        validate_routing_signal|session_close)
            echo 'Payload: {"session_id":"<sid>"}  (optional; falls back to the current session marker)'
            ;;
        post_run_audit)
            echo 'Payload: {"agent":"<name>","session_id":"<sid>","steps":["session_start"],"required":["session_start"]}'
            ;;
        pre_activation_check)
            echo 'Payload: {"project":"<name>"}  (optional)'
            ;;
        audit_event)
            cat <<'EOF'
Payload: {"event":"post_tool_use","session_id":"<sid>"}   (event is required)
Side effect: appends to brain/state/hook-audit.jsonl. Invalid/empty payload BLOCKs without writing.
EOF
            ;;
        pre_exec_guard)
            echo 'Payload: {"tool_name":"<name>","tool_input":{...},"session_id":"<sid>"}'
            ;;
        validate_ship)
            echo 'Payload: {"ship":"<name>","project":"<name>"}'
            ;;
        detect_orphan_session)
            echo 'Payload: {"project_active":"<project>"}'
            ;;
        the_source)
            cat <<'EOF'
Payload: {"check":true}  (read-only validation)
WARNING: without a payload this hook GENERATES docs/SYSTEM_TRUTH.md.
EOF
            ;;
        *)
            if [[ -f "$HOOKS_DIR/$name.py" ]]; then
                echo "No payload required (noargs). See docs/SYSTEM_TRUTH.md."
            else
                log_error "Hook '$name' not found at $HOOKS_DIR/$name.py. Available hooks:"
                local f
                for f in "$HOOKS_DIR"/*.py; do
                    [[ -f "$f" ]] || continue
                    local hname; hname="$(basename "$f" .py)"
                    [[ "$hname" == _* ]] && continue
                    echo "  $hname"
                done
                return 1
            fi
            ;;
    esac
}

# Gate: Layer-2 CLI-neutrality must pass before any Trainman build/install.
require_layer2_clean() {
    local out rc=0
    out="$(run_hook validate_layer2 2>&1)" || rc=$?
    local ok
    ok="$(printf '%s' "$out" | jq -r '.ok // false' 2>/dev/null || echo false)"
    if [[ "$ok" != "true" ]]; then
        log_error "Layer-2 CLI-neutrality gate BLOCKED. Fix the following violations before build/install:"
        printf '%s\n' "$out" | jq -r '(.errors // [])[]' 2>/dev/null | while IFS= read -r err; do
            [[ -n "$err" ]] && log_error "  - $err"
        done
        return 1
    fi
}

# --- Artifact summary advisory check (D8) -----------------------------------
# Port of hooks/precheck_phase_close.py::check_artifact_summary, warn-only.
# Reads the same phase-close payload and emits a JSON array of warning strings.
check_artifact_summary_warn() {
    local payload="$1"
    local root="${MATRIX_DIR:-${MATRIX_ROOT:-$(pwd)}}"
    local field value raw_path referenced disk_path
    local re=$'brain/output/[^[:space:]"\'`]+|/tmp/[^[:space:]"\'`]+'
    local -a warns=()

    for field in evidence lesson; do
        value="$(printf '%s' "$payload" | jq -r --arg f "$field" '.[$f] // ""' 2>/dev/null || true)"
        [[ -z "$value" ]] && continue
        while IFS= read -r raw_path; do
            [[ -z "$raw_path" ]] && continue
            referenced="$(printf '%s' "$raw_path" | sed 's/[].,;:\)}]\+$//')"
            [[ "$referenced" == brain/output/* ]] || continue
            disk_path="$root/$referenced"
            [[ -f "$disk_path" && "$disk_path" == *.md ]] || continue
            if [[ ! -r "$disk_path" ]]; then
                warns+=("${field}: no se pudo leer ${referenced}: permiso denegado")
                continue
            fi
            if ! awk 'NF{c++; if($0 ~ /<!-- MATRIX:ARTIFACT-SUMMARY v1 -->/){f=1; exit}; if(c>=3){exit}} END{exit !f}' "$disk_path" 2>/dev/null; then
                warns+=("${field} referencia artefacto de salida sin el bloque MATRIX:ARTIFACT-SUMMARY v1 en sus primeras 3 lineas no vacias: ${referenced}")
            fi
        done < <(printf '%s' "$value" | grep -oE "$re" 2>/dev/null || true)
    done

    if [[ ${#warns[@]} -eq 0 ]]; then
        printf '[]\n'
    else
        printf '%s\n' "${warns[@]}" | jq -R '{source:"artifact_summary",detail:.}' | jq -s .
    fi
}

# --- Phase close (Seraph verdict → Link ledger) -----------------------------
# phase_close <json>
# Runs validate_phase_close, appends the verdict to the Link ledger (PASS *and*
# BLOCK), echoes the hook's JSON, and exits with the hook's exit code.
phase_close() {
    local payload="${1:-}"
    if [[ "$payload" == "--help" || "$payload" == "-h" ]]; then
        phase_close_help
        return 0
    fi
    [[ -z "$payload" ]] && { phase_close_help; return 1; }
    printf '%s' "$payload" | jq empty 2>/dev/null || {
        log_error "Invalid JSON payload. See 'matrix phase close --help' for the schema."; return 1; }
    if [[ "$(printf '%s' "$payload" | jq -r 'type' 2>/dev/null || true)" != "object" ]]; then
        log_error "Payload must be a JSON object. See 'matrix phase close --help' for the schema."
        return 1
    fi

    local out="" rc=0
    out="$(run_hook validate_phase_close "$payload")" || rc=$?

    local verdict phase evidence errs detail subject
    verdict="$(printf '%s' "$out"     | jq -r '.verdict // "UNKNOWN"' 2>/dev/null || echo UNKNOWN)"
    phase="$(printf '%s' "$out"       | jq -r '.phase   // "unknown"' 2>/dev/null || echo unknown)"
    errs="$(printf '%s' "$out"        | jq -r '(.errors // []) | join("; ")' 2>/dev/null | cut -c1-160 || true)"
    evidence="$(printf '%s' "$payload" | jq -r '(.evidence // "") | gsub("[\\r\\n|]+";" ")' 2>/dev/null | cut -c1-160 || true)"

    if [[ "$verdict" == "PASS" ]]; then detail="evidence=${evidence}"
    else                                detail="errors=${errs} | evidence=${evidence}"; fi

    local artifact_warns_json="[]" artifact_count=0
    artifact_warns_json="$(check_artifact_summary_warn "$payload")" || artifact_warns_json="[]"
    artifact_count="$(printf '%s' "$artifact_warns_json" | jq 'length' 2>/dev/null || echo 0)"
    detail="${detail} | artifact_summary_warns=${artifact_count}"

    if printf '%s' "$out" | jq -e 'has("warns")' >/dev/null 2>&1; then
        out="$(printf '%s' "$out" | jq --argjson extra "$artifact_warns_json" '.warns += $extra')"
    else
        out="$(printf '%s' "$out" | jq --argjson extra "$artifact_warns_json" '. + {warns: $extra}' 2>/dev/null || printf '{"warns":%s}' "$artifact_warns_json")"
    fi

    subject="$(resolve_scope_project || true)"
    subject="${subject:-matrix}"
    link_append "phase:close" "$subject" "$verdict | phase=${phase} | ${detail}"

    local sid="" sid_kind
    sid_kind="$(printf '%s' "$payload" | jq -r 'if has("session_id") then (.session_id | type) else "absent" end' 2>/dev/null || echo absent)"
    if [[ "$sid_kind" == "string" ]]; then
        sid="$(printf '%s' "$payload" | jq -r '.session_id' 2>/dev/null || true)"
    elif [[ "$sid_kind" == "absent" ]]; then
        sid="$(current_session_id || true)"
    fi
    if [[ -n "$sid" ]]; then
        local audit_event_name audit_json
        if [[ "$verdict" == "PASS" ]]; then
            audit_event_name="phase_close"
        else
            audit_event_name="phase_close_blocked"
        fi
        audit_json="$(jq -n --arg event "$audit_event_name" --arg sid "$sid" '{event:$event, session_id:$sid}' 2>/dev/null || true)"
        [[ -n "$audit_json" ]] && run_hook audit_event "$audit_json" >/dev/null || true
    fi

    printf '%s\n' "$out"
    return $rc
}

phase_precheck() {
    local payload="${1:-}"
    if [[ "$payload" == "--help" || "$payload" == "-h" ]]; then
        phase_precheck_help
        return 0
    fi
    [[ -z "$payload" ]] && { phase_precheck_help; return 1; }
    printf '%s' "$payload" | jq empty 2>/dev/null || {
        log_error "Invalid JSON payload. See 'matrix phase precheck --help' for the schema."; return 1; }
    if [[ "$(printf '%s' "$payload" | jq -r 'type' 2>/dev/null || true)" != "object" ]]; then
        log_error "Payload must be a JSON object. See 'matrix phase precheck --help' for the schema."
        return 1
    fi

    local layer_a="" layer_a_rc=0
    layer_a="$(run_hook validate_phase_close "$payload")" || layer_a_rc=$?
    printf '%s\n' "$layer_a"

    local verdict phase layer_b_verdict="SKIPPED" subject
    verdict="$(printf '%s' "$layer_a" | jq -r '.verdict // "BLOCK"' 2>/dev/null || echo BLOCK)"
    phase="$(printf '%s' "$layer_a" | jq -r '.phase // "unknown"' 2>/dev/null || echo unknown)"

    if [[ "$verdict" == "PASS" && $layer_a_rc -eq 0 ]]; then
        local layer_b="" layer_b_rc=0
        layer_b="$(run_hook precheck_phase_close "$payload")" || layer_b_rc=$?
        printf '%s\n' "$layer_b"
        layer_b_verdict="$(printf '%s' "$layer_b" | jq -r '.verdict // "WARN"' 2>/dev/null || echo WARN)"
        [[ "$layer_b_verdict" == "PASS" ]] || verdict="WARN"
    fi

    subject="$(resolve_scope_project || true)"
    subject="${subject:-matrix}"
    link_append "phase:precheck" "$subject" "$verdict | phase=${phase} | capa_b=${layer_b_verdict}"
    return $layer_a_rc
}

phase_cmd() {
    case "${1:-}" in
        --help|-h) phase_help ;;
        close)    shift; phase_close "${1:-}" ;;
        precheck) shift; phase_precheck "${1:-}" ;;
        "")       phase_help; return 1 ;;
        *)        log_error "Usage: matrix phase {close|precheck} '<json>' — see 'matrix phase close --help'"; return 1 ;;
    esac
}

# --- Session close (Seraph audit → Link ledger) -----------------------------
# session_close [json]
# Runs the session_close hook, appends a session:close entry to the Link ledger,
# echoes the hook's JSON, and exits with the hook's exit code.
session_close() {
    local payload="${1:-}"
    if [[ "$payload" == "--help" || "$payload" == "-h" ]]; then
        session_close_help
        return 0
    fi
    if [[ -n "$payload" ]]; then
        printf '%s' "$payload" | jq empty 2>/dev/null || {
            log_error "Invalid JSON payload. Usage: matrix session close '[<json>]'"; return 1; }
        if [[ "$(printf '%s' "$payload" | jq -r 'type' 2>/dev/null || true)" != "object" ]]; then
            log_error "Payload must be a JSON object. Usage: matrix session close '[<json>]'"
            return 1
        fi
    fi

    local out="" rc=0
    out="$(run_hook session_close "$payload")" || rc=$?

    local sid ok phase_close_missing detail subject
    sid="$(printf '%s' "$out"     | jq -r '.session_id // ""' 2>/dev/null || true)"
    ok="$(printf '%s' "$out"      | jq -r '.ok // false' 2>/dev/null || echo false)"
    phase_close_missing="$(printf '%s' "$out" | jq -r '.phase_close_missing // false' 2>/dev/null || echo false)"

    subject="$sid"
    [[ -z "$subject" || "$subject" == "null" ]] && subject="matrix"
    detail="ok=${ok}"
    [[ "$phase_close_missing" == "true" ]] && detail="${detail} | missing=phase_close"

    link_append "session:close" "$subject" "$detail"

    printf '%s\n' "$out"
    return $rc
}

session_cmd() {
    case "${1:-}" in
        close) shift; session_close "${1:-}" ;;
        --help|-h) session_close_help ;;
        "") session_close_help; return 1 ;;
        *)     log_error "Usage: matrix session close '[<json>]'"; return 1 ;;
    esac
}

# --- Hardline queue ---------------------------------------------------------
