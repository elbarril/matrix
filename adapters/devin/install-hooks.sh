#!/usr/bin/env bash
# Matrix Devin hook installer — Layer 3 wiring for ~/.config/devin/config.json
set -euo pipefail

CONFIG_FILE="${HOME}/.config/devin/config.json"
BACKUP_FILE="${CONFIG_FILE}.bak-$(date +%Y%m%d-%H%M%S)"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MATRIX_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
HOOK_SCRIPT="${MATRIX_ROOT}/adapters/devin/hooks/session_audit.py"
ADAPTER_YAML="${MATRIX_ROOT}/adapters/devin/adapter.yaml"

mkdir -p "$(dirname "$CONFIG_FILE")"

if [[ -f "$CONFIG_FILE" ]]; then
    cp "$CONFIG_FILE" "$BACKUP_FILE"
    echo "Backup created: $BACKUP_FILE"
else
    echo "No existing config at $CONFIG_FILE; a fresh one will be created."
fi

python3 - "$CONFIG_FILE" "$HOOK_SCRIPT" "$MATRIX_ROOT" "$ADAPTER_YAML" <<'PY'
import json
import os
import sys

try:
    import yaml
except Exception as exc:  # pragma: no cover - PyYAML is a hard dependency for build
    print(f"[trainman:hooks] error: PyYAML is required: {exc}", file=sys.stderr)
    sys.exit(1)

config_path = sys.argv[1]
hook_script = sys.argv[2]
matrix_root = sys.argv[3]
adapter_yaml = sys.argv[4]

if os.path.isfile(config_path):
    with open(config_path, encoding="utf-8") as fh:
        text = fh.read().strip()
        cfg = json.loads(text) if text else {}
else:
    cfg = {}

command = f'env MATRIX_ROOT={matrix_root} python3 {hook_script}'
guard_script = f'{matrix_root}/adapters/devin/hooks/pre_tool_use_guard.py'
guard_command = f'env MATRIX_ROOT={matrix_root} python3 {guard_script}'

# Merge Matrix lifecycle hooks without touching unrelated config keys.
# PostToolUse omits matcher to audit every tool call (empty/omitted matcher
# matches all per Devin's hook schema).
hooks = cfg.setdefault("hooks", {})

for event in ("SessionStart", "UserPromptSubmit", "PostCompaction", "SessionEnd"):
    timeout = 30 if event == "SessionEnd" else 10
    hooks[event] = [
        {
            "hooks": [
                {"type": "command", "command": command, "timeout": timeout}
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

hooks["PreToolUse"] = [
    {
        "matcher": "exec",
        "hooks": [
            {
                "type": "command",
                "command": guard_command,
                "timeout": 10,
            }
        ]
    },
    {
        "matcher": "edit",
        "hooks": [
            {
                "type": "command",
                "command": guard_command,
                "timeout": 10,
            }
        ]
    },
    {
        "matcher": "write",
        "hooks": [
            {
                "type": "command",
                "command": guard_command,
                "timeout": 10,
            }
        ]
    },
    {
        "matcher": "multi_edit",
        "hooks": [
            {
                "type": "command",
                "command": guard_command,
                "timeout": 10,
            }
        ]
    },
    {
        "matcher": "run_subagent",
        "hooks": [
            {
                "type": "command",
                "command": command,
                "timeout": 10,
            }
        ]
    }
]

# Stop (Hardline stop_notify) is no longer wired by Matrix. Remove any stale
# entry left by an older install; the merge above is additive and would not
# clear a key it no longer manages. Reactivate: re-add the Stop block + script.
hooks.pop("Stop", None)

# Merge Matrix Exec allowlist from adapter.yaml into permissions.allow.
# Preserves pre-existing entries (Read(**), Write(**), MCP tools, etc.) and
# never duplicates entries across re-runs.
permissions = cfg.setdefault("permissions", {})
if not isinstance(permissions, dict):
    permissions = {}
    cfg["permissions"] = permissions
allow = permissions.setdefault("allow", [])
if not isinstance(allow, list):
    allow = []
    permissions["allow"] = allow

declared = []
try:
    with open(adapter_yaml, encoding="utf-8") as fh:
        adapter_cfg = yaml.safe_load(fh) or {}
    declared = adapter_cfg.get("permissions_allow", [])
    if not isinstance(declared, list):
        declared = []
except Exception as exc:
    print(f"[trainman:hooks] warning: could not read {adapter_yaml}: {exc}", file=sys.stderr)

added = []
for p in declared:
    if isinstance(p, str) and p not in allow:
        allow.append(p)
        added.append(p)

if added:
    print(f"[trainman:hooks] added to permissions.allow: {added}")

with open(config_path, "w", encoding="utf-8") as fh:
    json.dump(cfg, fh, ensure_ascii=False, indent=2)
    fh.write("\n")

print(f"Updated: {config_path}")
PY

python3 -m json.tool "$CONFIG_FILE" > /dev/null
echo "JSON validation passed."
