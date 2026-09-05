# Matrix CLI — hooks module (sourced by bin/matrix)

run_hook() {
    local name="$1"; shift || true
    local hook="$HOOKS_DIR/$name.py"
    [[ -f "$hook" ]] || { log_error "Hook '$name' not found at $hook"; return 1; }
    MATRIX_ROOT="$MATRIX_DIR" python3 "$hook" "$@"
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
    [[ -z "$payload" ]] && { log_error "Usage: matrix phase close '<json>'"; return 1; }
    printf '%s' "$payload" | jq empty 2>/dev/null || {
        log_error "Invalid JSON payload. Usage: matrix phase close '<json>'"; return 1; }

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

    local sid; sid="$(current_session_id || true)"
    if [[ -n "$sid" ]]; then
        local audit_event_name
        if [[ "$verdict" == "PASS" ]]; then
            audit_event_name="phase_close"
        else
            audit_event_name="phase_close_blocked"
        fi
        run_hook audit_event "{\"event\":\"$audit_event_name\",\"session_id\":\"$sid\"}" >/dev/null || true
    fi

    printf '%s\n' "$out"
    return $rc
}

phase_precheck() {
    local payload="${1:-}"
    [[ -z "$payload" ]] && { log_error "Usage: matrix phase precheck '<json>'"; return 1; }
    printf '%s' "$payload" | jq empty 2>/dev/null || {
        log_error "Invalid JSON payload. Usage: matrix phase precheck '<json>'"; return 1; }

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
        close)    shift; phase_close "${1:-}" ;;
        precheck) shift; phase_precheck "${1:-}" ;;
        *)        log_error "Usage: matrix phase {close|precheck} '<json>'"; return 1 ;;
    esac
}

# --- Session close (Seraph audit → Link ledger) -----------------------------
# session_close [json]
# Runs the session_close hook, appends a session:close entry to the Link ledger,
# echoes the hook's JSON, and exits with the hook's exit code.
session_close() {
    local payload="${1:-}"
    if [[ -n "$payload" ]]; then
        printf '%s' "$payload" | jq empty 2>/dev/null || {
            log_error "Invalid JSON payload. Usage: matrix session close '[<json>]'"; return 1; }
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
        *)     log_error "Usage: matrix session close '[<json>]'"; return 1 ;;
    esac
}

# --- Hardline queue ---------------------------------------------------------
