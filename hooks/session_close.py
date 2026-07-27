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

from _common import current_session_id, emit, read_input, resolve_root


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
        if event == "session_start" and entry.get("pre_activation_check_ok") is True:
            if "pre_activation_check" not in steps:
                steps.append("pre_activation_check")
    return steps


MUTATING_TOOLS = {"write", "edit", "multi_edit"}


def _is_state_path(root, raw_path):
    """Return True if raw_path is under brain/state/** relative to root."""
    if not isinstance(raw_path, str) or not raw_path:
        return False
    if os.path.isabs(raw_path):
        try:
            rel = os.path.relpath(raw_path, root)
        except ValueError:
            rel = raw_path
    else:
        rel = raw_path
    norm = os.path.normpath(rel).replace(os.sep, "/")
    return norm == "brain/state" or norm.startswith("brain/state/")


def _has_mutating_work(entries, root):
    """Return True if any post_tool_use mutating tool touches a path outside brain/state."""
    for entry in entries:
        if entry.get("event") != "post_tool_use":
            continue
        tool_name = entry.get("tool_name")
        if tool_name not in MUTATING_TOOLS:
            continue
        paths = entry.get("tool_paths") or []
        if not paths:
            # fail-closed: a mutating tool with no visible path cannot be proven state-only
            return True
        for p in paths:
            if not _is_state_path(root, p):
                return True
    return False


# What a hook-derived audit can realistically observe. Unlike the LLM
# self-report default in post_run_audit.py (which expects "load_config" and
# "resolve_context" — steps no Devin lifecycle event exposes), a session
# built purely from hook-audit.jsonl can only ever see these three. Passing
# the default REQUIRED_STEPS here would make every session report
# bypass_suspected=true even for a perfectly compliant one.
SESSION_REQUIRED_STEPS = ["session_start", "pre_activation_check", "session_end"]


def _run_post_run_audit(root, steps, required=None):
    """Invoke post_run_audit via bin/matrix with the derived steps."""
    if required is None:
        required = list(SESSION_REQUIRED_STEPS)
    bin_matrix = os.path.join(root, "bin", "matrix")
    payload = {"agent": "neo", "steps": steps, "required": required}
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


def _run_the_source_check(root):
    """Invoke the Source check and return its JSON result defensively."""
    bin_matrix = os.path.join(root, "bin", "matrix")
    env = {**os.environ, "MATRIX_ROOT": root}
    proc = subprocess.run(
        [bin_matrix, "hooks", "the_source", json.dumps({"check": True})],
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
        "hook": "the_source",
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
    has_mutating_work = _has_mutating_work(filtered, root)
    if has_mutating_work:
        required.append("phase_close")
    phase_close_missing = has_mutating_work and "phase_close" not in steps

    post_report = _run_post_run_audit(root, steps, required)
    the_source_report = _run_the_source_check(root)

    result = {
        "hook": "session_close",
        "ok": post_report.get("ok", False),
        "session_id": session_id,
        "phase_close_missing": phase_close_missing,
        "steps_seen": steps,
        "entries_examined": len(filtered),
        "validation": post_report,
        "the_source_check": the_source_report,
    }
    emit(result)


if __name__ == "__main__":
    main()
