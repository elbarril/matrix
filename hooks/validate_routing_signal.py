#!/usr/bin/env python3
"""Seraph · validate_routing_signal — warn when real engineering work in a session
shows no Link evidence of delegation to Trinity/Smith/Architect.

Reads `brain/state/hook-audit.jsonl` for the session and `brain/state/activity.log`
for Link route/handoff entries. Warn-only: always returns `ok: true`. When the
pattern repeats for a 3rd time (2 prior triggers + this one), it exposes
`escalate_to_block: true` for a future process to decide on.

Input (argv[1] or stdin):
  {"session_id": "..."}   # optional
"""

import json
import os
import re
from datetime import datetime, timezone

from _common import current_session_id, emit, read_input, resolve_root


AUDIT_LOG = "brain/state/hook-audit.jsonl"
ACTIVITY_LOG = "brain/state/activity.log"
HISTORY_LOG = "brain/state/routing-signal-history.jsonl"

MUTATING_TOOLS = {"write", "edit", "multi_edit"}
RUN_COMMAND_TOOLS = {"exec", "run_command", "run-command"}
EXCLUDED_PREFIXES = ("brain/state/", "brain/output/")
DELEGATION_NAMES = ("trinity", "smith", "architect")

# Detection criterion (documented explicitly because activity.log is free text):
# A line counts as delegation evidence only if it contains "route" or "handoff"
# (case-insensitive) AND one of the three agent names (case-insensitive).
# A `phase:close` entry is NOT counted as delegation evidence; that is a separate
# checkpoint-discipline signal already handled by `_has_mutating_work` /
# `phase_close_missing` in session_close.py.
ROUTE_HANDOFF_RE = re.compile(r"\b(route|handoff)\b", re.IGNORECASE)
DELEGATION_RE = re.compile(
    r"\b(" + "|".join(re.escape(n) for n in DELEGATION_NAMES) + r")\b",
    re.IGNORECASE,
)


def _read_jsonl(path):
    """Read a JSONL file, skipping malformed lines."""
    entries = []
    if not os.path.isfile(path):
        return entries
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


def _is_excluded_path(root, raw_path):
    """Return True if raw_path is under brain/state/ or brain/output/."""
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
    return norm == "brain/state" or norm.startswith("brain/state/") or \
        norm == "brain/output" or norm.startswith("brain/output/")


def _parse_timestamp(value):
    """Parse ISO-8601 timestamps with or without fractional seconds/offset."""
    if not value:
        return None
    value = value.strip()
    # Python's fromisoformat handles offsets since 3.7, but not 'Z' until 3.11.
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _session_window(entries, session_id):
    """Return (start_dt, end_dt) for the session."""
    start_dt = None
    end_dt = None
    last_dt = None
    for entry in entries:
        if entry.get("session_id") != session_id:
            continue
        ts = _parse_timestamp(entry.get("timestamp"))
        if not ts:
            continue
        if not ts.tzinfo:
            ts = ts.replace(tzinfo=timezone.utc)
        if entry.get("event") == "session_start":
            if start_dt is None or ts < start_dt:
                start_dt = ts
        if entry.get("event") == "session_end":
            if end_dt is None or ts > end_dt:
                end_dt = ts
        if last_dt is None or ts > last_dt:
            last_dt = ts
    if end_dt is None:
        end_dt = last_dt
    return start_dt, end_dt


def _collect_mutating_real_paths(entries, root, session_id):
    """Return the set of distinct real file paths touched by mutating tools."""
    paths = set()
    for entry in entries:
        if entry.get("session_id") != session_id:
            continue
        if entry.get("event") != "post_tool_use":
            continue
        if entry.get("tool_name") not in MUTATING_TOOLS:
            continue
        for p in entry.get("tool_paths") or []:
            if not isinstance(p, str) or not p:
                continue
            if _is_excluded_path(root, p):
                continue
            paths.add(p)
    return paths


def _has_run_command(entries, session_id):
    """Return True if the session includes a run-command/exec post_tool_use."""
    for entry in entries:
        if entry.get("session_id") != session_id:
            continue
        if entry.get("event") != "post_tool_use":
            continue
        if entry.get("tool_name") in RUN_COMMAND_TOOLS:
            return True
    return False


def _find_delegation_evidence(root, start_dt, end_dt):
    """Search activity.log for route/handoff entries naming Trinity/Smith/Architect."""
    if start_dt is None or end_dt is None:
        return None
    path = os.path.join(root, ACTIVITY_LOG)
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            # Extract the leading timestamp. Accepted formats:
            #   2026-06-15T14:26:15-03:00 | ...
            #   [2024-06-23T10:30:00Z] phase:close | ...
            ts_str = ""
            if line.startswith("["):
                m = re.match(r"\[([^\]]+)\]\s*(.*)", line)
                if m:
                    ts_str = m.group(1)
                    rest = m.group(2)
                else:
                    rest = line
            else:
                parts = line.split(" | ", 1)
                ts_str = parts[0] if parts else ""
                rest = parts[1] if len(parts) > 1 else line
            ts = _parse_timestamp(ts_str)
            if not ts:
                continue
            if not ts.tzinfo:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts < start_dt or ts > end_dt:
                continue
            if ROUTE_HANDOFF_RE.search(rest) and DELEGATION_RE.search(rest):
                return line
    return None


def _prior_trigger_count(path):
    """Count how many times this signal has already fired in history."""
    if not os.path.isfile(path):
        return 0
    count = 0
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if record.get("triggered"):
                count += 1
    return count


def _record_trigger(path, session_id, triggered):
    """Append a trigger record if this session produced the signal."""
    if not triggered:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "triggered": True,
    }
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def validate(data):
    root = resolve_root()
    session_id = data.get("session_id") if data else None
    if not session_id:
        session_id = current_session_id(root)

    entries = _read_jsonl(os.path.join(root, AUDIT_LOG))
    start_dt, end_dt = _session_window(entries, session_id)

    mutating_paths = _collect_mutating_real_paths(entries, root, session_id)
    run_command_seen = _has_run_command(entries, session_id)

    # Decision #3: trigger threshold.
    #   >=2 distinct real files outside brain/state/brain/output
    #   OR >=1 mutating real file + >=1 run-command/exec in the same session.
    triggered = (
        len(mutating_paths) >= 2
        or (len(mutating_paths) >= 1 and run_command_seen)
    )

    delegation_evidence = None
    if triggered:
        delegation_evidence = _find_delegation_evidence(root, start_dt, end_dt)
        if delegation_evidence:
            triggered = False

    history_path = os.path.join(root, HISTORY_LOG)
    prior = 0
    escalate = False
    if triggered:
        prior = _prior_trigger_count(history_path)
        escalate = prior >= 2
        _record_trigger(history_path, session_id, triggered)

    message = None
    if triggered:
        message = (
            f"Session {session_id} did real engineering work "
            f"({len(mutating_paths)} file(s) edited, run_command={run_command_seen}) "
            f"but no Link route/handoff to Trinity/Smith/Architect was found in the session window."
        )
        if escalate:
            message += " This is the 3rd+ occurrence — escalate_to_block is set."

    return {
        "hook": "validate_routing_signal",
        "ok": True,
        "session_id": session_id,
        "triggered": triggered,
        "window": {
            "start": start_dt.isoformat() if start_dt else None,
            "end": end_dt.isoformat() if end_dt else None,
        },
        "mutating_paths": sorted(mutating_paths),
        "run_command_seen": run_command_seen,
        "delegation_evidence": delegation_evidence,
        "historical_triggers": prior,
        "escalate_to_block": escalate,
        "message": message,
    }


def main():
    emit(validate(read_input()))


if __name__ == "__main__":
    main()
