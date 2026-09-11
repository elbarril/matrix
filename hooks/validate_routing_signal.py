#!/usr/bin/env python3
"""Seraph · validate_routing_signal — warn when real engineering work in a session
shows no Link evidence of delegation to Trinity/Smith/Architect.

Reads `brain/state/hook-audit.jsonl` for the session and `brain/state/activity.log`
for Link route/handoff entries. Warn-only: always returns `ok: true`. When the
pattern repeats for a 3rd time (2 prior triggers + this one), the escalation is
informational — severity is derived by the consumer, never set by this hook.
A `phase:path-decision` declaration suppresses the signal only when its real
git diff is small; unresolved diffs fail safe.

Input (argv[1] or stdin):
  {"session_id": "..."}   # optional
"""

import fnmatch
import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone

from _common import current_session_id, emit, read_input, resolve_root


AUDIT_LOG = "brain/state/hook-audit.jsonl"
ACTIVITY_LOG = "brain/state/activity.log"
HISTORY_LOG = "brain/state/routing-signal-history.jsonl"

MUTATING_TOOLS = {"write", "edit", "multi_edit"}
RUN_COMMAND_TOOLS = {"exec", "run_command", "run-command"}
EXCLUDED_PREFIXES = ("brain/state/", "brain/output/")
DELEGATION_NAMES = ("trinity", "smith", "architect")
PATH_DECISION_EVENT = "phase:path-decision"
SMALL_PATH_MAX_LINES = 10
SMALL_PATH_MAX_FILES = 1
NEVER_SMALL_PREFIXES = ("hooks/", "bin/lib/", "brain/state/", "adapters/")
NEVER_SMALL_EXACT = ("AGENTS.md", "DEVIN.md", "bin/matrix", "brain/data/lessons.md")
NEVER_SMALL_GLOBS = (
    "brain/agents/*.md",
    "brain/data/lessons/*.md",
    "brain/data/capability-map.md",
    "adapters/*/adapter.yaml",
)
GIT_CALL_TIMEOUT_S = 5
GIT_BUDGET_S = 10.0
MAX_GIT_CALLS = 6

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
# A delegation only counts as verified when it names a real harness check
# (SMITH_CHECK_TOKENS) or references an eval artifact under brain/output/eval.
SMITH_CHECK_TOKENS = ("fidelity_check", "informe_site", "e2e", "smoke")
SMITH_CHECK_RE = re.compile(
    r"\b(" + "|".join(re.escape(t) for t in SMITH_CHECK_TOKENS) + r")\b",
    re.IGNORECASE,
)
EVAL_ARTIFACT_RE = re.compile(r"brain/output/[^\s]*eval|MATRIX:EVAL", re.IGNORECASE)
SESSION_ID_RE = re.compile(r"session_id\s*=\s*([^\s|]+)")


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


def _iter_activity_events(root, start_dt, end_dt):
    """Yield activity lines in the window as (timestamp, rest, original)."""
    if start_dt is None or end_dt is None:
        return
    path = os.path.join(root, ACTIVITY_LOG)
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            ts_str = ""
            if line.startswith("["):
                match = re.match(r"\[([^\]]+)\]\s*(.*)", line)
                if match:
                    ts_str = match.group(1)
                    rest = match.group(2)
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
            if start_dt <= ts <= end_dt:
                yield ts, rest, line


def _line_parts(rest):
    """Return (event, subject, detail) from a window rest string.

    Handles both the ledger format ('event | subject | detail') and the
    bracketed test format ('| event | subject | detail').
    """
    parts = [p.strip() for p in rest.split("|")]
    if parts and parts[0] == "":
        parts = parts[1:]
    event = parts[0] if parts else ""
    subject = parts[1] if len(parts) > 1 else ""
    detail = " | ".join(parts[2:]) if len(parts) > 2 else ""
    return event, subject, detail


def _line_session_id(text):
    """Return the session_id=<sid> value in a line, or None.

    Trailing punctuation is stripped so (session_id=S1) parses as S1.
    """
    m = SESSION_ID_RE.search(text)
    if not m:
        return None
    return m.group(1).rstrip("),;.")


def _detail_subject(detail):
    """Extract 'subject=<x>' from a path-decision detail."""
    m = re.search(r"\bsubject=([^\s|]+)", detail)
    return m.group(1) if m else None


def _activity_in_scope(rest, session_id, project):
    """Return True when an activity line may belong to the audited session.

    A line that carries an explicit session_id= is attributed only on equality
    with the current session and never falls back to the project on a
    mismatch. Project match (or the legacy in-scope default) applies only when
    the line has no session_id.
    """
    line_sid = _line_session_id(rest)
    if line_sid is not None:
        return session_id is not None and line_sid == session_id
    _event, subject, _detail = _line_parts(rest)
    if project:
        return subject == project
    return True


def _path_decision_in_scope(rest, session_id, project):
    """Scope a phase:path-decision line to the session.

    The ledger subject for path decisions is always 'A'; the real project is
    declared in the detail as subject=<x>. An explicit session_id= is
    attributed only on equality and never falls back to the project on a
    mismatch. Legacy sessions without a known project fall back to in-scope.
    """
    line_sid = _line_session_id(rest)
    if line_sid is not None:
        return session_id is not None and line_sid == session_id
    if not project:
        return True
    _event, _subject, detail = _line_parts(rest)
    declared = _detail_subject(detail)
    return declared is not None and declared == project


def _session_project(entries, session_id):
    """Return the non-null project_active recorded for the session, or None."""
    for entry in entries:
        if entry.get("session_id") != session_id:
            continue
        pa = entry.get("project_active")
        if pa:
            return pa
    return None


def _find_delegation_evidence(root, start_dt, end_dt, session_id=None, project=None):
    """Search activity.log for route/handoff entries naming Trinity/Smith/Architect.

    Returns (line, verified): searches ALL in-scope entries in the window and
    prefers a verified one (a real mechanical check token or an eval artifact);
    if none verifies, returns the first matching entry with verified False.
    """
    matches = []
    for _ts, rest, line in _iter_activity_events(root, start_dt, end_dt):
        if ROUTE_HANDOFF_RE.search(rest) and DELEGATION_RE.search(rest):
            if not _activity_in_scope(rest, session_id, project):
                continue
            verified = bool(SMITH_CHECK_RE.search(rest) or EVAL_ARTIFACT_RE.search(rest))
            matches.append((line, verified))
    if not matches:
        return None, False
    for line, verified in matches:
        if verified:
            return line, True
    return matches[0][0], False


def _find_path_decision(root, start_dt, end_dt, session_id=None, project=None):
    """Return the earliest in-scope exact path-decision declaration's ts and ref."""
    earliest = None
    for ts, rest, _line in _iter_activity_events(root, start_dt, end_dt):
        event, _subject, _detail = _line_parts(rest)
        if event != PATH_DECISION_EVENT:
            continue
        if not _path_decision_in_scope(rest, session_id, project):
            continue
        match = re.search(r"\[([^\]]+)\]", rest)
        candidate = (ts, match.group(1) if match else None)
        if earliest is None or ts < earliest[0]:
            earliest = candidate
    return earliest


def _git(repo, args, deadline):
    """Run one read-only git command within the shared call/time budget."""
    if deadline["calls"] >= MAX_GIT_CALLS or time.monotonic() >= deadline["end"]:
        return None
    deadline["calls"] += 1
    env = os.environ.copy()
    env.update({
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_TERMINAL_PROMPT": "0",
        "LC_ALL": "C",
    })
    try:
        result = subprocess.run(
            ["git", "-C", repo] + args,
            shell=False,
            capture_output=True,
            text=True,
            timeout=min(GIT_CALL_TIMEOUT_S, max(0.01, deadline["end"] - time.monotonic())),
            stdin=subprocess.DEVNULL,
            env=env,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout if result.returncode == 0 else None


def _resolve_target_repo(root, paths, deadline):
    absolute = [
        path if os.path.isabs(path) else os.path.join(root, path)
        for path in paths
    ]
    if not absolute:
        return None
    try:
        probe = os.path.commonpath([os.path.dirname(path) for path in absolute])
    except ValueError:
        return None
    top = _git(probe or root, ["rev-parse", "--show-toplevel"], deadline)
    if top is None:
        return None
    values = [line.strip() for line in top.splitlines() if line.strip()]
    if len(values) != 1:
        return None
    repo = os.path.realpath(values[0])
    if any(os.path.commonpath([repo, os.path.realpath(path)]) != repo for path in absolute):
        return None
    worktrees = _git(repo, ["worktree", "list", "--porcelain"], deadline)
    if worktrees is None or sum(1 for line in worktrees.splitlines() if line.startswith("worktree ")) != 1:
        return None
    return repo


def _git_baseline(repo, declared_at, deadline):
    value = _git(repo, ["rev-list", "-1", f"--before={declared_at.isoformat()}", "HEAD"], deadline)
    return value.strip() if value and value.strip() else None


def _diff_counts(repo, baseline, deadline):
    output = _git(repo, ["diff", "--numstat", "--no-renames", baseline, "--"], deadline)
    if output is None:
        return None
    counts = {}
    for line in output.splitlines():
        parts = line.split("\t", 2)
        if len(parts) != 3 or "-" in parts[:2]:
            return None
        try:
            counts[parts[2]] = int(parts[0]) + int(parts[1])
        except ValueError:
            return None
    return counts


def _untracked_counts(repo, deadline):
    output = _git(repo, ["ls-files", "--others", "--exclude-standard"], deadline)
    if output is None:
        return None
    counts = {}
    for rel in output.splitlines():
        if not rel:
            continue
        path = os.path.join(repo, rel)
        try:
            if os.path.getsize(path) > 64 * 1024:
                counts[rel] = 999
                continue
            with open(path, "rb") as fh:
                line_count = sum(1 for _line in fh)
            counts[rel] = 999 if line_count > 200 else line_count
        except OSError:
            return None
    return counts


def _is_never_small(path, repo, root):
    if os.path.realpath(repo) != os.path.realpath(root):
        return False
    normalized = path.replace(os.sep, "/")
    return (
        normalized in NEVER_SMALL_EXACT
        or normalized.startswith(NEVER_SMALL_PREFIXES)
        or any(fnmatch.fnmatchcase(normalized, pattern) for pattern in NEVER_SMALL_GLOBS)
    )


def _evaluate_small_path(root, paths, start_dt, end_dt, session_id=None, project=None):
    result = {
        "declared": False, "ref": None, "declared_at": None,
        "resolvable": False, "exempt": False, "files": None, "lines": None,
        "never_small": [], "reason": "no_declaration",
    }
    try:
        declaration = _find_path_decision(
            root, start_dt, end_dt, session_id=session_id, project=project
        )
        if not declaration:
            return result
        declared_at, ref = declaration
        result.update(declared=True, ref=ref, declared_at=declared_at.isoformat())
        deadline = {"end": time.monotonic() + GIT_BUDGET_S, "calls": 0}
        repo = _resolve_target_repo(root, paths, deadline)
        if not repo:
            result["reason"] = "not_a_git_repo"
            return result
        baseline = _git_baseline(repo, declared_at, deadline)
        if not baseline:
            result["reason"] = "no_baseline"
            return result
        tracked = _diff_counts(repo, baseline, deadline)
        untracked = _untracked_counts(repo, deadline)
        if tracked is None or untracked is None:
            result["reason"] = "git_unresolved"
            return result
        counts = dict(tracked)
        counts.update(untracked)
        if not counts:
            result["reason"] = "empty_diff"
            return result
        files = len(counts)
        lines = sum(counts.values())
        never_small = sorted(path for path in counts if _is_never_small(path, repo, root))
        result.update(resolvable=True, files=files, lines=lines, never_small=never_small)
        if never_small:
            result["reason"] = f"never_small:{never_small[0]}"
        elif files > SMALL_PATH_MAX_FILES:
            result["reason"] = "files_exceeded"
        elif lines > SMALL_PATH_MAX_LINES:
            result["reason"] = "lines_exceeded"
        else:
            result.update(exempt=True, reason="within_tops")
        return result
    except Exception:
        result["reason"] = "evaluation_error"
        result["resolvable"] = False
        result["exempt"] = False
        return result


def _last_state_by_session(path):
    """Return {session_id: last_record} from the append-only history (last wins)."""
    by_session = {}
    if not os.path.isfile(path):
        return by_session
    for record in _read_jsonl(path):
        sid = record.get("session_id")
        if not sid:
            continue
        by_session[sid] = record
    return by_session


def count_unresolved_sessions(path, exclude_session_id=None):
    """Count sessions whose last history record is an unresolved trigger.

    Same coherent count used by validate_phase_close's escalation warn: last
    state per session wins; the current session is excluded. Returns
    (count, [session_ids]).
    """
    count = 0
    unresolved = []
    for sid, record in _last_state_by_session(path).items():
        if exclude_session_id is not None and sid == exclude_session_id:
            continue
        if record.get("triggered"):
            count += 1
            unresolved.append(sid)
    return count, unresolved


def _last_record_for_session(path, session_id):
    """Return the most recent record for a session, or None."""
    last = None
    if not os.path.isfile(path):
        return last
    for record in _read_jsonl(path):
        if record.get("session_id") == session_id:
            last = record
    return last


def _record_outcome(path, session_id, triggered, resolved, small_path, persist_history=True):
    """Append one compact outcome record when the session's state transitions.

    History is append-only: the last record for a session wins when counting.
    A record is written only when (triggered, resolved) differs from the
    session's previous record, so repeated runs never duplicate the same state.
    persist_history=False disables all writes.
    """
    if not persist_history:
        return
    last = _last_record_for_session(path, session_id)
    state = (bool(triggered), resolved)
    if last is not None and (bool(last.get("triggered")), last.get("resolved")) == state:
        return
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "triggered": triggered,
        "resolved": resolved,
        "small_path": small_path,
    }
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass


def validate(data, persist_history=True):
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
    threshold_triggered = triggered
    resolved = None
    small_path = None

    delegation_evidence = None
    unverified_delegation = False
    project = _session_project(entries, session_id)
    if triggered:
        delegation_evidence, delegation_verified = _find_delegation_evidence(
            root, start_dt, end_dt, session_id=session_id, project=project
        )
        if delegation_evidence and delegation_verified:
            triggered = False
            resolved = "delegated"
        elif delegation_evidence:
            unverified_delegation = True

    if triggered:
        small_path = _evaluate_small_path(
            root, mutating_paths, start_dt, end_dt, session_id=session_id, project=project
        )
        if small_path["exempt"]:
            triggered = False
            resolved = "exempted"
        elif small_path["declared"] and not small_path["resolvable"]:
            resolved = "unknown"
        else:
            resolved = "triggered"

    history_path = os.path.join(root, HISTORY_LOG)
    prior, _ = count_unresolved_sessions(history_path, exclude_session_id=session_id)
    if threshold_triggered:
        _record_outcome(
            history_path, session_id, triggered, resolved, small_path,
            persist_history=persist_history,
        )

    message = None
    if triggered:
        reason = small_path["reason"] if small_path else "no_declaration"
        detail = reason
        if reason == "lines_exceeded":
            detail = f"lines={small_path['lines']}>{SMALL_PATH_MAX_LINES}"
        elif reason == "files_exceeded":
            detail = f"files={small_path['files']}>{SMALL_PATH_MAX_FILES}"
        elif resolved == "unknown":
            detail = f"unresolved:{reason.replace('_', '-')}"
        if unverified_delegation:
            message = (
                f"Session {session_id} did real engineering work "
                f"({len(mutating_paths)} file(s) edited, run_command={run_command_seen}) "
                f"but the Link route/handoff names Trinity/Smith/Architect without a "
                f"verified mechanical check or eval artifact (delegación sin check verificado)."
            )
        else:
            message = (
                f"Session {session_id} did real engineering work "
                f"({len(mutating_paths)} file(s) edited, run_command={run_command_seen}) "
                f"but no Link route/handoff to Trinity/Smith/Architect was found in the session window."
            )
        if reason != "no_declaration":
            message = message[:-1] + f"; {detail}."

    return {
        "hook": "validate_routing_signal",
        "ok": True,
        "session_id": session_id,
        "triggered": triggered,
        "resolved": resolved,
        "small_path": small_path,
        "window": {
            "start": start_dt.isoformat() if start_dt else None,
            "end": end_dt.isoformat() if end_dt else None,
        },
        "mutating_paths": sorted(mutating_paths),
        "run_command_seen": run_command_seen,
        "delegation_evidence": delegation_evidence,
        "unverified_delegation": unverified_delegation,
        "historical_triggers": prior,
        "message": message,
    }


def main():
    emit(validate(read_input()))


if __name__ == "__main__":
    main()
