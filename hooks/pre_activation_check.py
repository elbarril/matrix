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

from _common import emit, read_input, resolve_root

ROSTER = ["neo", "oracle", "morpheus", "architect", "trinity", "smith", "keymaker"]


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
    check("roster_intact", not missing, "missing agents: " + ", ".join(missing) if missing else "")

    # State directory
    state = os.path.join(root, "brain", "state")
    check("state_dir", os.path.isdir(state), f"missing {state}")

    result = {
        "hook": "pre_activation_check",
        "ok": not errors,
        "project": data.get("project"),
        "root": root,
        "checks": checks,
        "errors": errors,
    }
    emit(result)


if __name__ == "__main__":
    main()
