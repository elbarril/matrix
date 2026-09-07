"""Seraph · _writer_lane — per-file writer lane (single-flight) for the shared
surface. Layer 1 helper owned by the shared-surface gate; both the Devin
adapter guard (adapters/devin/hooks/pre_tool_use_guard.py) and the audit
adapter (session_audit.py) import it via the same sys.path pattern as
_common.

Representation: one file per target under brain/state/lanes/ named
<sha1(rel_path)[:16]>.json with {"session_id": <sid|null>,
"timestamp": <iso-utc>, "rel_path": <rel_path>}.

Acquisition is atomic via os.open(O_CREAT|O_EXCL). Reentrancy is per
session_id. A lane held beyond TTL seconds (env MATRIX_WRITER_LANE_TTL_S,
default 120) is reclaimable. Release is best-effort: it only removes the
lane when holder == session_id.
"""
import datetime
import hashlib
import json
import os


LANES_DIR = os.path.join("brain", "state", "lanes")


def normalize_relpath(root, raw_path):
    """Return a normalized posix relative path under root, or None if outside."""
    if not isinstance(raw_path, str) or not raw_path:
        return None
    if os.path.isabs(raw_path):
        try:
            rel = os.path.relpath(raw_path, root)
        except ValueError:
            return None
    else:
        rel = raw_path
    norm = os.path.normpath(rel).replace(os.sep, "/")
    if norm == ".." or norm.startswith("../"):
        return None
    return norm


def lane_path(root, rel_path):
    digest = hashlib.sha1(rel_path.encode("utf-8")).hexdigest()[:16]
    return os.path.join(root, LANES_DIR, digest + ".json")


def _now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _parse_ts(value):
    if not value:
        return None
    try:
        return datetime.datetime.fromisoformat(value)
    except ValueError:
        return None


def _read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _write(path, data):
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False)
        return True
    except OSError:
        return False


def acquire(root, rel_path, session_id, ttl_s=120):
    """Acquire the per-file writer lane atomically.

    Returns:
      {"ok": True, "reentrant": False, "stale_reclaimed": False}  — acquired
      {"ok": True, "reentrant": True, ...}                         — same session holds it
      {"ok": False, "reason": "busy", "holder": sid, "since": iso} — held by another session
    """
    path = lane_path(root, rel_path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = {
        "session_id": session_id,
        "timestamp": _now_iso(),
        "rel_path": rel_path,
    }
    existing = None
    for _attempt in range(2):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            existing = _read(path)
        else:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False)
            return {"ok": True, "reentrant": False, "stale_reclaimed": False}
        if existing is None:
            continue
        holder = existing.get("session_id")
        ts = _parse_ts(existing.get("timestamp"))
        age = (datetime.datetime.now(datetime.timezone.utc) - ts).total_seconds() if ts else None
        if holder == session_id:
            _write(path, payload)
            return {"ok": True, "reentrant": True, "stale_reclaimed": False}
        if age is not None and age < ttl_s:
            return {
                "ok": False,
                "reason": "busy",
                "holder": holder,
                "since": existing.get("timestamp"),
            }
        # Stale: reclaim via rename + retry O_EXCL.
        try:
            os.rename(path, path + ".stale")
        except OSError:
            continue
        try:
            os.remove(path + ".stale")
        except OSError:
            pass
    return {
        "ok": False,
        "reason": "busy",
        "holder": existing.get("session_id") if existing else None,
        "since": existing.get("timestamp") if existing else None,
    }


def release(root, rel_path, session_id):
    """Best-effort release; only removes the lane when holder == session_id."""
    path = lane_path(root, rel_path)
    existing = _read(path)
    if existing is None:
        return False
    if existing.get("session_id") != session_id:
        return False
    try:
        os.remove(path)
        return True
    except OSError:
        return False


def status(root, rel_path, ttl_s=120):
    """Return a held-lane descriptor when the lane is busy, else None."""
    path = lane_path(root, rel_path)
    existing = _read(path)
    if existing is None:
        return None
    ts = _parse_ts(existing.get("timestamp"))
    if ts is None:
        return None
    age = (datetime.datetime.now(datetime.timezone.utc) - ts).total_seconds()
    if age >= ttl_s:
        return None
    return {"holder": existing.get("session_id"), "since": existing.get("timestamp")}


def lanes_for_session(root, session_id):
    """Return the list of lane files currently held by this session (best-effort)."""
    directory = os.path.join(root, LANES_DIR)
    found = []
    if not os.path.isdir(directory):
        return found
    try:
        names = sorted(os.listdir(directory))
    except OSError:
        return found
    for name in names:
        if not name.endswith(".json"):
            continue
        data = _read(os.path.join(directory, name))
        if data and data.get("session_id") == session_id:
            found.append(os.path.join(directory, name))
    return found
