#!/usr/bin/env python3
"""Seraph · validate_phase_close — the reality gate.

Blocks declaring a phase "done" without real, end-to-end evidence. Implements
the sacred foundation: "Si no es real, no cuenta." A theoretical win is not a
win.

Input JSON:
  {
    "phase": "develop",          # spec | develop | test | eval | <free>
    "e2e": true,                 # was an end-to-end happy-path check run?
    "evidence": "ran ./run ... output X",   # concrete proof (command/output/url)
    "tests": "passed 12/12"      # optional
  }

Exit 0 (PASS) only when e2e is true AND evidence is non-trivial.
Exit 1 (BLOCK) otherwise.
"""

from _common import emit, read_input, resolve_root

# Phases that may legitimately have no runtime E2E (pure planning/research).
NO_RUNTIME_PHASES = {"spec", "plan", "research"}


def main():
    data = read_input()
    phase = (data.get("phase") or "").strip().lower()
    e2e = bool(data.get("e2e"))
    evidence = (data.get("evidence") or "").strip()
    errors = []

    if phase in NO_RUNTIME_PHASES:
        # Planning/research phases close on a concrete artifact, not a runtime check.
        if len(evidence) < 8:
            errors.append("planning phase needs a concrete artifact reference as evidence")
    else:
        if not e2e:
            errors.append("no end-to-end happy-path check was run (e2e=false)")
        if len(evidence) < 8:
            errors.append("evidence is missing or trivial — provide the command/output/url that proves it real")

    result = {
        "hook": "validate_phase_close",
        "ok": not errors,
        "verdict": "PASS" if not errors else "BLOCK",
        "phase": phase or None,
        "root": resolve_root(),
        "errors": errors,
        "note": "Reality decides, not opinions. (Foundation 3.)",
    }
    emit(result)


if __name__ == "__main__":
    main()
