# Matrix CLI — status module (sourced by bin/matrix)

show_bindings() {
    local json=false warm_only=false arg
    for arg in "$@"; do
        case "$arg" in
            --json) json=true ;;
            --warm-only) warm_only=true ;;
            *) log_error "Unknown flag '$arg'"; return 1 ;;
        esac
    done
    if $warm_only; then
        show_workspace
        return
    fi
    local projects; projects="$(jq -r '.projects[] | "\(.name)\t\(.path)\t\(.type)"' "$REGISTRY_FILE" 2>/dev/null)"
    [[ -z "$projects" ]] && { if $json; then echo '[]'; else echo "  (none registered)"; fi; return; }
    if $json; then
        local lines=""
        while IFS=$'\t' read -r name path type; do
            local real_path; real_path="$(get_project_path "$name" 2>/dev/null || true)"
            [[ -z "$real_path" ]] && real_path="$path"
            local bound=false
            is_bound "$name" && bound=true
            lines="${lines}$(jq -n -c \
                --arg name "$name" --arg path "$real_path" --arg type "$type" --argjson bound "$bound" \
                '{name:$name,path:$path,type:$type,bound:$bound}')"$'\n'
        done <<< "$projects"
        printf '%s' "$lines" | jq -s '.'
        return
    fi
    log_info "Bound projects:"; echo
    while IFS=$'\t' read -r name path type; do
        local real_path; real_path="$(get_project_path "$name" 2>/dev/null || true)"
        if is_bound "$name"; then
            echo "  ✓ $name -> $real_path [bound]"
        else
            echo "  ✗ $name -> $real_path"
        fi
    done <<< "$projects"
}

show_status() {
    log_info "Matrix Status"; echo
    local line mode project detail
    IFS=$'\n' read -r line < <(resolve_scope)
    mode="$(printf '%s\n' "$line" | cut -f1)"
    project="$(printf '%s\n' "$line" | cut -f2)"
    detail="$(printf '%s\n' "$line" | cut -f3)"
    case "$mode" in
        workspace)
            echo "Current directory: Matrix workspace mode"
            ;;
        bound)
            echo "Current directory: bound to $project"
            ;;
        bound-unregistered)
            echo "Current directory: bound (project not in registry)"
            ;;
        broken)
            echo "Current directory: not bound (broken _brain link at $detail)"
            ;;
        none|*)
            echo "Current directory: not bound"
            ;;
    esac
    echo
    local bound_count=0 bound_names=""
    while IFS=$'\t' read -r n _ _; do
        [[ -z "$n" ]] && continue
        if is_bound "$n"; then
            bound_count=$((bound_count+1))
            bound_names="$bound_names$n "
        fi
    done <<< "$(read_registry)"
    bound_names="${bound_names% }"
    echo "Bound: $bound_count project(s)${bound_names:+ ($bound_names)}"
    local warm_n; warm_n="$(grep -c '^  - name:' "$WORKSPACE_FILE" 2>/dev/null)" || warm_n=0
    echo "Warm set: ${warm_n:-0} project(s)"
    local reg_n; reg_n="$(jq '.projects | length' "$REGISTRY_FILE" 2>/dev/null)" || reg_n=0
    echo "Registered: ${reg_n:-0} project(s)"
    echo
    # Default view is scoped to the resolved project (session focus > cwd
    # binding) — global checkpoints/Link events are one project's needle in
    # everyone else's haystack (see lessons.md: cross-project sessions were
    # pushing a project's own recent checkpoint out of an unfiltered last-3
    # window). `matrix status --all` keeps the old unfiltered, cross-project view.
    local show_all="${1:-}" scope_project="" scope_label=""
    [[ "$show_all" != "--all" ]] && scope_project="$(resolve_scope_project)"
    if [[ "$mode" == "workspace" ]]; then
        scope_label="Matrix workspace mode"
    else
        scope_label="project: $scope_project"
    fi
    if [[ -n "$scope_project" ]]; then
        if [[ -s "$CHECKPOINTS_FILE" ]]; then
            echo "Recent checkpoints ($scope_label):"
            jq -c --arg p "$scope_project" 'select(.project == $p)' "$CHECKPOINTS_FILE" 2>/dev/null \
                | tail -n 5 | jq -r '"  " + .timestamp + " — " + .note' 2>/dev/null || true
        fi
        echo
        if [[ -s "$ACTIVITY_LOG" ]]; then
            echo "Recent Link events ($scope_label):"
            awk -F' *\\| *' -v p="$scope_project" '{if ($3==p) print}' "$ACTIVITY_LOG" | tail -n 5 | sed 's/^/  /'
        fi
        echo
        echo "(run 'matrix status --all' for the unfiltered, cross-project view)"
    else
        if [[ -s "$CHECKPOINTS_FILE" ]]; then
            echo "Recent checkpoints (all projects):"
            tail -n 3 "$CHECKPOINTS_FILE" | jq -r '"  " + .timestamp + " — " + .note' 2>/dev/null || true
        fi
        echo
        if [[ -s "$ACTIVITY_LOG" ]]; then
            echo "Recent Link events (all projects):"
            tail -n 3 "$ACTIVITY_LOG" | sed 's/^/  /'
        fi
    fi
}

# --- Checkpoints ------------------------------------------------------------
write_checkpoint() {
    local note="$1"
    [[ -z "$note" ]] && { log_error "Usage: matrix checkpoint \"<note>\""; return 1; }
    init_state
    local ts; ts="$(date -Iseconds)"
    local active; active="$(resolve_scope_project)"; active="${active:-null}"
    jq -n -c --arg ts "$ts" --arg user "Emiliano" --arg proj "$active" --arg note "$note" \
        '{timestamp:$ts,user:$user,project:$proj,note:$note,context:{active_agents:[],current_focus:"",blockers:[],next_actions:[]}}' \
        >> "$CHECKPOINTS_FILE"
    link_append "checkpoint" "$active" "$note"
    log_success "Checkpoint written"
}

# show_activity [n] [--all] [--project=<name>]
# Default scope mirrors show_status: filters to the resolved project (session
# focus > cwd binding). --all forces the old unfiltered, all-projects tail;
# --project=<name> filters to an explicit project regardless of cwd (e.g. to
# check on a project you aren't currently bound to).
show_activity() {
    init_state
    local n=20 show_all=false proj="" mode=""
    for arg in "$@"; do
        case "$arg" in
            --all) show_all=true ;;
            --project=*) proj="${arg#*=}" ;;
            *[0-9]*) [[ "$arg" =~ ^[0-9]+$ ]] && n="$arg" ;;
        esac
    done
    if [[ -z "$proj" && "$show_all" != true ]]; then
        local line raw_proj
        IFS=$'\n' read -r line < <(resolve_scope)
        mode="$(printf '%s\n' "$line" | cut -f1)"
        raw_proj="$(printf '%s\n' "$line" | cut -f2)"
        proj="$raw_proj"
        [[ "$proj" == "null" ]] && proj=""
    fi
    if [[ -n "$proj" && "$show_all" != true ]]; then
        if [[ "$mode" == "workspace" ]]; then
            log_info "Link ledger (last $n, Matrix workspace mode):"; echo
        else
            log_info "Link ledger (last $n, project: $proj):"; echo
        fi
        awk -F' *\\| *' -v p="$proj" '{if ($3==p) print}' "$ACTIVITY_LOG" | tail -n "$n" | sed 's/^/  /'
    else
        log_info "Link ledger (last $n, all projects):"; echo
        tail -n "$n" "$ACTIVITY_LOG" | sed 's/^/  /'
    fi
}

# --- Seraph hooks -----------------------------------------------------------
