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

say "done. Neo and specialists installed to $DEVIN_HOME"
