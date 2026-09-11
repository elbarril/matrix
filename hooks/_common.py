"""Seraph — shared helpers for portable enforcement hooks.

Hooks follow a JSON in / JSON out contract and are CLI-agnostic. Input is read
from argv[1] (a JSON string) or stdin; output is a JSON object on stdout. Exit
code is 0 on PASS, 1 on BLOCK/FAIL. No third-party dependencies.
"""

import datetime
import json
import os
import re
import subprocess
import sys
import time


def resolve_root():
    """Resolve the Matrix root: $MATRIX_ROOT, else walk up to brain/ + AGENTS.md."""
    env = os.environ.get("MATRIX_ROOT")
    if env and os.path.isdir(os.path.join(env, "brain")):
        return env
    d = os.path.dirname(os.path.abspath(__file__))
    d = os.path.dirname(d)  # hooks/ -> root
    cur = d
    while cur != "/":
        if os.path.isdir(os.path.join(cur, "brain")) and os.path.isfile(
            os.path.join(cur, "AGENTS.md")
        ):
            return cur
        cur = os.path.dirname(cur)
    return d


def parse_scalar_list(raw):
    """Parse a scalar YAML-style inline list."""
    v = raw.split("#", 1)[0].strip()
    if v.startswith("[") and v.endswith("]"):
        v = v[1:-1]
    if not v:
        return []
    return [item.strip().strip('"').strip("'") for item in v.split(",") if item.strip()]


def parse_frontmatter(path):
    """Return a dict of the YAML frontmatter in a markdown file."""
    data = {}
    if not os.path.isfile(path):
        return data
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    if not lines or lines[0].strip() != "---":
        return data
    for ln in lines[1:]:
        if ln.strip() == "---":
            break
        if ":" not in ln:
            continue
        k, v = ln.split(":", 1)
        k = k.strip()
        v = v.strip()
        if v.startswith("["):
            data[k] = parse_scalar_list(v)
        else:
            data[k] = v.strip('"').strip("'")
    return data


def read_input():
    """Read hook input as a dict from argv[1] (JSON) or stdin. Empty -> {}."""
    raw = ""
    if len(sys.argv) > 1 and sys.argv[1].strip():
        raw = sys.argv[1]
    elif not sys.stdin.isatty():
        try:
            raw = sys.stdin.read()
        except Exception:
            raw = ""
    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return {}


def current_session_id(root=None):
    """Return the synthetic session id from the marker file, or None."""
    if root is None:
        root = resolve_root()
    marker = os.path.join(root, "brain", "state", ".current-hook-session")
    if not os.path.isfile(marker):
        return None
    try:
        with open(marker, encoding="utf-8") as fh:
            sid = fh.read().strip()
        return sid or None
    except OSError:
        return None


def _load_registry(root):
    """Read .registry.json from the Matrix root, returning a dict on failure."""
    path = os.path.join(root, ".registry.json")
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (ValueError, OSError):
        return {}


def _registry_project(registry, name):
    """Find a project entry by name in a loaded registry dict."""
    if not isinstance(registry, dict):
        return None
    for proj in registry.get("projects", []):
        if proj.get("name") == name:
            return proj
    return None


def _load_yaml(path):
    """Load a YAML file, falling back to empty dict if yaml is unavailable."""
    try:
        import yaml
        with open(path, encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
    except Exception:
        return {}


def resolve_bound_target(project_name, root=None):
    """Resolve the adapter target for a project from .registry.json.

    bound_target is a registry fact (the adapter target a project was selected
    with), not a filesystem binding — the field name is conserved unchanged.

    Esta lectura de bound_target desde .registry.json es una segunda implementación
    en paralelo a la resolución equivalente en bash dentro de bin/matrix (jq sobre
    el mismo campo). Si bin/matrix cambia el shape de .registry.json o la semántica
    de bound_target, este resolutor debe actualizarse en el mismo commit.

    Falls back to "devin" when bound_target is missing or null, matching
    registry_bound_target() in bin/matrix.
    """
    if root is None:
        root = resolve_root()
    registry = _load_registry(root)
    proj = _registry_project(registry, project_name)
    if not proj:
        return None
    target = proj.get("bound_target")
    if not target or target == "null":
        target = "devin"
    return target


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


def _parse_iso_ts(ts):
    """Parse an ISO timestamp string; return a timezone-aware datetime or None."""
    if not ts:
        return None
    ts = ts.strip()
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    try:
        return datetime.datetime.fromisoformat(ts)
    except ValueError:
        return None


def ledger_tail_events(root, max_bytes=256 * 1024):
    """Return the most recent tail of the activity.log as a list of event dicts.

    Each dict has timestamp, event, subject, and detail. Lines that do not match
    the four-column pipe format are skipped. The read is bounded to max_bytes.
    """
    path = os.path.join(root, "brain", "state", "activity.log")
    if not os.path.isfile(path):
        return []
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
    events = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in re.split(r"\s*\|\s*", line, maxsplit=3)]
        if len(parts) < 4:
            continue
        ts = parts[0]
        if ts.startswith("[") and ts.endswith("]"):
            ts = ts[1:-1]
        events.append({"timestamp": ts, "event": parts[1], "subject": parts[2], "detail": parts[3]})
    return events


def _extract_ref(detail):
    """Return the ref slug between leading brackets, or None."""
    if not isinstance(detail, str):
        return None
    m = re.match(r"^\[([^\]]+)\]", detail.strip())
    return m.group(1) if m else None


def _extract_until(detail):
    """Return an (until_datetime_or_date, raw_string) pair from a detail, or (None, None)."""
    if not isinstance(detail, str):
        return None, None
    m = re.search(
        r"until=([0-9]{4}-[0-9]{2}-[0-9]{2}(?:[T ][0-9]{2}:[0-9]{2}(?::[0-9]{2})?(?:[+-][0-9]{2}:[0-9]{2}|Z)?)?)",
        detail,
    )
    if not m:
        return None, None
    raw = m.group(1)
    # Normalize a space separator to T for fromisoformat.
    normalized = re.sub(r"^(\d{4}-\d{2}-\d{2}) ", r"\1T", raw)
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    # If only a date, keep it as a date object for end-of-day semantics.
    if re.match(r"^\d{4}-\d{2}-\d{2}$", normalized):
        try:
            return datetime.date.fromisoformat(normalized), raw
        except ValueError:
            return None, raw
    try:
        return datetime.datetime.fromisoformat(normalized), raw
    except ValueError:
        return None, raw


PATH_DECISION_TEST_REFS = {"phase-path-decision-tkun6c", "phase-path-decision-tkunlk"}


def ttl_scan(events, now=None):
    """Return active and expired TTL-style events keyed by (event, subject).

    Parses until=YYYY-MM-DD[...] from event detail. Latest occurrence wins per
    (event, subject). For the fallback-A ttl:path-decision-reform event the
    result includes path_decision_real_uses excluding the two frozen test refs.
    """
    if now is None:
        now = datetime.datetime.now().astimezone()
    state = {}
    for ev in events:
        event = ev.get("event", "")
        subject = ev.get("subject", "")
        detail = ev.get("detail", "")
        until, _ = _extract_until(detail)
        if until is None:
            continue
        ts = _parse_iso_ts(ev.get("timestamp"))
        if ts is None:
            continue
        key = (event, subject)
        prev_ts = _parse_iso_ts(state[key]["timestamp"]) if key in state else None
        if prev_ts is None or ts >= prev_ts:
            state[key] = {"event": event, "subject": subject, "detail": detail, "timestamp": ev["timestamp"], "until": until}
    expired = []
    active = []
    for record in state.values():
        until = record["until"]
        if isinstance(until, datetime.datetime):
            is_expired = now > until
        else:
            # date-only: expired when the current date is strictly later.
            is_expired = now.date() > until
        record["until"] = until.isoformat()
        if is_expired:
            extra = {}
            if record["event"] == "ttl:path-decision-reform":
                uses = 0
                for e in events:
                    if e.get("event") == "phase:path-decision":
                        ref = _extract_ref(e.get("detail", ""))
                        if ref and ref not in PATH_DECISION_TEST_REFS:
                            uses += 1
                extra["path_decision_real_uses"] = uses
            expired.append({**record, **extra})
        else:
            active.append(record)
    return {"expired": expired, "active": active}


def model_override_active(events, now=None):
    """Return a dict of active model overrides keyed by agent/skill subject.

    Expects model:override events whose detail begins with an optional [ref],
    then the model name, then until=... Active means the until date has not passed.
    """
    if now is None:
        now = datetime.datetime.now().astimezone()
    state = {}
    for ev in events:
        if ev.get("event") != "model:override":
            continue
        subject = ev.get("subject", "")
        detail = ev.get("detail", "")
        until, _ = _extract_until(detail)
        if until is None:
            continue
        ts = _parse_iso_ts(ev.get("timestamp"))
        if ts is None:
            continue
        # Strip leading [ref] and trailing until=... to recover the model token.
        body = re.sub(r"^\[[^\]]+\]\s*", "", detail).strip()
        body = re.sub(r"\s*until=.*", "", body, flags=re.IGNORECASE).strip()
        model = body.split()[0] if body else ""
        if not model:
            continue
        record = {"model": model, "until": until, "detail": detail, "timestamp": ev["timestamp"]}
        prev_ts = _parse_iso_ts(state[subject]["timestamp"]) if subject in state else None
        if prev_ts is None or ts >= prev_ts:
            state[subject] = record
    active = {}
    for subject, record in state.items():
        until = record["until"]
        if isinstance(until, datetime.datetime):
            is_active = now <= until
        else:
            is_active = now.date() <= until
        record["until"] = until.isoformat()
        if is_active:
            active[subject] = record
    return active


def snapshot_window(root, events=None, now=None):
    """Determine whether a new metrics:snapshot is due.

    Stage 1 (cheap): window_start = max(last metrics:snapshot, d3:window-start);
    if less than MATRIX_SNAPSHOT_MIN_DAYS (default 30) days have elapsed, due:false.
    Stage 2 (cached 24h): count distinct session_ids since window_start with at
    least one post_tool_use of MUTATING_TOOLS or run_subagent outside brain/state.
    due:true when real_work_sessions >= MATRIX_SNAPSHOT_MIN_SESSIONS (default 5).
    """
    if now is None:
        now = datetime.datetime.now().astimezone()
    min_days = int(os.environ.get("MATRIX_SNAPSHOT_MIN_DAYS", 30))
    min_sessions = int(os.environ.get("MATRIX_SNAPSHOT_MIN_SESSIONS", 5))
    if events is None:
        events = ledger_tail_events(root)
    window_start = None
    for ev in events:
        if ev.get("event") in ("metrics:snapshot", "d3:window-start"):
            ts = _parse_iso_ts(ev.get("timestamp"))
            if ts is not None and (window_start is None or ts > window_start):
                window_start = ts
    if window_start is None:
        # No snapshot/window marker: treat as an ancient window to surface the reminder.
        days = 999
    else:
        days = (now - window_start).days
    result = {
        "window_start": window_start.isoformat() if window_start else None,
        "days": days,
        "min_days": min_days,
        "min_sessions": min_sessions,
        "real_work_sessions": 0,
    }
    if days < min_days:
        result.update({"due": False, "valid": True, "reason": "within_window"})
        return result
    # Stage 2: expensive, cached for 24h.
    cache_path = os.path.join(root, "brain", "state", "sessions", ".snapshot-window.json")
    try:
        with open(cache_path, encoding="utf-8") as fh:
            cache = json.load(fh)
        cache_ts = _parse_iso_ts(cache.get("cached_at"))
        if (
            cache_ts
            and (now - cache_ts).total_seconds() < 24 * 3600
            and cache.get("window_start") == result["window_start"]
        ):
            return cache
    except (OSError, ValueError, TypeError):
        pass
    real_work_sessions = set()
    log_path = os.path.join(root, "brain", "state", "hook-audit.jsonl")
    if os.path.isfile(log_path) and window_start is not None:
        with open(log_path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                if entry.get("event") != "post_tool_use":
                    continue
                ts = _parse_iso_ts(entry.get("timestamp"))
                if ts is None or ts < window_start:
                    continue
                sid = entry.get("session_id")
                if not sid:
                    continue
                tool_name = entry.get("tool_name")
                if tool_name in MUTATING_TOOLS:
                    paths = entry.get("tool_paths") or []
                    if not paths:
                        real_work_sessions.add(sid)
                        continue
                    for p in paths:
                        if not _is_state_path(root, p):
                            real_work_sessions.add(sid)
                            break
                elif tool_name == "run_subagent":
                    real_work_sessions.add(sid)
    count = len(real_work_sessions)
    due = count >= min_sessions
    reason = "sufficient_real_work" if due else "insufficient_real_work"
    result.update({
        "real_work_sessions": count,
        "due": due,
        "valid": due,
        "reason": reason,
    })
    try:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        cache = dict(result, cached_at=now.isoformat())
        tmp = f"{cache_path}.tmp-{os.getpid()}"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(cache, fh, ensure_ascii=False)
        os.replace(tmp, cache_path)
    except OSError:
        pass
    return result


def emit(result):
    """Print the result JSON and exit with the right code."""
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result.get("ok") else 1)
