# Matrix CLI — registry module (sourced by bin/matrix)

read_registry() { init_registry; jq -r '.projects[] | "\(.name)\t\(.path)\t\(.type)"' "$REGISTRY_FILE" 2>/dev/null || echo ""; }

# --- Single source of truth: mode + subject resolution ----------------------
# resolve_scope: answers "where am I?" exactly once, for every call-site.
# Prints: <mode>\t<project>\t<detail>
#   workspace           matrix   <matrix root>   cwd is inside the Matrix repo itself
#   project             <name>   <project root>  cwd is inside a registered project (registry-path walk-up)
#   none                (empty)  (empty)         no registered project found walking up
#
# THE RULE: innermost root wins. Walking up from cwd, the first directory that
# is either the Matrix root or a registered project root decides. There is no
# filesystem binding (`_brain`) anymore: a project is in scope when its registry
# path is an ancestor of cwd. This handles all real topologies with one rule and
# no special cases:
#   (a) the Matrix repo living inside a registered project (emi ⊃ matrix) → workspace
#   (b) a registered project living inside the Matrix repo (clients/<name>, type:remote)
#   (c) a registered project inside another registered project (pas ⊃ sandisk) → project, innermost wins
resolve_scope() {
    local matrix_real; matrix_real="$(readlink -f "$MATRIX_DIR" 2>/dev/null || echo "$MATRIX_DIR")"
    local dir;         dir="$(readlink -f "$PWD" 2>/dev/null || echo "$PWD")"
    while :; do
        if [[ "$dir" == "$matrix_real" ]]; then
            printf '%s\t%s\t%s\n' "workspace" "$MATRIX_WORKSPACE_PROJECT" "$matrix_real"
            return 0
        fi
        local n; n="$(registry_name_for_path "$dir" 2>/dev/null || true)"
        if [[ -n "$n" ]]; then
            local p; p="$(get_project_path "$n")"
            printf '%s\t%s\t%s\n' "project" "$n" "$(readlink -f "$p" 2>/dev/null || echo "$p")"
            return 0
        fi
        [[ "$dir" == "/" ]] && break
        dir="$(dirname "$dir")"
    done
    printf '%s\t\t\n' "none"
    return 0
}

# session_focused_project: reads brain/state/sessions/<sid>.json (written by
# `matrix focus`) and prints the focused project name IFF: the file exists,
# its session_id matches the current session's sid, and the project it names
# still exists in .registry.json (read-time check — covers mid-session
# de-registration, not just write-time). Any other case (no file, stale
# session_id, de-registered project, unreadable/corrupt JSON) prints nothing.
# Never propagates an error — same "always usable inside `&&` chains" contract
# as resolve_scope_project, which is this function's only caller.
session_focused_project() {
    local sid; sid="$(current_session_id 2>/dev/null || true)"
    [[ -n "$sid" ]] || return 0
    local focus_file="$STATE_DIR/sessions/$sid.json"
    [[ -f "$focus_file" ]] || return 0
    local file_sid focused
    file_sid="$(jq -r '.session_id // empty' "$focus_file" 2>/dev/null || true)"
    [[ -n "$file_sid" && "$file_sid" == "$sid" ]] || return 0
    focused="$(jq -r '.focused_project // empty' "$focus_file" 2>/dev/null || true)"
    [[ -n "$focused" ]] || return 0
    local existing; existing="$(registry_path "$focused" 2>/dev/null || true)"
    [[ -n "$existing" && "$existing" != "null" ]] || return 0
    printf '%s\n' "$focused"
    return 0
}

# scope_subject_from_name <name>: prints <name> iff it is still registered.
# Defends the env/focus subject resolution from ghost names — the same
# read-time check session_focused_project() does for its own value.
scope_subject_from_name() {
    local name="$1"
    [[ -n "$name" ]] || return 0
    local p; p="$(registry_path "$name" 2>/dev/null || true)"
    [[ -n "$p" && "$p" != "null" ]] || return 0
    printf '%s\n' "$name"
    return 0
}

# resolve_scope_project: the *filter subject* for checkpoints/ledger views.
# Priority: $MATRIX_PROJECT (env, explicit) > session focus > registry walk-up
# (chain[0], innermost). Workspace resolves to the reserved "matrix" name.
# Always returns 0 (callers use it inside `&&` lists under `set -e`).
resolve_scope_project() {
    local subject=""
    local envp; envp="$(scope_subject_from_name "${MATRIX_PROJECT:-}" 2>/dev/null || true)"
    [[ -n "$envp" ]] && subject="$envp"
    if [[ -z "$subject" ]]; then
        local focused; focused="$(session_focused_project 2>/dev/null || true)"
        [[ -n "$focused" ]] && subject="$focused"
    fi
    if [[ -z "$subject" ]]; then
        local line mode project
        IFS=$'\n' read -r line < <(resolve_scope)
        mode="$(printf '%s\n' "$line" | cut -f1)"
        project="$(printf '%s\n' "$line" | cut -f2)"
        case "$mode" in
            workspace) printf '%s\n' "$MATRIX_WORKSPACE_PROJECT" ;;
            project)   printf '%s\n' "$project" ;;
            *)         ;;
        esac
        return 0
    fi
    printf '%s\n' "$subject"
    return 0
}

# registry_name_for_path: the registry lookup that show_status and
# resolve_scope_project each open-coded before. TAB-delimited so remote URLs
# containing ':' remain intact.
registry_name_for_path() {
    local target; target="$(readlink -f "$1" 2>/dev/null || true)"
    [[ -n "$target" ]] || return 1
    init_registry
    local n p
    while IFS=$'\t' read -r n p; do
        [[ -n "$n" ]] || continue
        [[ "$(readlink -f "$(to_abs_path "$p")" 2>/dev/null || true)" == "$target" ]] && { printf '%s\n' "$n"; return 0; }
    done < <(jq -r '.projects[] | select(.type=="local") | "\(.name)\t\(.path)"' "$REGISTRY_FILE" 2>/dev/null)
    while IFS=$'\t' read -r n; do
        [[ -n "$n" ]] || continue
        [[ "$(readlink -f "$CLIENTS_DIR/$n" 2>/dev/null || true)" == "$target" ]] && { printf '%s\n' "$n"; return 0; }
    done < <(jq -r '.projects[] | select(.type=="remote") | .name' "$REGISTRY_FILE" 2>/dev/null)
    return 1
}

# registry_names_for_path <path>: print every registered project whose
# canonical path is an ancestor of <path> (or equal), innermost first.
# The Matrix root is excluded (it is context, not a node). Returns 0 always.
registry_names_for_path() {
    local target; target="$(readlink -f "$1" 2>/dev/null || true)"
    [[ -n "$target" ]] || return 0
    init_registry
    local matrix_real; matrix_real="$(readlink -f "$MATRIX_DIR" 2>/dev/null || echo "$MATRIX_DIR")"
    local dir n
    dir="$target"
    while :; do
        [[ "$dir" == "$matrix_real" ]] && break
        n="$(registry_name_for_path "$dir" 2>/dev/null || true)"
        [[ -n "$n" ]] && printf '%s\n' "$n"
        [[ "$dir" == "/" ]] && break
        dir="$(dirname "$dir")"
    done
    return 0
}

# resolve_scope_chain: the memory tree for cwd. One registered project name
# per line, innermost first; workspace and none print nothing. Returns 0
# always (contract: usable inside `&&` lists under `set -e`).
resolve_scope_chain() {
    registry_names_for_path "$PWD"
}

# resolve_scope_chain_effective: the memory tree for this session, honoring
# $MATRIX_PROJECT > session focus > cwd walk-up. When the subject is a named
# project, the chain recomputes from that project's registered path (its
# ancestors); workspace/none fall back to the cwd walk (workspace → empty).
resolve_scope_chain_effective() {
    local subject; subject="$(resolve_scope_project)"
    if [[ -z "$subject" || "$subject" == "$MATRIX_WORKSPACE_PROJECT" ]]; then
        registry_names_for_path "$PWD"
        return 0
    fi
    local p; p="$(get_project_path "$subject" 2>/dev/null || true)"
    if [[ -n "$p" ]]; then
        registry_names_for_path "$p"
    else
        registry_names_for_path "$PWD"
    fi
    return 0
}

# scope_tree [--json]: print the session memory chain (one name per line) or,
# with --json, {"mode":..., "subject":..., "chain":[...]} for machines.
scope_tree() {
    local json=false arg
    for arg in "$@"; do
        case "$arg" in
            --json) json=true ;;
            --*) log_error "Unknown flag '$arg'"; return 1 ;;
            *) log_error "Unknown argument '$arg'"; return 1 ;;
        esac
    done
    local line mode subject
    IFS=$'\n' read -r line < <(resolve_scope)
    mode="$(printf '%s\n' "$line" | cut -f1)"
    subject="$(resolve_scope_project)"
    if $json; then
        local chain_json
        chain_json="$(resolve_scope_chain_effective | jq -R -s -c 'split("\n") | map(select(length > 0))' 2>/dev/null || echo '[]')"
        jq -n -c --arg mode "$mode" --arg subject "$subject" --argjson chain "$chain_json" \
            '{mode:$mode, subject:$subject, chain:$chain}'
        return 0
    fi
    resolve_scope_chain_effective
    return 0
}

# --- Project registry -------------------------------------------------------
add_project() {
    local name="" path_or_url="" replace=false arg
    for arg in "$@"; do
        case "$arg" in
            --replace|--force) replace=true ;;
            --*) log_error "Unknown flag '$arg'"; return 1 ;;
            *)
                if [[ -z "$name" ]]; then
                    name="$arg"
                elif [[ -z "$path_or_url" ]]; then
                    path_or_url="$arg"
                else
                    log_error "Unexpected argument '$arg'"
                    return 1
                fi
                ;;
        esac
    done
    [[ -z "$name" ]] && { log_error "Usage: matrix add <name> [path-or-url] [--replace]"; return 1; }
    is_workspace_target "$name" && { log_error "'$name' is a reserved name (the Matrix workspace itself) — choose another"; return 1; }
    if [[ -z "$path_or_url" ]]; then
        local current_dir; current_dir="$(pwd)"
        log_info "No path provided. Current directory: $current_dir"
        echo -n "Use this path? [y/N]: "; read -r r
        [[ "$r" =~ ^[Yy]$ ]] || { log_warning "Cancelled"; return 1; }
        path_or_url="$current_dir"
    fi
    local type="local"
    [[ "$path_or_url" =~ ^https?:// || "$path_or_url" =~ ^git@ ]] && type="remote"
    if [[ "$type" == "local" ]]; then
        path_or_url="$(to_abs_path "$path_or_url")"
        path_or_url="${path_or_url%/}"
        [[ -d "$path_or_url" ]] || { log_error "Path '$path_or_url' does not exist"; return 1; }
    fi
    local existing; existing="$(registry_path "$name")"
    if [[ -n "$existing" && "$existing" != "null" ]]; then
        if [[ "$replace" != true ]]; then
            log_error "Project '$name' already exists — use 'matrix add <name> <path> --replace' to update it"
            return 1
        fi
        if has_legacy_binding_artifacts "$name" >/dev/null 2>&1; then
            log_warning "Project '$name' has legacy binding artifacts (_brain/AGENTS.local.md/exclude) — run 'matrix migrate-nobind $name' to clean them"
        fi
        local tmp; tmp="$(mktemp)"
        jq --arg n "$name" --arg p "$path_or_url" --arg t "$type" \
           '.projects |= map(if .name==$n then . + {path:$p, type:$t} else . end)' \
           "$REGISTRY_FILE" > "$tmp" && mv "$tmp" "$REGISTRY_FILE"
        link_append "project:replace" "$name" "$existing -> $path_or_url"
        log_success "Replaced project '$name'"
        return 0
    fi
    local tmp; tmp="$(mktemp)"
    jq --arg n "$name" --arg p "$path_or_url" --arg t "$type" \
       '.projects += [{"name": $n, "path": $p, "type": $t, "added": "'$(date -Iseconds)'"}]' \
       "$REGISTRY_FILE" > "$tmp" && mv "$tmp" "$REGISTRY_FILE"
    link_append "project:add" "$name" "$path_or_url"
    log_success "Added project '$name'"
}

remove_project() {
    local name="${1:-}"
    [[ $# -eq 1 && -n "$name" ]] || { log_error "Usage: matrix remove <name>"; return 1; }
    init_registry
    jq -e --arg n "$name" '.projects[] | select(.name==$n)' "$REGISTRY_FILE" >/dev/null 2>&1 \
        || { log_error "Project '$name' not found"; return 1; }
    if grep -qxF "  - name: $name" "$WORKSPACE_FILE" 2>/dev/null; then
        log_error "Project '$name' is warm — run 'matrix unwork $name' before removing it"
        return 1
    fi
    local tmp; tmp="$(mktemp)"
    jq --arg n "$name" '.projects |= map(select(.name != $n))' "$REGISTRY_FILE" > "$tmp" && mv "$tmp" "$REGISTRY_FILE"
    link_append "registry:remove" "$name" ""
    log_success "Removed project '$name'"
}

focus_project() {
    local name="${1:-}"
    [[ $# -eq 1 && -n "$name" ]] || { log_error "Usage: matrix focus <name>"; return 1; }
    local existing; existing="$(registry_path "$name")"
    [[ -n "$existing" && "$existing" != "null" ]] || { log_error "Project '$name' not found — register it first with 'matrix add'"; return 1; }
    local sid; sid="$(current_session_id || true)"
    [[ -n "$sid" ]] || { log_error "No active session marker — can't set a session focus without a session to attach it to"; return 1; }
    init_state
    local focus_file="$STATE_DIR/sessions/$sid.json"
    jq -n -c --arg sid "$sid" --arg proj "$name" --arg ts "$(date -Iseconds)" \
        '{session_id:$sid, focused_project:$proj, set_at:$ts}' > "$focus_file"
    link_append "focus" "$name" "session=$sid"
    log_success "Session focus set to '$name'"
}

list_projects() {
    log_info "Known projects:"; echo
    init_registry
    local projects; projects="$(jq -r '.projects[] | "\(.name)\t\(.path)\t\(.type)"' "$REGISTRY_FILE" 2>/dev/null)"
    [[ -z "$projects" ]] && { echo "  No projects registered"; return; }
    while IFS=$'\t' read -r name path type; do
        local marks=""
        is_project_warm "$name" && marks+="[warm]"
        if [[ -n "$marks" ]]; then
            echo "  ✓ $name ($type) - $path $marks"
        else
            echo "    $name ($type) - $path"
        fi
    done <<< "$projects"
}

registry_path() {
    local name="$1"
    init_registry
    jq -r --arg n "$name" '.projects[] | select(.name==$n) | .path' "$REGISTRY_FILE" 2>/dev/null
}

registry_type() {
    local name="$1"
    init_registry
    jq -r --arg n "$name" '.projects[] | select(.name==$n) | .type' "$REGISTRY_FILE" 2>/dev/null
}

get_project_path() {
    local name="$1"
    local p t
    p="$(registry_path "$name")"
    t="$(registry_type "$name")"
    [[ -z "$p" || "$p" == "null" ]] && return 1
    if [[ "$t" == "remote" ]]; then
        echo "$CLIENTS_DIR/$name"
    else
        p="$(to_abs_path "$p")"
        echo "${p%/}"
    fi
}

resolve_project_path() {
    local name="$1"
    get_project_path "$name"
}

registry_bound_target() {
    local name="$1"
    init_registry
    jq -r --arg n "$name" '.projects[] | select(.name==$n) | (.bound_target // "devin")' "$REGISTRY_FILE" 2>/dev/null
}

set_registry_bound_target() {
    local name="$1" target="$2" tmp
    tmp="$(mktemp)"
    jq --arg n "$name" --arg target "$target" \
       '.projects |= map(if .name==$n then . + {bound_target:$target} else . end)' \
       "$REGISTRY_FILE" > "$tmp" && mv "$tmp" "$REGISTRY_FILE"
}

