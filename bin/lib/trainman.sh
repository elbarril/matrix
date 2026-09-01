# Matrix CLI — trainman module (sourced by bin/matrix)

_adapter_model_templates() {
    local target="$1"
    python3 - "$MATRIX_DIR/adapters/$target/adapter.yaml" <<'PY'
import sys, os

def parse_scalar_list(raw):
    v = raw.split("#", 1)[0].strip()
    if v.startswith("[") and v.endswith("]"):
        v = v[1:-1]
    if not v:
        return []
    return [item.strip().strip('"').strip("'") for item in v.split(",") if item.strip()]

adapter_yaml = sys.argv[1]
if not os.path.isfile(adapter_yaml):
    sys.exit(0)
with open(adapter_yaml, encoding="utf-8") as fh:
    for raw in fh:
        stripped = raw.split("#", 1)[0].strip()
        if stripped.startswith("model_templates:"):
            v = stripped.split(":", 1)[1].strip()
            if v.startswith("["):
                print(" ".join(parse_scalar_list(v)))
            break
PY
}

_persist_adapter_template() {
    local target="$1" template="$2"
    local state_file="$STATE_DIR/adapter-templates.json"
    mkdir -p "$STATE_DIR"
    if [[ -f "$state_file" ]]; then
        local tmp; tmp="$(mktemp)"
        jq --arg t "$target" --arg n "$template" '.[$t] = $n' "$state_file" > "$tmp" && mv "$tmp" "$state_file"
    else
        echo "{\"$target\": \"$template\"}" > "$state_file"
    fi
}

_read_persisted_adapter_template() {
    local target="$1"
    local state_file="$STATE_DIR/adapter-templates.json"
    [[ -f "$state_file" ]] || return 1
    jq -r --arg t "$target" '.[$t] // empty' "$state_file" 2>/dev/null
}

# --- Trainman build ---------------------------------------------------------
build_target() {
    local target="" template="" arg
    for arg in "$@"; do
        case "$arg" in
            --target=*) target="${arg#*=}" ;;
            --template=*) template="${arg#*=}" ;;
        esac
    done
    [[ -z "$target" ]] && { log_error "Usage: matrix build --target=<cli> [--template=<name>]"; return 1; }
    require_layer2_clean || return 1
    local builder="$MATRIX_DIR/adapters/$target/build.sh"
    [[ -x "$builder" ]] || { log_warning "Trainman: no adapter builder at $builder (not implemented yet for '$target')."; return 1; }

    if [[ -n "$template" ]]; then
        local valid_templates found=0 t
        valid_templates="$(_adapter_model_templates "$target")"
        for t in $valid_templates; do
            [[ "$t" == "$template" ]] && { found=1; break; }
        done
        if [[ $found -eq 0 ]]; then
            log_error "Invalid template '$template' for target '$target'. Valid: ${valid_templates// /, }"
            return 1
        fi
        _persist_adapter_template "$target" "$template"
    else
        template="$(_read_persisted_adapter_template "$target" 2>/dev/null || true)"
        if [[ -z "$template" ]]; then
            template="equilibrado"
            _persist_adapter_template "$target" "$template"
        fi
    fi

    log_info "Trainman: building artifacts for '$target' (template=$template)..."
    MATRIX_ROOT="$MATRIX_DIR" MATRIX_ADAPTER_TEMPLATE="$template" "$builder" ${template:+--template="$template"}
    link_append "build" "$target" "artifacts generated (template=$template)"
}

# --- Trainman harden (reconcile permissions.deny with secret-deny config) ----
harden_target() {
    local target=""
    for arg in "$@"; do case "$arg" in --target=*) target="${arg#*=}";; esac; done
    [[ -z "$target" ]] && { log_error "Usage: matrix harden --target=<cli> [--apply] [--revert]"; return 1; }
    local hardener="$MATRIX_DIR/adapters/$target/harden.sh"
    if [[ -x "$hardener" ]]; then
        log_info "Trainman: hardening permissions.deny for '$target'..."
        MATRIX_ROOT="$MATRIX_DIR" "$hardener" "$@"
        link_append "harden" "$target" "permissions.deny reconciled"
    else
        log_warning "Trainman: no hardener at $hardener (not implemented yet for '$target')."
        return 1
    fi
}

# --- Trainman install (deploy artifacts into the host CLI's discovery path) --
install_target() {
    local target=""
    for arg in "$@"; do case "$arg" in --target=*) target="${arg#*=}";; esac; done
    [[ -z "$target" ]] && { log_error "Usage: matrix install --target=<cli>"; return 1; }
    require_layer2_clean || return 1
    local installer="$MATRIX_DIR/adapters/$target/install.sh"
    if [[ -x "$installer" ]]; then
        log_info "Trainman: installing artifacts for '$target' into the discovery path..."
        MATRIX_ROOT="$MATRIX_DIR" "$installer"
        link_append "install" "$target" "artifacts deployed"
    else
        log_warning "Trainman: no adapter installer at $installer (not implemented yet for '$target')."
        return 1
    fi
}

# --- Devin session retrospectives ------------------------------------------
session_query() {
    local subcmd="$1"; shift
    local target="devin"
    local args=()
    local arg
    for arg in "$@"; do
        case "$arg" in
            --target=*) target="${arg#*=}" ;;
            *) args+=("$arg") ;;
        esac
    done
    local query="$MATRIX_DIR/adapters/$target/session_query.py"
    if [[ -x "$query" ]]; then
        python3 "$query" "$subcmd" "${args[@]}"
    else
        log_warning "Trainman: no session query at $query (not implemented yet for '$target')."
        return 1
    fi
}

session_report() {
    local target="devin"
    local args=()
    local arg
    for arg in "$@"; do
        case "$arg" in
            --target=*) target="${arg#*=}" ;;
            *) args+=("$arg") ;;
        esac
    done
    local report="$MATRIX_DIR/adapters/$target/session_report.py"
    if [[ -x "$report" ]]; then
        python3 "$report" "${args[@]}"
    else
        log_warning "Trainman: no session report at $report (not implemented yet for '$target')."
        return 1
    fi
}

