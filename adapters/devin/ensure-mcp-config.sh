#!/bin/bash
# Matrix — Devin MCP config scaffold + merge idempotente.
#
# Gestiona ~/.config/devin/mcp_config.json para que una instalación de cero
# quede con los dos MCPs que el brain asume (chrome-browser, context7), sin
# pisar servers ajenos que el usuario pudiera tener.
#
# Comportamiento:
#   - Si el archivo no existe (o está vacío), lo crea con ambos servers.
#   - Si existe y parsea como JSON, hace merge idempotente: agrega solo los
#     servers requeridos que falten, sin tocar el resto.
#   - Si existe pero está corrupto, hace backup con timestamp, crea uno limpio
#     y lo reporta.
#   - NUNCA lee ni imprime secretos: el archivo es de configuración estructural.
#
# TODO (R3, plan instalación/portabilidad): esto NO toca permissions.allow de
# ~/.config/devin/config.json. Evidencia observada en esta máquina: context7
# figura en mcp_config.json sin ningún grant mcp__context7__* en
# config.json permissions.allow y funciona (lo usa Oracle vía allowed-tools
# del AGENT.md generado). Los grants mcp__chrome-browser__* que existen en
# config.json permissions.allow son legacy/manuales y no se requieren para los
# MCPs presentes. Smith debe cerrar en el gate real: MCP *utilizable*, no solo
# presente.
set -uo pipefail

DEVIN_HOME="${XDG_CONFIG_HOME:-$HOME/.config}/devin"
MCP_FILE="$DEVIN_HOME/mcp_config.json"
mkdir -p "$DEVIN_HOME"

python3 - "$MCP_FILE" <<'PY'
import json
import os
import sys
import time

path = sys.argv[1]

REQUIRED = {
    "chrome-browser": {
        "command": "npx",
        "args": ["-y", "chrome-devtools-mcp@1.9.0", "--isolated", "--no-usage-statistics"],
    },
    "context7": {
        "url": "https://mcp.context7.com/mcp",
        "transport": "http",
    },
}


def load():
    if not os.path.isfile(path):
        return None, "missing"
    with open(path, encoding="utf-8") as fh:
        text = fh.read().strip()
    if not text:
        return None, "missing"
    try:
        return json.loads(text), "ok"
    except ValueError as exc:
        return None, f"corrupt: {exc}"


cfg, state = load()

if state == "missing":
    print(f"[ensure-mcp-config] {path} no existía; creando archivo nuevo")
    cfg = {"mcpServers": {}}
elif state != "ok":
    backup = f"{path}.bak-{time.strftime('%Y%m%d-%H%M%S')}"
    with open(backup, "w", encoding="utf-8") as fh:
        fh.write(open(path, encoding="utf-8").read())
    print(f"[ensure-mcp-config] {path} corrupto ({state}); backup en {backup}; creando archivo limpio")
    cfg = {"mcpServers": {}}
else:
    if not isinstance(cfg, dict):
        backup = f"{path}.bak-{time.strftime('%Y%m%d-%H%M%S')}"
        with open(backup, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(cfg, ensure_ascii=False))
        print(f"[ensure-mcp-config] {path} no es un objeto JSON ({type(cfg).__name__}); backup en {backup}; creando archivo limpio")
        cfg = {"mcpServers": {}}
    elif not isinstance(cfg.get("mcpServers"), dict):
        print(f"[ensure-mcp-config] {path} no tiene mcpServers; creando la sección")
        cfg["mcpServers"] = {}

added = []
servers = cfg["mcpServers"]
for name, spec in REQUIRED.items():
    if name not in servers:
        servers[name] = spec
        added.append(name)

with open(path, "w", encoding="utf-8") as fh:
    json.dump(cfg, fh, ensure_ascii=False, indent=2)
    fh.write("\n")

if added:
    print(f"[ensure-mcp-config] agregados servers: {', '.join(added)}")
else:
    print(f"[ensure-mcp-config] OK: {path} ya tenía todos los servers requeridos")
PY
