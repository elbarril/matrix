#!/usr/bin/env python3
"""Seraph · audit_event — append-only metadata-only audit log for lifecycle events.

Layer 1 portable hook. Input is a generic envelope with a fixed allow-list of
metadata fields. Unknown keys are ignored. No prompt content or tool output is
ever written.
"""
import datetime
import json
import os

from _common import emit, read_input, resolve_root

ALLOWED = {"event", "timestamp", "session_id", "project_active", "pre_activation_check_ok", "tool_name", "tool_paths"}


def main():
    data = read_input()
    root = resolve_root()
    state_dir = os.path.join(root, "brain", "state")
    os.makedirs(state_dir, exist_ok=True)

    # Only copy allowed keys; drop anything else (including prompt content).
    envelope = {k: data.get(k) for k in ALLOWED}
    # Drop optional tool metadata when not supplied so non-tool events stay clean.
    if envelope.get("tool_name") is None:
        envelope.pop("tool_name", None)
    if envelope.get("tool_paths") is None:
        envelope.pop("tool_paths", None)

    # Normalize timestamp if missing or not a string.
    ts = envelope.get("timestamp")
    if not ts or not isinstance(ts, str):
        ts = datetime.datetime.now().astimezone().isoformat()
    envelope["timestamp"] = ts

    log_path = os.path.join(state_dir, "hook-audit.jsonl")
    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(envelope, ensure_ascii=False) + "\n")

    emit({"hook": "audit_event", "ok": True, "written_to": log_path})


if __name__ == "__main__":
    main()
