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


# Roster + supporting agents — single owner in the kernel. Moved here from
# pre_activation_check to break the pre_activation_check <-> install_integrity
# import cycle (G3 S2); both hooks import these names.
ROSTER = ["neo", "oracle", "morpheus", "architect", "trinity", "smith"]

# Infrastructure agents that deliberately live as installable subagent files in
# brain/agents/ but are NOT subject to roster discipline (see
# brain/data/contract-catalog.md "Supporting cast" — retire-one-to-add-one
# applies only to ROSTER above).
# docs/SYSTEM_TRUTH.md lists these alongside the roster with their own description.
# Add a name here ONLY if brain/data/contract-catalog.md already documents it as
# supporting-cast infrastructure — never to silently permit an undocumented new file.
SUPPORTING_AGENTS = ["lock"]


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


# --- Session identity bindings (D1/A0) ------------------------------------
# Single owner for the binding schema, path and TTL in Layer 1. The adapter
# (adapters/devin/hooks/session_audit.py) imports these helpers; the path is
# never duplicated. `brain/state/sessions/<sid>.json` is owned by `matrix
# focus` (bin/lib/registry.sh), so the liveness binding lives at
# `brain/state/sessions/<sid>-binding.json` — no collision.
SESSION_BINDING_DIR = os.path.join("brain", "state", "sessions")
SESSION_BINDING_SUFFIX = "-binding.json"
SESSION_BINDING_DEFAULT_TTL_S = 900
SESSION_BINDING_HEARTBEAT_INTERVAL_S = 60
SESSION_MARKER = os.path.join("brain", "state", ".current-hook-session")

# --- Session artifact pruning (G3 S4) --------------------------------------
# TTL per artifact type in brain/state/sessions/. "Alive" means the sid has a
# fresh liveness binding (<SESSION_BINDING_TTL), which touch_session_binding
# refreshes on every post_tool_use. The TTLs are generous by design: pruning
# only touches files whose session is long dead, never a working one.
SESSION_ARTIFACT_TTL_DAYS = {
    "post-tool-count": 14,
    "plain-sid": 14,
    "validation-report": 30,
    "phase-close-nudge": 7,
}
# All prunable kinds except the liveness binding. The sid must be resolved
# BEFORE these are pruned so the current session's own focus survives (the
# plain-sid rule needs current_sid); see current_session_id.
SESSION_ARTIFACT_NON_BINDING_KINDS = frozenset(SESSION_ARTIFACT_TTL_DAYS)
# Known per-session artifact suffixes. user-prompt-count is classified here so
# it never falls through to plain-sid; it has no TTL entry and is not pruned.
SESSION_ARTIFACT_SUFFIXES = {
    "binding": "-binding.json",
    "post-tool-count": "-post-tool-count.json",
    "user-prompt-count": "-user-prompt-count.json",
    "validation-report": "-validation-report.json",
    "phase-close-nudge": "-phase-close-nudge.json",
}


def _session_binding_ttl_s():
    return int(os.environ.get("MATRIX_SESSION_BINDING_TTL_S", SESSION_BINDING_DEFAULT_TTL_S))


def session_binding_path(root, session_id):
    return os.path.join(root, SESSION_BINDING_DIR, f"{session_id}{SESSION_BINDING_SUFFIX}")


def _session_binding_paths(root):
    directory = os.path.join(root, SESSION_BINDING_DIR)
    if not os.path.isdir(directory):
        return []
    try:
        names = sorted(os.listdir(directory))
    except OSError:
        return []
    return [
        os.path.join(directory, name)
        for name in names
        if name.endswith(SESSION_BINDING_SUFFIX)
    ]


def read_binding(path):
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def _write_binding(path, data):
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False)
        return True
    except OSError:
        return False


def _binding_now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _binding_fresh(binding):
    """True when the binding's last_seen_at is within TTL of now."""
    ts = _parse_iso_ts(binding.get("last_seen_at"))
    if ts is None:
        return False
    now = datetime.datetime.now().astimezone()
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=now.tzinfo)
    return (now - ts).total_seconds() <= _session_binding_ttl_s()


def _classify_session_artifact(name):
    """Classify a brain/state/sessions filename as (kind, sid) or (None, None)."""
    if name.startswith(".") or not name.endswith(".json"):
        return None, None
    for kind, suffix in SESSION_ARTIFACT_SUFFIXES.items():
        if name.endswith(suffix):
            return kind, name[: -len(suffix)]
    return "plain-sid", name[: -len(".json")]


def prune_session_artifacts(root, current_sid=None, dry_run=False, kinds=None):
    """Generalized TTL pruning of brain/state/sessions artifacts (G3 S4).

    Extends the binding-prune precedent (2*TTL) to every session artifact type:

      binding           age > 2*TTL (unchanged)                       never a fresh binding
      post-tool-count   14 d and no fresh binding for the sid        never an alive sid
      plain-sid (focus) 14 d and no fresh binding for the sid        never an alive sid, never current sid
      validation-report 30 d and no fresh binding for the sid        never an alive sid
      phase-close-nudge 7 d                                          always prunable past TTL

    kinds restricts which artifact kinds are considered (None = all). The
    caller owns the ordering: bindings may be pruned before the current sid is
    known (they are protected by freshness only), but NON-binding kinds must
    only be pruned once current_sid is resolved, or the current session's own
    focus/counter would be deleted (see current_session_id).

    "Alive" = the sid has a fresh liveness binding (touch_session_binding
    refreshes it on every post_tool_use). Pruning is best-effort and never a
    correctness requirement — the readers already ignore stale files, so a
    failed prune only accumulates disk until the next success.

    Every removed path is logged to the Link ledger as prune:session-artifact
    via ledger_append (the kernel is the only writer; hooks never touch
    activity.log directly). dry_run lists the candidates without removing or
    logging anything.

    Race (accepted, cosmetic — see hooks-design-hardening-g3-review.md §3):
    pruning also runs at session_start. A session resumed after 14+ days has no
    fresh binding in that instant, so its own session_start — or any concurrent
    session's prune — can remove its counter/validation-report. Focus and
    counter are rebuildable (the counter rebuilds from hook-audit.jsonl); the
    plain-sid rule additionally protects the focus whose sid == the current
    session. Covered by the S4 E2E.

    Returns a list of removed {path, kind, sid, age_days} records.
    """
    if kinds is not None:
        kinds = set(kinds)
    directory = os.path.join(root, SESSION_BINDING_DIR)
    if not os.path.isdir(directory):
        return []
    now = datetime.datetime.now().astimezone()
    alive = set()
    if kinds is None or any(k != "binding" for k in kinds):
        for bp in _session_binding_paths(root):
            binding = read_binding(bp)
            if binding and _binding_fresh(binding):
                sid = binding.get("session_id")
                if sid:
                    alive.add(sid)
    try:
        names = sorted(os.listdir(directory))
    except OSError:
        return []
    removed = []
    for name in names:
        kind, sid = _classify_session_artifact(name)
        if kind is None:
            continue
        if kinds is not None and kind not in kinds:
            continue
        path = os.path.join(directory, name)
        if kind == "binding":
            binding = read_binding(path)
            if binding is None:
                continue
            ts = _parse_iso_ts(binding.get("last_seen_at"))
            if ts is None:
                continue
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=now.tzinfo)
            age_days = (now - ts).total_seconds() / 86400.0
            if age_days <= 2 * _session_binding_ttl_s() / 86400.0:
                continue
        else:
            ttl_days = SESSION_ARTIFACT_TTL_DAYS.get(kind)
            if ttl_days is None:
                continue
            try:
                age_days = (now.timestamp() - os.path.getmtime(path)) / 86400.0
            except OSError:
                continue
            if age_days <= ttl_days:
                continue
            if kind != "phase-close-nudge":
                if sid in alive:
                    continue
                if kind == "plain-sid" and current_sid and sid == current_sid:
                    continue
        if not dry_run:
            try:
                os.remove(path)
            except OSError:
                continue
            ledger_append(
                root,
                "prune:session-artifact",
                sid or "matrix",
                f"path={os.path.relpath(path, root)} | kind={kind} | age_days={age_days:.1f}",
                session_id=sid,
            )
        removed.append({
            "path": path,
            "kind": kind,
            "sid": sid,
            "age_days": round(age_days, 2),
        })
    return removed


def write_session_binding(root, session_id, project_active=None):
    """Create/refresh the liveness binding for a session (session_start).

    Best-effort: a failed write never blocks the session. Prunes stale
    bindings on the way in (hygiene, not correctness).
    """
    if not session_id:
        return
    prune_session_artifacts(root, current_sid=session_id)
    path = session_binding_path(root, session_id)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
    except OSError:
        return
    now = _binding_now_iso()
    _write_binding(path, {
        "session_id": session_id,
        "started_at": now,
        "project_active": project_active,
        "last_seen_at": now,
    })


def touch_session_binding(root, session_id):
    """Refresh last_seen_at, throttled to HEARTBEAT_INTERVAL_S.

    A busy session (every post_tool_use) must not rewrite the binding on every
    tool call. Best-effort.
    """
    if not session_id:
        return
    path = session_binding_path(root, session_id)
    existing = read_binding(path)
    if existing is None:
        write_session_binding(root, session_id)
        return
    ts = _parse_iso_ts(existing.get("last_seen_at"))
    now = datetime.datetime.now().astimezone()
    if ts is not None:
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=now.tzinfo)
        if (now - ts).total_seconds() < SESSION_BINDING_HEARTBEAT_INTERVAL_S:
            return
    existing["last_seen_at"] = _binding_now_iso()
    _write_binding(path, existing)


def remove_session_binding(root, session_id):
    """Remove the liveness binding (session_end). Best-effort."""
    if not session_id:
        return
    try:
        os.remove(session_binding_path(root, session_id))
    except OSError:
        pass


def _marker_session_id(root):
    marker = os.path.join(root, SESSION_MARKER)
    if not os.path.isfile(marker):
        return None
    try:
        with open(marker, encoding="utf-8") as fh:
            sid = fh.read().strip()
        return sid or None
    except OSError:
        return None


def current_session_id(root=None, session_id=None):
    """Resolve the current session id fail-closed (D1/A0).

    Order (strict):
      1. explicit session_id (payload/env MATRIX_SESSION_ID) -> always wins;
      2. 0 binding files -> legacy marker (.current-hook-session);
      3. exactly 1 binding file and fresh (now - last_seen_at <= TTL) -> it;
      4. any other case (2+ files, or 1 stale) -> None (ambiguous/unknown).
    None means the caller should BLOCK and ask for an explicit session_id.
    "Active" is derived from last_seen_at at read time, never from the file's
    existence; never resolve to "the only active one" — that reopens the race.
    """
    if session_id:
        return session_id
    env_sid = os.environ.get("MATRIX_SESSION_ID", "").strip()
    if env_sid:
        return env_sid
    if root is None:
        root = resolve_root()
    # Prune order matters: a stale binding must NOT count as the current
    # session, so stale bindings are pruned BEFORE resolution — but the current
    # sid is only known after resolution. Therefore non-binding kinds are
    # pruned AFTER the sid resolves, passing it as current_sid so the current
    # session's own focus survives even when resumed after 14+ days (no fresh
    # binding yet). Fix verified 2026-09-25 (Smith BLOCK, S4 hand-back).
    prune_session_artifacts(root, kinds={"binding"})
    paths = _session_binding_paths(root)
    resolved = None
    if not paths:
        resolved = _marker_session_id(root)
    elif len(paths) == 1:
        binding = read_binding(paths[0])
        candidate = binding.get("session_id") if binding else None
        if candidate and _binding_fresh(binding):
            resolved = candidate
    prune_session_artifacts(root, current_sid=resolved, kinds=SESSION_ARTIFACT_NON_BINDING_KINDS)
    return resolved


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


def has_mutating_work(entries, root):
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


def ledger_append(root, event, subject, detail, session_id=None):
    """Append one event line to the Link ledger (brain/state/activity.log).

    Kernel-side append mirroring the `matrix link` line format so
    ledger_tail_events and `matrix link --validate` parse it. Hooks must use
    this helper (or `bin/matrix link`) to touch the ledger — never write
    activity.log by hand. Returns True on success, False on OSError.
    """
    detail = re.sub(r"[\r\n]+", " ", str(detail))
    if session_id and not re.search(r"(^|\s)session_id=\S+\s*$", detail):
        detail = f"{detail} session_id={session_id}"
    line = (
        f"{datetime.datetime.now().astimezone().isoformat(timespec='seconds')}"
        f" | {event:<12} | {subject:<16} | {detail}"
    )
    path = os.path.join(root, "brain", "state", "activity.log")
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        return True
    except OSError:
        return False


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
