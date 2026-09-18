#!/usr/bin/env python3
"""Seraph · session_close — manual/CI close audit for a session.

Reads brain/state/hook-audit.jsonl, isolates the audit lines for the given
session_id (or, when session_id is missing, every line since the most recent
session_start), derives the steps actually seen, and reuses the existing
post_run_audit logic to produce a validation report.

Input (argv[1] or stdin):
  {"session_id": "..."}   # session_id may be omitted
"""
import json
import os
import subprocess

from _common import _has_mutating_work, current_session_id, emit, read_input, resolve_root


AUDIT_LOG = "hook-audit.jsonl"


def _read_audit_log(path):
    if not os.path.isfile(path):
        return []
    entries = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except ValueError:
                continue
    return entries


def _filter_entries(entries, session_id):
    """Return entries for session_id, or all entries since last session_start."""
    if session_id:
        return [e for e in entries if e.get("session_id") == session_id]
    # Heuristic when no session_id is supplied: audit from the most recent
    # session_start to the end of the log. This lets a CI/manual close work
    # even when the caller did not capture the session id.
    last_idx = None
    for i in range(len(entries) - 1, -1, -1):
        if entries[i].get("event") == "session_start":
            last_idx = i
            break
    if last_idx is None:
        return entries
    return entries[last_idx:]


def _derive_steps(entries):
    """Derive an ordered, de-duplicated list of steps from the audit events."""
    steps = []
    for entry in entries:
        event = entry.get("event")
        if event and event not in steps:
            steps.append(event)
        if event == "session_start" and (
            entry.get("pre_activation_check_ok") is True
            or entry.get("pre_activation_check_status") in ("ok", "failed", "timeout", "error")
        ):
            if "pre_activation_check" not in steps:
                steps.append("pre_activation_check")
    return steps


def _session_start_status(entries):
    """Return the pre_activation_check_status of the session's session_start.

    Judged from the session's own audit record, never from the current global
    flag. Legacy entries without a status return None (still required).
    """
    for entry in entries:
        if entry.get("event") == "session_start":
            return entry.get("pre_activation_check_status")
    return None


# What a hook-derived audit can realistically observe. Unlike the LLM
# self-report default in post_run_audit.py (which expects "load_config" and
# "resolve_context" — steps no Devin lifecycle event exposes), a session
# built purely from hook-audit.jsonl can only ever see these two. Passing
# the default REQUIRED_STEPS here would make every session report
# bypass_suspected=true even for a perfectly compliant one. `session_end` is a
# lifecycle boundary, not an activation step, and is reported separately as
# `session_end_seen` so a mid-session close is not a false bypass.
SESSION_REQUIRED_STEPS = ["session_start", "pre_activation_check"]


def _run_post_run_audit(root, session_id, steps, required=None):
    """Invoke post_run_audit via bin/matrix with the derived steps."""
    if required is None:
        required = list(SESSION_REQUIRED_STEPS)
    bin_matrix = os.path.join(root, "bin", "matrix")
    payload = {"agent": "neo", "session_id": session_id, "steps": steps, "required": required}
    env = {**os.environ, "MATRIX_ROOT": root}
    proc = subprocess.run(
        [bin_matrix, "hooks", "post_run_audit", json.dumps(payload)],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        stdin=subprocess.DEVNULL,
    )
    if proc.stdout:
        try:
            return json.loads(proc.stdout)
        except ValueError:
            pass
    return {
        "hook": "post_run_audit",
        "ok": False,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def _run_validate_routing_signal_check(root, session_id):
    """Invoke validate_routing_signal check and return its JSON result defensively."""
    bin_matrix = os.path.join(root, "bin", "matrix")
    env = {**os.environ, "MATRIX_ROOT": root}
    payload = {"session_id": session_id} if session_id else {}
    proc = subprocess.run(
        [bin_matrix, "hooks", "validate_routing_signal", json.dumps(payload)],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        stdin=subprocess.DEVNULL,
    )
    if proc.stdout:
        try:
            return json.loads(proc.stdout)
        except ValueError:
            pass
    return {
        "hook": "validate_routing_signal",
        "ok": False,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def main():
    data = read_input()
    root = resolve_root()
    session_id = data.get("session_id") if data else None
    if not session_id:
        session_id = current_session_id()

    log_path = os.path.join(root, "brain", "state", AUDIT_LOG)
    entries = _read_audit_log(log_path)
    filtered = _filter_entries(entries, session_id)
    steps = _derive_steps(filtered)

    required = list(SESSION_REQUIRED_STEPS)
    start_status = _session_start_status(filtered)
    if start_status == "disabled":
        required = [s for s in required if s != "pre_activation_check"]
    has_mutating_work = _has_mutating_work(filtered, root)
    if has_mutating_work:
        required.append("phase_close")
    phase_close_missing = has_mutating_work and "phase_close" not in steps

    validate_routing_signal_report = _run_validate_routing_signal_check(root, session_id)
    smith_gate_required = has_mutating_work and validate_routing_signal_report.get("triggered") is True
    if smith_gate_required:
        required.append("smith_gate")

    post_report = _run_post_run_audit(root, session_id, steps, required)

    result = {
        "hook": "session_close",
        "ok": post_report.get("ok", False),
        "session_id": session_id,
        "phase_close_missing": phase_close_missing,
        "smith_gate_required": smith_gate_required,
        "session_end_seen": "session_end" in steps,
        "steps_seen": steps,
        "entries_examined": len(filtered),
        "pre_activation_check_status": start_status,
        "pre_activation_check_failed": start_status in ("failed", "timeout", "error"),
        "validation": post_report,
        "validate_routing_signal_check": validate_routing_signal_report,
    }
    emit(result)


if __name__ == "__main__":
    main()
