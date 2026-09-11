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
            local warm=false
            is_project_warm "$name" && warm=true
            lines="${lines}$(jq -n -c \
                --arg name "$name" --arg path "$real_path" --arg type "$type" --argjson warm "$warm" \
                '{name:$name,path:$path,type:$type,known:true,warm:$warm}')"$'\n'
        done <<< "$projects"
        printf '%s' "$lines" | jq -s '.'
        return
    fi
    log_info "Known / Warm projects:"; echo
    while IFS=$'\t' read -r name path type; do
        local real_path; real_path="$(get_project_path "$name" 2>/dev/null || true)"
        if is_project_warm "$name"; then
            echo "  ✓ $name -> $real_path [warm]"
        else
            echo "    $name -> $real_path"
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
        project)
            echo "Current directory: in project $project"
            ;;
        none|*)
            echo "Current directory: no project in scope (neutral)"
            ;;
    esac
    echo
    local known_count=0 warm_count=0 known_names="" warm_names=""
    while IFS=$'\t' read -r n _ _; do
        [[ -z "$n" ]] && continue
        known_count=$((known_count+1))
        known_names="$known_names$n "
        if is_project_warm "$n"; then
            warm_count=$((warm_count+1))
            warm_names="$warm_names$n "
        fi
    done <<< "$(read_registry)"
    known_names="${known_names% }"; warm_names="${warm_names% }"
    echo "Known: $known_count project(s)${known_names:+ ($known_names)}"
    echo "Warm: $warm_count project(s)${warm_names:+ ($warm_names)}"
    echo
    # Default view is scoped to the resolved project — or, with views.scoped
    # (default on), to the whole memory chain (subject + registered ancestors).
    # Global checkpoints/Link events are one project's needle in everyone
    # else's haystack. `matrix status --all` keeps the unfiltered view.
    local show_all="${1:-}" filter_projects="" scope_label=""
    if [[ "$show_all" != "--all" ]]; then
        if [[ "$(flag_value views.scoped)" == "true" ]]; then
            filter_projects="$(resolve_scope_chain_effective)"
            if [[ -z "$filter_projects" ]]; then
                local subject; subject="$(resolve_scope_project)"
                [[ -n "$subject" ]] && filter_projects="$subject"
            fi
        else
            filter_projects="$(resolve_scope_project)"
        fi
    fi
    if [[ "$mode" == "workspace" ]]; then
        scope_label="Matrix workspace mode"
    elif [[ -n "$filter_projects" ]]; then
        scope_label="chain: $(printf '%s' "$filter_projects" | tr '\n' ' ')"
    else
        scope_label="no subject (neutral)"
    fi
    if [[ -n "$filter_projects" ]]; then
        local chain_json; chain_json="$(printf '%s\n' "$filter_projects" | jq -R -s -c 'split("\n") | map(select(length > 0))' 2>/dev/null || echo '[]')"
        if [[ -s "$CHECKPOINTS_FILE" ]]; then
            echo "Recent checkpoints ($scope_label):"
            jq -c --argjson ps "$chain_json" 'select(.project as $p | $ps | index($p))' "$CHECKPOINTS_FILE" 2>/dev/null \
                | tail -n 5 | jq -r '"  " + .timestamp + " — " + .note' 2>/dev/null || true
        fi
        echo
        if [[ -s "$ACTIVITY_LOG" ]]; then
            echo "Recent Link events ($scope_label):"
            awk -F' *\\| *' -v chain="$filter_projects" '
                BEGIN { nn=split(chain, arr, "\n"); for (i=1;i<=nn;i++) set[arr[i]]=1 }
                { if ($3 in set) print }
            ' "$ACTIVITY_LOG" | tail -n 5 | sed 's/^/  /'
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
# Default scope mirrors show_status: filters to the resolved project — or, with
# views.scoped (default on), to the whole memory chain. --all forces the old
# unfiltered, all-projects tail; --project=<name> filters to an explicit
# project regardless of cwd.
show_activity() {
    init_state
    local n=20 show_all=false explicit_proj="" mode=""
    for arg in "$@"; do
        case "$arg" in
            --all) show_all=true ;;
            --project=*) explicit_proj="${arg#*=}" ;;
            *[0-9]*) [[ "$arg" =~ ^[0-9]+$ ]] && n="$arg" ;;
        esac
    done
    local filter="" label=""
    if [[ -n "$explicit_proj" ]]; then
        filter="$explicit_proj"
        label="project: $explicit_proj"
    elif [[ "$show_all" == true ]]; then
        label="all projects"
    else
        if [[ "$(flag_value views.scoped)" == "true" ]]; then
            filter="$(resolve_scope_chain_effective)"
            if [[ -z "$filter" ]]; then
                local subject; subject="$(resolve_scope_project)"
                [[ -n "$subject" ]] && filter="$subject"
            fi
            if [[ -n "$filter" ]]; then
                label="chain: $(printf '%s' "$filter" | tr '\n' ' ')"
            else
                label="no subject (neutral)"
            fi
        else
            IFS=$'\n' read -r line < <(resolve_scope)
            mode="$(printf '%s\n' "$line" | cut -f1)"
            local raw_proj; raw_proj="$(printf '%s\n' "$line" | cut -f2)"
            [[ "$raw_proj" == "null" ]] && raw_proj=""
            filter="$raw_proj"
            if [[ "$mode" == "workspace" ]]; then
                filter="$(resolve_scope_project)"
                label="Matrix workspace mode"
            else
                label="project: $raw_proj"
            fi
        fi
    fi
    if [[ -n "$filter" && "$show_all" != true ]]; then
        log_info "Link ledger (last $n, $label):"; echo
        awk -F' *\\| *' -v chain="$filter" '
            BEGIN { nn=split(chain, arr, "\n"); for (i=1;i<=nn;i++) set[arr[i]]=1 }
            { if ($3 in set) print }
        ' "$ACTIVITY_LOG" | tail -n "$n" | sed 's/^/  /'
    else
        log_info "Link ledger (last $n, all projects):"; echo
        tail -n "$n" "$ACTIVITY_LOG" | sed 's/^/  /'
    fi
}

# --- Seraph hooks -----------------------------------------------------------
