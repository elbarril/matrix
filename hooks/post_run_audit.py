#!/usr/bin/env python3
"""Seraph · post_run_audit — compliance and bypass detection.

After a run, verifies the enforced steps were executed, writes a validation
report, and flags non-compliant or bypassed activations.

Input JSON:
  {
    "agent": "neo",
    "steps": ["load_config","resolve_context","review_state",
              "pre_activation_check","route","validate_phase_close","checkpoint"]
  }

Writes brain/state/validation-report.json. Exit 0 if compliant, 1 if not.
"""

import datetime
import json
import os

from _common import emit, read_input, resolve_root

# The steps an enforced activation must contain.
REQUIRED_STEPS = [
    "load_config",
    "resolve_context",
    "pre_activation_check",
]


def main():
    data = read_input()
    root = resolve_root()
    steps = [str(s) for s in (data.get("steps") or [])]
    agent = data.get("agent")

    missing = [s for s in REQUIRED_STEPS if s not in steps]
    bypass = bool(steps) and missing  # ran something but skipped required steps
    compliant = not missing

    report = {
        "hook": "post_run_audit",
        "ok": compliant,
        "agent": agent,
        "timestamp": datetime.datetime.now().astimezone().isoformat(),
        "steps_seen": steps,
        "required": REQUIRED_STEPS,
        "missing": missing,
        "bypass_suspected": bool(bypass),
        "compliant": compliant,
    }

    state_dir = os.path.join(root, "brain", "state")
    os.makedirs(state_dir, exist_ok=True)
    with open(os.path.join(state_dir, "validation-report.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)

    emit(report)


if __name__ == "__main__":
    main()
