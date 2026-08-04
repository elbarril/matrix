#!/usr/bin/env python3
"""Seraph · detect_orphan_session — find a stale orphan session to close retroactively.

Layer 1 portable hook. Reads brain/state/hook-audit.jsonl, groups events by
session_id, and returns the session_id of one candidate orphan that should be
closed. A candidate is a session that:

  - shares the same project_active as the detecting session
  - never emitted a session_end event
  - has no event newer than the staleness threshold (10 minutes)

Before returning a candidate, a cheap synchronous marker is written so a
burst of session_start events cannot trigger redundant closes of the same
orphan. The marker is a per-session_id line in
brain/state/orphan-close-attempts.jsonl.

Input (argv[1] or stdin):
  {"project_active": "<project>"}
"""
import datetime
import json
import os

from _common import emit, read_input, resolve_root

# Staleness threshold. Chosen generous enough to avoid closing genuinely
# concurrent sessions in crash-loop bursts while still catching real orphans.
STALENESS_MINUTES = 10
ATTEMPT_LOG = "orphan-close-attempts.jsonl"


def _read_jsonl(path):
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


def _parse_ts(ts):
    if not isinstance(ts, str):
        return None
    try:
        return datetime.datetime.fromisoformat(ts)
    except ValueError:
        return None


def _attempted_session_ids(attempt_path):
    """Return session_ids for which a close attempt was already recorded.

    We keep this as a simple permanent guardrail: once an attempt has been
    recorded for a session_id, we never try to close it again. session_close
    is idempotent and session_ids are not reused, so a single marker is enough
    to prevent redundant work during crash-loop bursts. If the attempt failed,
    the orphan stays open; that is accepted because this is a best-effort
    recovery mechanism (Foundation 4: start simple).
    """
    attempts = _read_jsonl(attempt_path)
    return {a.get("session_id") for a in attempts if a.get("session_id")}


def _record_attempt(attempt_path, session_id):
    os.makedirs(os.path.dirname(attempt_path), exist_ok=True)
    record = {
        "session_id": session_id,
        "timestamp": datetime.datetime.now().astimezone().isoformat(),
    }
    with open(attempt_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def main():
    data = read_input()
    root = resolve_root()

    project_active = data.get("project_active")
    now = datetime.datetime.now().astimezone()
    threshold = datetime.timedelta(minutes=STALENESS_MINUTES)

    audit_path = os.path.join(root, "brain", "state", "hook-audit.jsonl")
    entries = _read_jsonl(audit_path)

    # Group events by session_id.
    by_session = {}
    for entry in entries:
        sid = entry.get("session_id")
        if not sid:
            continue
        by_session.setdefault(sid, []).append(entry)

    attempt_path = os.path.join(root, "brain", "state", ATTEMPT_LOG)
    attempted = _attempted_session_ids(attempt_path)

    candidates = []
    for sid, evts in by_session.items():
        # Skip sessions that already ended or were already attempted.
        if any(e.get("event") == "session_end" for e in evts):
            continue
        if sid in attempted:
            continue

        # Find the latest event timestamp and a stable project_active.
        last_ts = None
        session_project = None
        for e in evts:
            ts = _parse_ts(e.get("timestamp"))
            if ts and (last_ts is None or ts > last_ts):
                last_ts = ts
            # Use the most recent non-null project_active seen for the session.
            p = e.get("project_active")
            if p is not None:
                session_project = p

        if last_ts is None:
            continue

        # Staleness: the last event of any type must be older than the threshold.
        if now - last_ts < threshold:
            continue

        # Scope to the same project_active as the detecting session.
        if session_project != project_active:
            continue

        candidates.append((last_ts, sid))

    orphan_session_id = None
    if candidates:
        # Promote the stalest orphan first; leave others unmarked so a future
        # session_start can pick them up without redundant attempts.
        candidates.sort(key=lambda x: x[0])
        orphan_session_id = candidates[0][1]
        _record_attempt(attempt_path, orphan_session_id)

    emit(
        {
            "hook": "detect_orphan_session",
            "ok": True,
            "orphan_session_id": orphan_session_id,
            "project_active": project_active,
            "candidates_found": len(candidates),
        }
    )


if __name__ == "__main__":
    main()
