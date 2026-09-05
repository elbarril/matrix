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

import json
import os
import re
from collections import Counter

from _common import emit, ledger_tail_events, read_input, resolve_root

# The canonical phase vocabulary (retired brain workflow reference docs;
# this set is now the single source of truth).
VALID_PHASES = {"spec", "develop", "test", "eval"}
# Phases that may legitimately have no runtime E2E (artifact-closing phases).
NO_RUNTIME_PHASES = {"spec"}
EVAL_PHASES = {"eval"}

HISTORY_MAX_BYTES = 256 * 1024
HISTORY_LOG = "brain/state/routing-signal-history.jsonl"


def _tail_jsonl(path, max_bytes=HISTORY_MAX_BYTES):
    """Read the most recent tail of a JSONL file, skipping malformed lines."""
    records = []
    if not os.path.isfile(path):
        return records
    try:
        size = os.path.getsize(path)
        if size > max_bytes:
            with open(path, "rb") as fh:
                fh.seek(size - max_bytes)
                text = fh.read(max_bytes).decode("utf-8", errors="replace")
            if "\n" in text:
                text = text.split("\n", 1)[1]
        else:
            with open(path, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
    except OSError:
        return records
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except ValueError:
            continue
    return records


def check_routing_escalate(root):
    """Return a WARN if the latest routing-signal history entry escalates."""
    path = os.path.join(root, HISTORY_LOG)
    records = _tail_jsonl(path)
    if not records:
        return None
    triggered = [r for r in records if r.get("triggered")]
    if not triggered:
        return None
    latest = triggered[-1]
    prior = len(triggered) - 1
    if prior < 2:
        return None
    session_id = latest.get("session_id") or "unknown"
    return (
        f"routing-signal: escalate_to_block detectado (sesión {session_id}, "
        f"prior={prior}) — revisar delegación a Trinity/Smith/Architect."
    )


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

    root = resolve_root()
    warns = []

    escalate_msg = check_routing_escalate(root)
    if escalate_msg:
        warns.append({"source": "escalate_to_block", "detail": escalate_msg})

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
