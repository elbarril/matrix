#!/usr/bin/env python3
"""Seraph · pre_activation_check — the guardian at the gate.

Validates prerequisites before any agent acts: contract present, config valid,
the roster intact, and the state directory ready. Halts (exit 1) with a clear
list of what is missing.

Usage:
  python3 hooks/pre_activation_check.py '{"project":"mck"}'
  bin/matrix hooks pre_activation_check
"""

import os

from _common import emit, gitignore_drift, read_input, resolve_root

try:
    from validate_ship import validate as validate_ship
except Exception:
    validate_ship = None

ROSTER = ["neo", "oracle", "morpheus", "architect", "trinity", "smith"]

# Infrastructure agents that deliberately live as installable subagent files in
# brain/agents/ but are NOT subject to roster discipline (AGENTS.md §3,
# "Supporting cast" — retire-one-to-add-one applies only to ROSTER above).
# docs/SYSTEM_TRUTH.md lists these alongside the roster with their own description.
# Add a name here ONLY if AGENTS.md §3 already documents it as supporting-cast
# infrastructure — never to silently permit an undocumented new file.
SUPPORTING_AGENTS = ["lock"]


def main():
    data = read_input()
    root = resolve_root()
    checks, errors = [], []

    def check(label, ok, detail=""):
        checks.append({"check": label, "ok": bool(ok), "detail": "" if ok else detail})
        if not ok:
            errors.append(label + (f": {detail}" if detail else ""))

    # Contract
    check("contract_present", os.path.isfile(os.path.join(root, "AGENTS.md")),
          "AGENTS.md missing at root")

    # Config (any of project _brain/config or brain/config)
    cfg = os.path.join(root, "brain", "config.yaml")
    check("config_present", os.path.isfile(cfg), f"missing {cfg}")
    if os.path.isfile(cfg):
        with open(cfg, encoding="utf-8") as fh:
            txt = fh.read()
        check("config_has_user", "user:" in txt, "config.yaml has no 'user:'")
        check("config_has_language", "language:" in txt, "config.yaml has no 'language:'")

    # Roster intact
    agents_dir = os.path.join(root, "brain", "agents")
    missing = [a for a in ROSTER if not os.path.isfile(os.path.join(agents_dir, a + ".md"))]
    unexpected = []
    if os.path.isdir(agents_dir):
        unexpected = sorted(
            f for f in os.listdir(agents_dir)
            if f.endswith(".md") and f[:-3] not in ROSTER + SUPPORTING_AGENTS
        )
    roster_detail_parts = []
    if missing:
        roster_detail_parts.append("missing agents: " + ", ".join(missing))
    if unexpected:
        roster_detail_parts.append("unexpected agent files: " + ", ".join(unexpected))
    check("roster_intact", not missing and not unexpected, "; ".join(roster_detail_parts))

    # State directory
    state = os.path.join(root, "brain", "state")
    check("state_dir", os.path.isdir(state), f"missing {state}")

    # Ship validation (delegated, generic)
    if data.get("ship") and validate_ship:
        v = validate_ship(data)
        checks.extend(v.get("checks", []))
        if not v.get("ok"):
            errors.extend(v.get("errors", []))

    # Gitignore drift — informational only, warn-only. The result lives in its own
    # field and never feeds into the global `ok` of the hook.
    drift = None
    if data.get("project"):
        drift = gitignore_drift(data["project"], root=root)

    result = {
        "hook": "pre_activation_check",
        "ok": not errors,
        "project": data.get("project"),
        "ship": data.get("ship"),
        "root": root,
        "checks": checks,
        "errors": errors,
        "gitignore_drift": drift,
    }
    emit(result)


if __name__ == "__main__":
    main()
