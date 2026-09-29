#!/usr/bin/env python3
"""Shared state for Telegram reply threads (Hardline Fase 2).

Single owner of the path, schema and access for
``<root>/brain/state/hardline/reply-threads.json``. Both writers — the Stop
hook (``_hardline_notify_common.py``) and the Telegram bridge
(``telegram-bridge.py``) — import this module so the schema is never
duplicated in two places (lesson 15). Standard library only.

Entry schema (keys are Telegram message_id strings):

    { "<message_id_str>": {
        "project": "<project-name|matrix>",
        "session_id": "<sid>" | null,
        "context": "<truncated output>" | null,
        "kind": "turn" | "ack",
        "created_at": <epoch_float>
    } }

- ``kind="turn"`` is written by the Stop hook after each per-turn message:
  ``session_id=null``, ``context`` = the turn output truncated to 1200 chars.
- ``kind="ack"`` is written by the bridge when it notifies an
  ``acked-success`` terminal event that carries a ``session_id``.

Entries expire after ``REPLY_TTL_SECONDS`` (48 h) and are capped at
``REPLY_MAX_ENTRIES`` (oldest first); the bridge sweeps on every loop.
"""

import fcntl
import json
import os
import time

REPLY_THREADS_FILE = "reply-threads.json"
LOCK_FILE = "reply-threads.lock"
REPLY_TTL_SECONDS = 172800
REPLY_MAX_ENTRIES = 1000


def path(root):
    """Absolute path of the reply-threads state file for a Matrix root."""
    return os.path.join(root, "brain", "state", "hardline", REPLY_THREADS_FILE)


def _lock_path(root):
    return os.path.join(root, "brain", "state", "hardline", LOCK_FILE)


def _entry_ts(entry):
    try:
        return float(entry.get("created_at")) if isinstance(entry, dict) else 0.0
    except (TypeError, ValueError):
        return 0.0


def load(root):
    """Return the reply-threads dict. Missing/corrupt/unreadable -> {}."""
    try:
        with open(path(root), encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save(root, data):
    """Atomically persist the dict (temp file + os.replace). False on OSError."""
    target = path(root)
    try:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        temporary = target + ".tmp"
        with open(temporary, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False)
        os.replace(temporary, target)
        return True
    except OSError:
        return False


def add_entry(root, message_id, entry):
    """Insert or overwrite one entry under a shared flock.

    Loads fresh under the lock so a concurrent writer is never lost, then
    saves atomically. Returns True on success, False on any OSError.
    """
    key = str(message_id)
    lock_path = _lock_path(root)
    try:
        os.makedirs(os.path.dirname(lock_path), exist_ok=True)
        fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    except OSError:
        return False
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
        except OSError:
            return False
        try:
            data = load(root)
            data[key] = entry
            return save(root, data)
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def sweep(root, ttl_seconds, max_entries, now=None):
    """Remove expired entries and, if still over cap, the oldest by created_at.

    Expired = ``created_at`` older than ``ttl_seconds``. Over-cap removes the
    oldest entries first. Saves only when something changed. Returns the
    number of entries removed. Never raises.
    """
    lock_path = _lock_path(root)
    try:
        os.makedirs(os.path.dirname(lock_path), exist_ok=True)
        fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    except OSError:
        return 0
    removed = 0
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
        except OSError:
            return 0
        try:
            data = load(root)
            now_ts = time.time() if now is None else now
            changed = False
            for key in [k for k, v in data.items() if now_ts - _entry_ts(v) > ttl_seconds]:
                del data[key]
                removed += 1
                changed = True
            if len(data) > max_entries:
                oldest = sorted(data.keys(), key=lambda k: _entry_ts(data[k]))
                for key in oldest[: len(data) - max_entries]:
                    del data[key]
                    removed += 1
                    changed = True
            if changed:
                save(root, data)
            return removed
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)
