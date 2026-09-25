#!/bin/bash
# Matrix — detector de prerrequisitos del sistema.
#
# Corre ANTES de que bin/matrix, jq o python3 existan: solo usa `command -v` y
# builtins de bash para decir exactamente qué falta en una máquina nueva, y
# sugerir el comando de instalación. Este script NUNCA instala ni toca nada:
# solo informa.
#
# Uso:  bin/check-prereqs.sh
# Exit: 0 = todo lo esencial presente
#       1 = falta algo esencial (bloquea el flujo completo)
#       2 = solo faltan opcionales (Matrix arranca, pero degrada)
set -u

# --- Repo root sin depender de realpath/readlink (este script debe poder
# correr antes de que esas herramientas existan). --------------------------
resolve_root() {
    local dir
    dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." 2>/dev/null && pwd)"
    while [[ "$dir" != "/" ]]; do
        if [[ -d "$dir/brain" && -f "$dir/AGENTS.md" ]]; then
            printf '%s\n' "$dir"
            return 0
        fi
        dir="$(dirname "$dir")"
    done
    printf '%s\n' "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." 2>/dev/null && pwd)"
}
ROOT="$(resolve_root)"

say()  { printf '%s\n' "$*"; }
ok()   { printf '  [OK]    %-16s %s\n' "$1" "${2:-}"; }
miss() { printf '  [FALTA] %-16s %s\n' "$1" "${2:-}"; }
warn() { printf '  [AVISO] %s\n' "$1"; }

ess_missing=0
opt_missing=0

say ""
say "== Prerrequisitos de Matrix =="
say ""

# --- Esenciales (bloquean) ---------------------------------------------------
say "Esenciales (bloquean el flujo completo):"

# bash >= 4
if [[ "${BASH_VERSINFO[0]:-0}" -ge 4 ]]; then
    ok "bash ${BASH_VERSION%% *}" "esencial"
else
    miss "bash >= 4 (tenés ${BASH_VERSION:-?})" "esencial — actualizá bash"
    ess_missing=$((ess_missing + 1))
fi

# python3
if command -v python3 >/dev/null 2>&1; then
    ok "python3" "esencial"
else
    miss "python3" "esencial — apt-get install -y python3 (macOS: brew install python3)"
    ess_missing=$((ess_missing + 1))
fi

# jq
if command -v jq >/dev/null 2>&1; then
    ok "jq" "esencial"
else
    miss "jq" "esencial — apt-get install -y jq (macOS: brew install jq)"
    ess_missing=$((ess_missing + 1))
fi

# git
if command -v git >/dev/null 2>&1; then
    ok "git" "esencial"
else
    miss "git" "esencial — apt-get install -y git (macOS: brew install git)"
    ess_missing=$((ess_missing + 1))
fi

# realpath OR readlink -f
if command -v realpath >/dev/null 2>&1; then
    ok "realpath" "esencial"
elif command -v readlink >/dev/null 2>&1 && readlink -f . >/dev/null 2>&1; then
    ok "readlink -f" "esencial"
else
    miss "realpath o readlink -f" "esencial — Linux: apt-get install -y coreutils; macOS: brew install coreutils"
    ess_missing=$((ess_missing + 1))
fi

# PyYAML (módulo python yaml)
if command -v python3 >/dev/null 2>&1 && python3 -c 'import yaml' >/dev/null 2>&1; then
    ok "yaml (PyYAML)" "esencial"
else
    miss "yaml (PyYAML)" "esencial — pip install --user pyyaml (o apt-get install -y python3-yaml)"
    ess_missing=$((ess_missing + 1))
fi

# --- Opcionales (degradan con aviso) -----------------------------------------
say ""
say "Opcionales (Matrix arranca igual; la capacidad correspondiente no va a andar):"

# flock
if command -v flock >/dev/null 2>&1; then
    ok "flock" "opcional — lock global"
else
    miss "flock" "opcional — lock global (apt-get install -y util-linux); Matrix corre sin lock global"
    opt_missing=$((opt_missing + 1))
fi

# setsid
if command -v setsid >/dev/null 2>&1; then
    ok "setsid" "opcional — Hardline"
else
    miss "setsid" "opcional — Hardline (apt-get install -y util-linux)"
    opt_missing=$((opt_missing + 1))
fi

# nohup
if command -v nohup >/dev/null 2>&1; then
    ok "nohup" "opcional — Hardline"
else
    miss "nohup" "opcional — Hardline (coreutils)"
    opt_missing=$((opt_missing + 1))
fi

# pgrep
if command -v pgrep >/dev/null 2>&1; then
    ok "pgrep" "opcional — Hardline"
else
    miss "pgrep" "opcional — Hardline (apt-get install -y procps)"
    opt_missing=$((opt_missing + 1))
fi

# /proc
if [[ -d /proc ]]; then
    ok "/proc" "opcional — Hardline"
else
    miss "/proc" "opcional — Hardline (ausente en macOS; Hardline degrada)"
    opt_missing=$((opt_missing + 1))
fi

# npx
if command -v npx >/dev/null 2>&1; then
    ok "npx" "opcional — MCP chrome-browser"
else
    miss "npx" "opcional — MCP chrome-browser (apt-get install -y nodejs npm)"
    opt_missing=$((opt_missing + 1))
fi

# xdg-open
if command -v xdg-open >/dev/null 2>&1; then
    ok "xdg-open" "opcional — alias hardlines"
else
    miss "xdg-open" "opcional — alias hardlines (macOS: usar 'open'); el alias se puede adaptar"
    opt_missing=$((opt_missing + 1))
fi

# --- Seguridad: secrets file world-readable ----------------------------------
SECRETS_FILE="$ROOT/brain/state/hardline/telegram.env"
if [[ -f "$SECRETS_FILE" ]]; then
    MODE_LINE="$(ls -l "$SECRETS_FILE" 2>/dev/null || true)"
    # 9º carácter de `ls -l` = bit de lectura "otros" (world-readable).
    if [[ "${MODE_LINE:8:1}" == "r" ]]; then
        say ""
        warn "AVISO: $SECRETS_FILE es legible por otros (world-readable)."
        warn "  Recomendado: chmod 600 $SECRETS_FILE"
    fi
fi

# --- Sugerencias de instalación ----------------------------------------------
say ""
say "Sugerencias de instalación (ajustá a tu distro):"
say "  Debian/Ubuntu: apt-get install -y jq git python3 python3-yaml util-linux coreutils procps"
say "  Python:        pip install --user pyyaml"
say "  npx (opcional): apt-get install -y nodejs npm"
say "  macOS:         brew install coreutils jq python3 git"
say ""

# --- Verdict ---------------------------------------------------------------
if [[ "$ess_missing" -gt 0 ]]; then
    say "No puedo seguir: falta algo esencial. Instalá lo indicado y volvé a correr bin/check-prereqs.sh"
    exit 1
fi
if [[ "$opt_missing" -gt 0 ]]; then
    say "Matrix arranca, pero algunas capacidades opcionales no van a andar (ver [FALTA] opcional arriba)."
    exit 2
fi
say "Todo lo esencial está presente."
exit 0
