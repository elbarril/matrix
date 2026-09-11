#!/usr/bin/env python3
"""Seraph · audit_event — append-only metadata-only audit log for lifecycle events.

Layer 1 portable hook. Input is a generic envelope with a fixed allow-list of
metadata fields. Unknown keys are ignored. No prompt content or tool output is
ever written.
"""
import datetime
import json
import os
import sys
import time

from _common import emit, read_input, resolve_root


AUDIT_MAX_BYTES = 16 * 1024 * 1024
AUDIT_ARCHIVE_RETENTION = 6


def _counter_path(state_dir, session_id):
    return os.path.join(state_dir, "sessions", f"{session_id}-post-tool-count.json")


def _write_counter(state_dir, session_id, count, log_path):
    if not session_id:
        return
    path = _counter_path(state_dir, session_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    stat = os.stat(log_path)
    data = {"count": count, "log_inode": stat.st_ino, "log_size": stat.st_size}
    tmp = f"{path}.tmp-{os.getpid()}"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    os.replace(tmp, path)


def _read_or_rebuild_count(state_dir, session_id, log_path):
    path = _counter_path(state_dir, session_id)
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        stat = os.stat(log_path)
        if data.get("log_inode") == stat.st_ino and data.get("log_size", 0) <= stat.st_size:
            return int(data.get("count", 0))
    except (OSError, ValueError, TypeError):
        pass
    count = 0
    if os.path.isfile(log_path):
        with open(log_path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                if entry.get("session_id") == session_id and entry.get("event") == "post_tool_use":
                    count += 1
    print(f"[audit_event] rebuilt divergent counter for session {session_id}", file=sys.stderr)
    return count


def _rotate_if_needed(log_path):
    max_bytes = int(os.environ.get("MATRIX_HOOK_AUDIT_MAX_BYTES", AUDIT_MAX_BYTES))
    if not os.path.isfile(log_path) or os.path.getsize(log_path) <= max_bytes:
        return {}
    with open(log_path, encoding="utf-8") as fh:
        lines = fh.readlines()
    latest = {}
    parsed = []
    for line in lines:
        try:
            entry = json.loads(line)
        except ValueError:
            parsed.append((line, None))
            continue
        parsed.append((line, entry))
        if entry.get("session_id"):
            latest[entry["session_id"]] = entry.get("event")
    active = {sid for sid, event in latest.items() if event != "session_end"}
    archive = f"{log_path}.{time.strftime('%Y%m%d-%H%M%S')}.{os.getpid()}"
    os.replace(log_path, archive)
    active_counts = {}
    with open(log_path, "w", encoding="utf-8") as fh:
        for line, entry in parsed:
            if entry and entry.get("session_id") in active:
                fh.write(line)
                if entry.get("event") == "post_tool_use":
                    sid = entry["session_id"]
                    active_counts[sid] = active_counts.get(sid, 0) + 1
    archives = sorted(
        (p for p in os.listdir(os.path.dirname(log_path)) if p.startswith("hook-audit.jsonl.")),
        reverse=True,
    )
    for old in archives[AUDIT_ARCHIVE_RETENTION:]:
        try:
            os.remove(os.path.join(os.path.dirname(log_path), old))
        except OSError:
            pass
    return active_counts

ALLOWED = {
    "event", "timestamp", "session_id", "project_active", "pre_activation_check_ok",
    "pre_activation_check_status", "boot_warn",
    "tool_name", "tool_paths", "subagent_profile", "subagent_invocation_id", "tool_command_head",
    "tool_command_unparsed",
    # nunca agregar `tool_response` ni claves que contengan contenido de archivo a
    # esta lista -- ver eval de Smith, ronda 4 de discovery-mediation.
    "invoked_artifact", "invoked_origin",
    # guard_decision/guard_reason: solo allow|block y una razón redactada
    # (verbo fijo + relpath de una lista pública) -- nunca comando/tool_input
    # crudo ni texto de excepción. Ver hooks/pre_exec_guard.py y
    # adapters/devin/hooks/pre_tool_use_guard.py.
    "guard_decision", "guard_reason",
}

BOOT_WARN_IDS = {
    "the_source",
    "validate_layer2",
    "validate_lessons",
    "surface_budget",
    "model_drift",
    "ttl_expired",
    "snapshot_due",
}


def main():
    data = read_input()
    root = resolve_root()

    if not isinstance(data, dict) or not isinstance(data.get("event"), str) or not data.get("event").strip():
        emit({
            "hook": "audit_event",
            "ok": False,
            "errors": ["payload must be a JSON object with a non-empty 'event' string — see `matrix hooks audit_event --help`"],
        })
        return

    state_dir = os.path.join(root, "brain", "state")
    os.makedirs(state_dir, exist_ok=True)

    # Only copy allowed keys; drop anything else (including prompt content).
    envelope = {k: data.get(k) for k in ALLOWED}
    # Sanitize boot_warn to the closed token set; details never leave the hook JSON.
    if envelope.get("boot_warn"):
        envelope["boot_warn"] = [
            t for t in envelope["boot_warn"]
            if isinstance(t, str) and t in BOOT_WARN_IDS
        ] or None
    if not envelope.get("boot_warn"):
        envelope.pop("boot_warn", None)
    # Drop optional keys when not supplied so non-relevant events stay clean.
    for optional_key in (
        "tool_name", "tool_paths", "subagent_profile", "subagent_invocation_id",
        "tool_command_head", "tool_command_unparsed",
        "invoked_artifact", "invoked_origin", "pre_activation_check_ok",
        "pre_activation_check_status", "boot_warn",
    ):
        if envelope.get(optional_key) is None:
            envelope.pop(optional_key, None)

    # Normalize timestamp if missing or not a string.
    ts = envelope.get("timestamp")
    if not ts or not isinstance(ts, str):
        ts = datetime.datetime.now().astimezone().isoformat()
    envelope["timestamp"] = ts

    log_path = os.path.join(state_dir, "hook-audit.jsonl")
    prior_count = None
    if envelope.get("event") == "post_tool_use" and envelope.get("session_id"):
        prior_count = _read_or_rebuild_count(state_dir, envelope["session_id"], log_path)
    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(envelope, ensure_ascii=False) + "\n")

    active_counts = _rotate_if_needed(log_path)
    if active_counts:
        for sid, count in active_counts.items():
            _write_counter(state_dir, sid, count, log_path)
    elif prior_count is not None:
        _write_counter(state_dir, envelope["session_id"], prior_count + 1, log_path)

    emit({"hook": "audit_event", "ok": True, "written_to": log_path})


if __name__ == "__main__":
    main()
