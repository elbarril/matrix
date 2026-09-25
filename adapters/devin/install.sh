#!/bin/bash
# Trainman · Devin installer.
#
# Deploys the generated thin-pointer artifacts into Devin's GLOBAL discovery
# path so the Matrix master (Neo) and its specialists are invocable from ANY
# project — inside Matrix, inside clients/, or in an unrelated repo.
#
# Self-contained by design: artifacts are COPIED (not symlinked) into the
# global path. The copied pointer references the brain by absolute path, so it
# keeps working even if adapters/<target>/generated/ (gitignored, ephemeral) is
# wiped. Run `bin/matrix build --target=devin` first, then this installer.
#
# Discovery paths (per Devin docs):
#   ~/.config/devin/skills/<name>/SKILL.md   (global skills)
#   ~/.config/devin/agents/<name>/AGENT.md   (global subagent profiles)
set -euo pipefail

ROOT="${MATRIX_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
GEN="$ROOT/adapters/devin/generated/.agents"
DEVIN_HOME="${XDG_CONFIG_HOME:-$HOME/.config}/devin"
SKILLS_DIR="$DEVIN_HOME/skills"
AGENTS_DIR="$DEVIN_HOME/agents"

say() { echo "[trainman:install] $*"; }

[[ -d "$GEN" ]] || { echo "[trainman:install] no build output at $GEN — run 'bin/matrix build --target=devin' first." >&2; exit 1; }

# Replace a path that is currently a (possibly broken) symlink with a real dir.
ensure_real_dir() {
    local d="$1"
    if [[ -L "$d" ]]; then
        say "replacing legacy symlink '$d' with a real directory"
        rm -f "$d"
    fi
    mkdir -p "$d"
}

# Remove broken Matrix-owned symlinks left over from the old ad-hoc wiring.
# Only touches symlinks whose target is missing AND points into the Matrix root.
clean_broken_matrix_links() {
    local base="$1"
    [[ -d "$base" ]] || return 0
    local entry tgt
    for entry in "$base"/*; do
        [[ -L "$entry" ]] || continue
        if [[ ! -e "$entry" ]]; then
            tgt="$(readlink "$entry")"
            if [[ "$tgt" == "$ROOT/"* ]]; then
                say "removing broken Matrix symlink: $(basename "$entry") -> $tgt"
                rm -f "$entry"
            fi
        fi
    done
}

deploy() {
    local src_root="$1" dest_root="$2" leaf="$3"   # leaf: SKILL.md | AGENT.md
    [[ -d "$src_root" ]] || return 0
    ensure_real_dir "$dest_root"
    local d name
    for d in "$src_root"/*/; do
        [[ -d "$d" ]] || continue
        name="$(basename "$d")"
        local dest="$dest_root/$name"
        # If a stale symlink occupies the slot, drop it before writing a real file.
        [[ -L "$dest" ]] && rm -f "$dest"
        mkdir -p "$dest"
        cp -f "$d/$leaf" "$dest/$leaf"
        say "installed $name -> $dest/$leaf"
    done
}

mkdir -p "$SKILLS_DIR"
clean_broken_matrix_links "$SKILLS_DIR"
clean_broken_matrix_links "$AGENTS_DIR"

deploy "$GEN/skills" "$SKILLS_DIR" "SKILL.md"
deploy "$GEN/agents" "$AGENTS_DIR" "AGENT.md"

# Wire the Seraph audit + session-start-bootstrap lifecycle hooks into Devin's
# global config (~/.config/devin/config.json). Without this step, AGENTS.md
# §6 step 0 (Matrix workspace mode forces Neo activation) has no deterministic
# delivery path — it would fall back to the same skill-description matching
# the doctrine exists to not depend on. Idempotent: install-hooks.sh merges
# into hooks.* without touching unrelated config keys, and backs up the
# previous config.json before writing.
if [[ -x "$ROOT/adapters/devin/install-hooks.sh" ]]; then
    say "wiring Seraph lifecycle hooks into $DEVIN_HOME/config.json..."
    "$ROOT/adapters/devin/install-hooks.sh"
else
    say "WARNING: $ROOT/adapters/devin/install-hooks.sh not found or not executable; skipping hook wiring."
fi

# MCP config: create/merge ~/.config/devin/mcp_config.json (chrome-browser +
# context7), idempotente, con backup si el archivo existente está corrupto.
if [[ -x "$ROOT/adapters/devin/ensure-mcp-config.sh" ]]; then
    # Guard against a failing scaffold under `set -e`: MCPs are optional by
    # contract, so a scaffold error warns and continues instead of aborting
    # the install (same spirit as the integrity check capture below).
    if ! "$ROOT/adapters/devin/ensure-mcp-config.sh"; then
        say "WARNING: ensure-mcp-config.sh falló; los MCPs quedaron sin scaffold, el install continúa."
    fi
else
    say "WARNING: $ROOT/adapters/devin/ensure-mcp-config.sh not found or not executable; skipping MCP config scaffolding."
fi

# Install-integrity self-check (informational). The hook exits 1 on ok:false,
# so under `set -e` we must capture and continue: the install completes and
# reports what's missing instead of aborting.
integrity_summary="$(python3 "$ROOT/hooks/install_integrity_check.py" devin 2>&1 || true)"
# Extract the TOP-LEVEL .ok only (the JSON also carries per-sub-check "ok"
# fields; grepping any '"ok": true' would false-positive on ok:false).
integrity_ok="$(printf '%s' "$integrity_summary" | jq -r '.ok // false' 2>/dev/null || true)"
if [[ "$integrity_ok" == "true" ]]; then
    say "Integridad de instalación: OK"
else
    integrity_errors="$(printf '%s' "$integrity_summary" | jq -r '(.errors // []) | join("; ")' 2>/dev/null || true)"
    [[ -n "$integrity_errors" ]] || integrity_errors="revisá la salida de install_integrity_check"
    say "ATENCIÓN: faltan piezas esenciales de la instalación — $integrity_errors"
fi

say "done. Neo and specialists installed to $DEVIN_HOME"
