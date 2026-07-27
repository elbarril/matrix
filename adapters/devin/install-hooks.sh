#!/usr/bin/env bash
# Matrix Devin hook installer — Layer 3 wiring for ~/.config/devin/config.json
set -euo pipefail

CONFIG_FILE="${HOME}/.config/devin/config.json"
BACKUP_FILE="${CONFIG_FILE}.bak-$(date +%Y%m%d-%H%M%S)"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MATRIX_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
HOOK_SCRIPT="${MATRIX_ROOT}/adapters/devin/hooks/session_audit.py"

mkdir -p "$(dirname "$CONFIG_FILE")"

if [[ -f "$CONFIG_FILE" ]]; then
    cp "$CONFIG_FILE" "$BACKUP_FILE"
    echo "Backup created: $BACKUP_FILE"
else
    echo "No existing config at $CONFIG_FILE; a fresh one will be created."
fi

python3 - "$CONFIG_FILE" "$HOOK_SCRIPT" "$MATRIX_ROOT" <<'PY'
import json
import os
import sys

config_path = sys.argv[1]
hook_script = sys.argv[2]
matrix_root = sys.argv[3]

if os.path.isfile(config_path):
    with open(config_path, encoding="utf-8") as fh:
        text = fh.read().strip()
        cfg = json.loads(text) if text else {}
else:
    cfg = {}

command = f'env MATRIX_ROOT={matrix_root} python3 {hook_script}'

# Merge Matrix lifecycle hooks without touching unrelated config keys.
# PostToolUse omits matcher to audit every tool call (empty/omitted matcher
# matches all per Devin's hook schema).
hooks = cfg.setdefault("hooks", {})

for event in ("SessionStart", "UserPromptSubmit", "PostCompaction", "SessionEnd"):
    timeout = 30 if event == "SessionEnd" else 10
    hooks[event] = [
        {
            "hooks": [
                {
                    "type": "command",
                    "command": command,
                    "timeout": timeout,
                }
            ]
        }
    ]

hooks["PostToolUse"] = [
    {
        "hooks": [
            {
                "type": "command",
                "command": command,
                "timeout": 10,
            }
        ]
    }
]

with open(config_path, "w", encoding="utf-8") as fh:
    json.dump(cfg, fh, ensure_ascii=False, indent=2)
    fh.write("\n")

print(f"Updated: {config_path}")
PY

python3 -m json.tool "$CONFIG_FILE" > /dev/null
echo "JSON validation passed."
