# Matrix CLI — warm module (sourced by bin/matrix)

warm_project_entry() {
    local name="$1" path="$2" quiet="${3:-}"
    init_state
    if grep -qxF "  - name: $name" "$WORKSPACE_FILE" 2>/dev/null; then
        [[ "$quiet" == "quiet" ]] || log_warning "'$name' already warm"
        return 0
    fi
    # Insert before the last_updated line.
    local ts; ts="$(date -Iseconds)"
    local tmp; tmp="$(mktemp)"
    awk -v n="$name" -v p="$path" -v ts="$ts" '
        /^active_projects:/ && $0 ~ /\[\]/ { print "active_projects:"; print "  - name: " n; print "    path: " p; print "    activated: " ts; next }
        /^last_updated:/ { print "last_updated: \"" ts "\""; next }
        { print }
    ' "$WORKSPACE_FILE" > "$tmp"
    # If the set was non-empty, the awk above only handles the empty case; handle non-empty by append.
    if grep -qxF "  - name: $name" "$tmp"; then mv "$tmp" "$WORKSPACE_FILE"; else
        rm -f "$tmp"
        # Append under active_projects: (non-empty list)
        sed -i "/^active_projects:/a\\  - name: $name\\n    path: $path\\n    activated: $ts" "$WORKSPACE_FILE"
        sed -i "s|^last_updated:.*|last_updated: \"$ts\"|" "$WORKSPACE_FILE"
    fi
    link_append "project:work" "$name" "$path"
    [[ "$quiet" == "quiet" ]] || log_success "Warmed '$name' into the active set"
}

work_project() {
    local name="$1"
    [[ -z "$name" ]] && { log_error "Usage: matrix work <name>"; return 1; }
    local path; path="$(resolve_project_path "$name")" || { log_error "Project '$name' not found"; return 1; }
    warm_project_entry "$name" "$path"
    local target; target="$(registry_bound_target "$name")"
    [[ -n "$target" && "$target" != "null" ]] || target="devin"
    update_exclude "$path" "$target" 2>/dev/null || true
}

is_project_warm() {
    grep -qxF "  - name: $1" "$WORKSPACE_FILE" 2>/dev/null
}

remove_warm_entry() {
    local name="$1" tmp; tmp="$(mktemp)"
    NAME="$name" awk '
        BEGIN { line = "  - name: " ENVIRON["NAME"] }
        $0 == line { skip=2; next }
        skip > 0 { skip--; next }
        { print }
    ' "$WORKSPACE_FILE" > "$tmp" && mv "$tmp" "$WORKSPACE_FILE"
    grep -q "^  - name:" "$WORKSPACE_FILE" || sed -i "s|^active_projects:.*|active_projects: []|" "$WORKSPACE_FILE"
    sed -i "s|^last_updated:.*|last_updated: \"$(date -Iseconds)\"|" "$WORKSPACE_FILE"
}

unwork_project() {
    local name="$1"
    [[ -z "$name" ]] && { log_error "Usage: matrix unwork <name>"; return 1; }
    init_state
    is_bound "$name" && deselect_project "$name"
    if ! is_project_warm "$name"; then
        log_warning "'$name' is not in the active set"
        return 0
    fi
    remove_warm_entry "$name"
    link_append "project:unwork" "$name" ""
    log_success "Removed '$name' from the active set"
}

unwork_all_projects() {
    local dry_run=false arg
    for arg in "$@"; do
        case "$arg" in
            --dry-run) dry_run=true ;;
            --all) : ;;  # ya consumido por el dispatcher, tolerado si se re-pasa
            *) log_error "Usage: matrix unwork --all [--dry-run]"; return 1 ;;
        esac
    done
    init_state
    local deselected=0 unworked=0 untouched=0
    local projects; projects="$(read_registry)"
    while IFS=$'\t' read -r name path type; do
        [[ -z "$name" ]] && continue
        local bound=false warm=false
        is_bound "$name" && bound=true
        is_project_warm "$name" && warm=true
        if ! $bound && ! $warm; then untouched=$((untouched+1)); continue; fi
        if $dry_run; then
            $bound && { echo "  deselect: $name"; deselected=$((deselected+1)); }
            $warm  && { echo "  unwork:   $name"; unworked=$((unworked+1)); }
            continue
        fi
        if $bound; then deselect_project "$name" || true; deselected=$((deselected+1)); fi
        if $warm; then
            remove_warm_entry "$name"
            link_append "project:unwork" "$name" ""
            unworked=$((unworked+1))
        fi
    done <<< "$projects"
    if ! $dry_run; then
        link_append "projects:unwork-all" "-" "deselected=$deselected unworked=$unworked"
    fi
    echo
    log_info "Deselected: $deselected | Unworked: $unworked | Untouched: $untouched"
}

unwork_dispatch() {
    local all=false name="" arg
    for arg in "$@"; do
        case "$arg" in
            --all) all=true ;;
            --dry-run) : ;;  # solo válido junto a --all, se re-chequea abajo
            --target=*) log_error "unwork --all does not accept --target (each project resolves its own bound target)"; return 1 ;;
            --*) log_error "Unknown flag '$arg'"; return 1 ;;
            *) if [[ -z "$name" ]]; then name="$arg"; else log_error "Unexpected argument '$arg'"; return 1; fi ;;
        esac
    done
    if $all; then
        [[ -n "$name" ]] && { log_error "unwork --all does not take a project name"; return 1; }
        unwork_all_projects "$@"
        return $?
    fi
    for arg in "$@"; do [[ "$arg" == "--dry-run" ]] && { log_error "--dry-run only applies to --all"; return 1; }; done
    unwork_project "$name"
}

show_workspace() {
    init_state
    log_info "Warm project set:"; echo
    local names; names="$(grep "^  - name:" "$WORKSPACE_FILE" 2>/dev/null | sed 's/  - name: //' || true)"
    if [[ -z "$names" ]]; then
        echo "   (empty) — use 'matrix work <name>'"
        return
    fi
    while IFS= read -r n; do
        [[ -z "$n" ]] && continue
        local mark=""
        is_bound "$n" && mark=" [bound]"
        echo "   • $n$mark"
    done <<< "$names"
}

# --- Status -----------------------------------------------------------------
