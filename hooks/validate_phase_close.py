#!/usr/bin/env python3
"""Seraph · validate_phase_close — the reality gate.

Blocks declaring a phase "done" without real, end-to-end evidence. Implements
the sacred foundation: "Si no es real, no cuenta." A theoretical win is not a
win.

Input JSON:
  {
    "phase": "develop",          # spec | develop | test | eval — closed set; anything else BLOCKs
    "e2e": true,                 # was an end-to-end happy-path check run?
    "evidence": "ran ./run ... output X",   # concrete proof (command/output/url)
    "tests": "passed 12/12",     # optional
    "lesson": "<what was captured and where, or an explicit N/A>"  # required when phase == "eval"
  }

Exit 0 (PASS) only when e2e is true AND evidence is non-trivial.
Exit 1 (BLOCK) otherwise.

For phase == "eval", the eval-phase contract (capturing lessons) is mandatory,
not optional flavor text — a phase cannot close on reality it didn't record. So
`lesson` must also be present and non-trivial: either a pointer to what was
appended to `brain/data/lessons.md` / `brain/data/lessons/<project>.md`, or an
explicit, reasoned "N/A" (reality taught nothing new worth keeping). A missing
`lesson` field is BLOCKed the same way missing `evidence` is — silence is not
a valid answer to "what did we learn".
"""

from _common import emit, read_input, resolve_root

# The canonical phase vocabulary (retired brain workflow reference docs;
# this set is now the single source of truth).
VALID_PHASES = {"spec", "develop", "test", "eval"}
# Phases that may legitimately have no runtime E2E (artifact-closing phases).
NO_RUNTIME_PHASES = {"spec"}
EVAL_PHASES = {"eval"}


def main():
    data = read_input()
    phase = (data.get("phase") or "").strip().lower()
    e2e = bool(data.get("e2e"))
    evidence = (data.get("evidence") or "").strip()
    lesson = (data.get("lesson") or "").strip()
    errors = []

    if phase not in VALID_PHASES:
        errors.append(
            f"unknown phase '{phase}' — valid phases are spec|develop|test|eval"
        )
    elif phase in NO_RUNTIME_PHASES:
        # Artifact-closing phases close on a concrete artifact, not a runtime check.
        if len(evidence) < 8:
            errors.append("planning phase needs a concrete artifact reference as evidence")
    else:
        if not e2e:
            errors.append("no end-to-end happy-path check was run (e2e=false)")
        if len(evidence) < 8:
            errors.append("evidence is missing or trivial — provide the command/output/url that proves it real")

    if phase in EVAL_PHASES and len(lesson) < 8:
        errors.append(
            "eval closes the loop by capturing lessons — 'lesson' is missing or trivial; "
            "state what was appended to lessons.md/lessons/<project>.md, or an explicit reasoned N/A"
        )

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
