#!/usr/bin/env python3
"""Seraph · validate_phase_close — the reality gate.

Blocks declaring a phase "done" without real, end-to-end evidence. Implements
the sacred foundation: "Si no es real, no cuenta." A theoretical win is not a
win.

Input JSON:
  {
    "phase": "develop",          # spec | develop | test | eval — closed set; anything else BLOCKs
    "e2e": true,                 # JSON boolean true only — never 1/"true"/"false"
    "evidence": "ran ./run ... output X",   # concrete proof (command/output/url)
    "lesson": "<what was captured and where, or an explicit N/A>"  # required when phase == "eval"
    "session_id": "..."          # optional; used for routing-signal escalation attribution
  }

Exit 0 (PASS) only when e2e is JSON true AND evidence is non-trivial.
Exit 1 (BLOCK) otherwise. A non-object payload or wrong field types BLOCK with
a controlled JSON error, never a traceback.

For phase == "eval", the eval-phase contract (capturing lessons) is mandatory,
not optional flavor text — a phase cannot close on reality it didn't record. So
`lesson` must also be present and non-trivial: either a pointer to what was
appended to `brain/data/lessons.md` / `brain/data/lessons/<project>.md`, or an
explicit, reasoned "N/A" (reality taught nothing new worth keeping). A missing
`lesson` field is BLOCKed the same way missing `evidence` is — silence is not
a valid answer to "what did we learn".
"""

import os
import re
import sys
from collections import Counter

from _common import current_session_id, emit, ledger_tail_events, read_input, resolve_root
from validate_routing_signal import (
    count_unresolved_sessions,
    validate as validate_routing_signal,
)

# The canonical phase vocabulary (retired brain workflow reference docs;
# this set is now the single source of truth).
VALID_PHASES = {"spec", "develop", "test", "eval"}
# Phases that may legitimately have no runtime E2E (artifact-closing phases).
NO_RUNTIME_PHASES = {"spec"}
EVAL_PHASES = {"eval"}

HISTORY_LOG = "brain/state/routing-signal-history.jsonl"


def check_lesson_violations(root):
    """Return WARNs for lessons whose violation count reached the threshold."""
    events = ledger_tail_events(root)
    counts = Counter()
    for ev in events:
        if ev.get("event") != "lesson:violation":
            continue
        lesson = None
        detail = ev.get("detail") or ""
        m = re.search(r"lesson=(\d+)", detail)
        if m:
            lesson = m.group(1)
        else:
            subject = ev.get("subject") or ""
            if subject.isdigit():
                lesson = subject
        if lesson is None:
            continue
        counts[lesson] += 1

    warns = []
    for lesson, n in sorted(counts.items()):
        if n >= 2:
            warns.append(
                f"lesson:violation ×{n} para lección {lesson} — revisar "
                f"brain/data/lessons.md#{lesson} (umbral mecánico: 2)."
            )
    return warns


def _routing_escalation_warns(root, session_id):
    """Return routing-signal escalation warns for the CURRENT session only.

    Warns only when the current session is actually triggered (recomputed via
    validate_routing_signal, which never writes history here) and at least 2
    prior sessions are unresolved in history (last state per session wins,
    current excluded). Without a session_id, another session is never accused.
    """
    if not session_id:
        return []
    try:
        signal = validate_routing_signal({"session_id": session_id}, persist_history=False)
        current_triggered = signal.get("triggered") is True
    except Exception as exc:
        print(
            f"[validate_phase_close] routing-signal recompute failed for session "
            f"{session_id}: {type(exc).__name__}: {exc} — escalation check skipped",
            file=sys.stderr,
        )
        current_triggered = False
    if not current_triggered:
        return []
    prior, _ = count_unresolved_sessions(
        os.path.join(root, HISTORY_LOG), exclude_session_id=session_id
    )
    if prior < 2:
        return []
    return [
        {
            "source": "routing_signal_escalation",
            "detail": (
                f"routing-signal: escalada detectada (sesión {session_id}, "
                f"prior={prior}) — revisar delegación a Trinity/Smith/Architect."
            ),
        }
    ]


def main():
    data = read_input()
    root = resolve_root()

    if not isinstance(data, dict):
        emit({
            "hook": "validate_phase_close",
            "ok": False,
            "verdict": "BLOCK",
            "phase": None,
            "root": root,
            "errors": ["payload must be a JSON object — see `matrix phase close --help` for the schema"],
            "warns": [],
            "note": "Reality decides, not opinions. (Foundation 3.)",
        })
        return

    errors = []

    if "e2e_passed" in data and "e2e" not in data:
        errors.append("unknown key 'e2e_passed' — use 'e2e' (JSON boolean true/false)")

    phase = ""
    phase_ok = False
    phase_raw = data.get("phase")
    if phase_raw is None:
        errors.append("missing required field 'phase' (spec|develop|test|eval)")
    elif not isinstance(phase_raw, str):
        errors.append(f"'phase' must be a string, got {type(phase_raw).__name__}")
    else:
        phase = phase_raw.strip().lower()
        phase_ok = True

    e2e = False
    e2e_raw = data.get("e2e")
    if e2e_raw is not None and not isinstance(e2e_raw, bool):
        errors.append("'e2e' must be a JSON boolean true/false, never a string or number")
    else:
        e2e = e2e_raw is True

    evidence = ""
    evidence_raw = data.get("evidence")
    if evidence_raw is not None and not isinstance(evidence_raw, str):
        errors.append(f"'evidence' must be a string, got {type(evidence_raw).__name__}")
    else:
        evidence = (evidence_raw or "").strip()

    lesson = ""
    lesson_raw = data.get("lesson")
    if lesson_raw is not None and not isinstance(lesson_raw, str):
        errors.append(f"'lesson' must be a string, got {type(lesson_raw).__name__}")
    else:
        lesson = (lesson_raw or "").strip()

    session_id = None
    sid_raw = data.get("session_id")
    if sid_raw is not None and not isinstance(sid_raw, str):
        errors.append(f"'session_id' must be a string, got {type(sid_raw).__name__}")
    else:
        session_id = (sid_raw or "").strip() or None
    if not session_id:
        session_id = current_session_id(root)
        if not session_id:
            errors.append(
                "sesión ambigua o desconocida — pasá session_id explícito "
                "(el session_id=<sid> del contexto de activación)"
            )

    if phase_ok and phase not in VALID_PHASES:
        errors.append(
            f"unknown phase '{phase}' — valid phases are spec|develop|test|eval"
        )
    elif phase_ok and phase in NO_RUNTIME_PHASES:
        # Artifact-closing phases close on a concrete artifact, not a runtime check.
        if len(evidence) < 8:
            errors.append("planning phase needs a concrete artifact reference as evidence")
    elif phase_ok and phase in VALID_PHASES:
        if e2e is not True:
            errors.append("no end-to-end happy-path check was run (e2e must be JSON true)")
        if len(evidence) < 8:
            errors.append("evidence is missing or trivial — provide the command/output/url that proves it real")

    if phase_ok and phase in EVAL_PHASES and len(lesson) < 8:
        errors.append(
            "eval closes the loop by capturing lessons — 'lesson' is missing or trivial; "
            "state what was appended to lessons.md/lessons/<project>.md, or an explicit reasoned N/A"
        )

    warns = _routing_escalation_warns(root, session_id)

    for lesson_msg in check_lesson_violations(root):
        lesson_num = lesson_msg.split("lección ", 1)[-1].split(" —", 1)[0]
        warns.append(
            {
                "source": "lesson_violation",
                "detail": lesson_msg,
                "lesson": lesson_num,
            }
        )

    result = {
        "hook": "validate_phase_close",
        "ok": not errors,
        "verdict": "PASS" if not errors else "BLOCK",
        "phase": phase or None,
        "root": root,
        "errors": errors,
        "warns": warns,
        "note": "Reality decides, not opinions. (Foundation 3.)",
    }
    emit(result)


if __name__ == "__main__":
    main()
