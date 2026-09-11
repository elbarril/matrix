#!/usr/bin/env python3
"""Devin CLI hook translator — Layer 3 adapter for Matrix audit_event.

Reads a Devin lifecycle-event JSON from stdin, extracts only metadata, runs
pre_activation_check on session_start, and forwards a generic envelope to the
Layer 1 portable hook hooks/audit_event.py via bin/matrix.
"""
import datetime
import json
import os
import re
import subprocess
import sys
import uuid


# We need the Matrix root to locate the Layer 1 helper. Compute a candidate from
# this script's location (adapters/devin/hooks -> root), then reuse the helper's
# resolve_root() so the same logic (MATRIX_ROOT env, traversal) is used everywhere.
_candidate = os.path.dirname(os.path.abspath(__file__))
for _ in range(3):
    _candidate = os.path.dirname(_candidate)
sys.path.insert(0, os.path.join(_candidate, "hooks"))
import _common as common  # noqa: E402
import _flags  # noqa: E402
import _writer_lane as lane  # noqa: E402
from post_run_audit import _write_targets, ALLOWED_MUTANT_PREFIX  # noqa: E402

ROOT = common.resolve_root()
BIN_MATRIX = os.path.join(ROOT, "bin", "matrix")

DEVIN_EVENT_MAP = {
    "SessionStart": "session_start",
    "UserPromptSubmit": "user_prompt_submit",
    "PreToolUse": "pre_tool_use",
    "PostToolUse": "post_tool_use",
    "PostCompaction": "post_compaction",
    "SessionEnd": "session_end",
}
SESSION_ID_KEYS = ("session_id", "sessionId", "session")
# Real Devin tool names (confirmed from a live session's native logs on
# 2026-07-17 — "read", not "read_file"; "write" added for the same reason:
# knowing WHICH files Neo reads/writes is structural metadata, not content.
STRUCTURAL_TOOLS = {"read", "edit", "multi_edit", "write"}

# B2: run validate_routing_signal every N post_tool_use events for a session.
ROUTING_SIGNAL_INTERVAL = 20
USERPROMPT_FULL_REINJECT_INTERVAL = 10

# B3: nudge after this many mutating operations without a phase_close.
MUTANT_WORK_THRESHOLD = 16
MUTANT_WORK_TOOLS = {"write", "edit", "multi_edit", "run_command", "run-command", "exec"}


def _flag_value(name):
    """Effective boolean of a feature flag via hooks/_flags.py (best-effort).

    On loader failure, fall back to the flag's declared default — security
    gates with default on (gate.shared_surface, gate.writer_lane,
    gate.pre_exec_guard) must never fail open silently.
    """
    try:
        return bool(_flags.get_flag(name)["value"])
    except Exception:
        return bool(_flags.DEFAULTS.get(name, False))


def _scope_project():
    """Return the project scope for this session's cwd via `bin/matrix scope`.

    Delegates to resolve_scope() — the single bash owner of the "where am I?"
    walk-up — instead of re-implementing it in Python (same no-duplicate rule
    as _activation_reinject_scope). Returns field 2 of the printed line
    (workspace→matrix, project→<name>, none→empty, normalized to None).
    """
    try:
        proc = subprocess.run(
            [BIN_MATRIX, "scope"],
            env={**os.environ, "MATRIX_ROOT": ROOT},
            capture_output=True,
            text=True,
            timeout=10,
            stdin=subprocess.DEVNULL,
        )
        line = (proc.stdout or "").splitlines()[0] if proc.stdout else ""
        fields = line.split("\t")
        if len(fields) < 2:
            return None
        value = fields[1].strip()
        return value or None
    except Exception as e:
        print(f"[session_audit] scope project resolution failed: {e}", file=sys.stderr)
        return None


def _activation_inject_enabled():
    """Flag activation.reinject gates the per-turn reinjection channel (B1)."""
    return _flag_value("activation.reinject")


def _activation_inject_userprompt_full():
    """Flag activation.reinject_full gates full-preamble reinjection on every
    user prompt (vs. session_start + sentinel)."""
    return _flag_value("activation.reinject_full")


def _is_workspace_mode(root):
    """True when this session's cwd is the Matrix root itself (AGENTS.md §6
    step 0: "Matrix workspace mode", no external project in scope). Devin runs
    hook commands as a child process of the session, so os.getcwd() here is
    the session's own cwd, not this script's location — confirmed live
    (2026-07-28) by a temporary debug spike that logged os.getcwd() during a
    real `devin -p` run started with cwd at the Matrix root.
    """
    cwd = os.path.abspath(os.getcwd())
    root = os.path.abspath(root)
    return cwd == root or cwd.startswith(root + os.sep)


def _activation_reinject_scope():
    """Return True when this session's cwd is either Matrix workspace mode or
    a registry-resolved project — the two cases where per-turn activation
    reinjection should fire (B1). There is no filesystem binding anymore; the
    mode comes from `bin/matrix scope` (registry-path walk-up).

    This intentionally calls into bash instead of re-implementing the walk-up
    in Python: that logic already has one bash owner (resolve_scope in
    bin/matrix). Falls back to workspace-only behavior (the old, narrower
    condition) if the subprocess call fails for any reason, so a broken
    `bin/matrix` never widens injection beyond what was already proven safe.
    """
    try:
        proc = subprocess.run(
            [BIN_MATRIX, "scope"],
            env={**os.environ, "MATRIX_ROOT": ROOT},
            capture_output=True,
            text=True,
            timeout=10,
            stdin=subprocess.DEVNULL,
        )
        line = (proc.stdout or "").splitlines()[0] if proc.stdout else ""
        mode = line.split("\t", 1)[0].strip()
        return mode in ("workspace", "project")
    except Exception as e:
        print(f"[session_audit] scope resolution failed: {e}", file=sys.stderr)
        return _is_workspace_mode(ROOT)


def _adapter_doc_path(root):
    """Resolve the current adapter's own reference doc via `bin/matrix
    adapter-doc-path` — delegates to bash instead of re-parsing adapter.yaml
    here, same "one owner" principle as _activation_reinject_scope() delegating
    to `bin/matrix scope`."""
    try:
        proc = subprocess.run(
            [BIN_MATRIX, "adapter-doc-path", "devin"],
            env={**os.environ, "MATRIX_ROOT": root},
            capture_output=True,
            text=True,
            timeout=10,
            stdin=subprocess.DEVNULL,
        )
        out = (proc.stdout or "").strip()
        return out
    except Exception as e:
        print(f"[session_audit] adapter doc path resolution failed: {e}", file=sys.stderr)
        return ""


def _render_activation_preamble(root):
    """Render brain/data/activation-preamble.tmpl — the single source of truth
    also used by the generated neo SKILL.md and by the (optional) legacy
    AGENTS.local.md artifacts. Workspace injection, the Neo skill, and project
    sessions all carry one wording."""
    tmpl_path = os.path.join(root, "brain", "data", "activation-preamble.tmpl")
    if not os.path.isfile(tmpl_path):
        return ""
    with open(tmpl_path, encoding="utf-8") as fh:
        text = fh.read()
    contract_path = os.path.join(root, "AGENTS.md")
    neo_path = os.path.join(root, "brain", "agents", "neo.md")
    adapter_doc_path = _adapter_doc_path(root)
    text = (
        text.replace("{{CONTRACT_PATH}}", contract_path)
        .replace("{{NEO_AGENT_PATH}}", neo_path)
        .replace("{{ADAPTER_DOC_PATH}}", adapter_doc_path)
    )
    return text.strip()


def _render_sentinel_text(session_id, turn):
    next_drift = ((turn // USERPROMPT_FULL_REINJECT_INTERVAL) + 1) * USERPROMPT_FULL_REINJECT_INTERVAL
    return f"Matrix contract active — session {session_id}, turn {turn}. Full activation preamble reinjects at turn {next_drift} or on-demand."


SESSION_MARKER = os.path.join("brain", "state", ".current-hook-session")


def _session_id_from_devin(payload):
    """Devin may provide a real session id in newer CLI versions."""
    for k in SESSION_ID_KEYS:
        v = payload.get(k)
        if v:
            return v
    return None


def _persist_session_marker(root, sid):
    """Persist sid to the shared marker so bin/matrix can correlate."""
    marker = os.path.join(root, SESSION_MARKER)
    try:
        os.makedirs(os.path.dirname(marker), exist_ok=True)
        with open(marker, "w", encoding="utf-8") as fh:
            fh.write(sid)
    except OSError:
        pass


def _synthetic_session_id(root, event):
    """Generate/read a synthetic session id, since Devin provides none.

    `session_start` mints a fresh id and persists it to a marker file;
    every other event in the same Devin process reads that same marker via
    _common.current_session_id() so the read path is centralized in Layer 1.
    This only disambiguates sessions run sequentially on one machine — two
    Devin processes writing to the same MATRIX_ROOT concurrently can still
    interleave, but that is a real platform gap, not something a Layer 3
    adapter can fully solve without Devin's cooperation.
    """
    if event == "session_start":
        sid = uuid.uuid4().hex[:12]
        _persist_session_marker(root, sid)
        return sid
    return common.current_session_id(root)


def _session_id(root, event, payload):
    sid = _session_id_from_devin(payload)
    if sid:
        if event == "session_start":
            _persist_session_marker(root, sid)
        return sid
    return _synthetic_session_id(root, event)


def _extract_tool_paths(tool_name, tool_input):
    """For structural file tools, extract the path(s) they touched."""
    if tool_name not in STRUCTURAL_TOOLS:
        return []
    if not isinstance(tool_input, dict):
        return []
    paths = []
    for key in ("file_path", "path", "paths"):
        val = tool_input.get(key)
        if isinstance(val, str):
            paths.append(val)
        elif isinstance(val, list):
            for p in val:
                if isinstance(p, str):
                    paths.append(p)
    # multi_edit may carry a list of per-file edits.
    edits = tool_input.get("edits")
    if tool_name == "multi_edit" and isinstance(edits, list):
        for edit in edits:
            if not isinstance(edit, dict):
                continue
            for key in ("file_path", "path", "paths"):
                val = edit.get(key)
                if isinstance(val, str):
                    paths.append(val)
                elif isinstance(val, list):
                    for p in val:
                        if isinstance(p, str):
                            paths.append(p)
    return paths


SKILL_ORIGIN_RE = re.compile(r"(?:Source|Base directory):\s*(.+?)(?:\n|$)", re.IGNORECASE | re.MULTILINE)


def _generated_skill_names(root):
    """Return the set of skill names generated by the last build, or None if the
    generated directory does not exist."""
    gen_dir = os.path.join(root, "adapters", "devin", "generated", ".agents", "skills")
    if not os.path.isdir(gen_dir):
        return None
    try:
        return set(name for name in os.listdir(gen_dir) if os.path.isdir(os.path.join(gen_dir, name)))
    except OSError:
        return None


def classify_skill_origin(tool_input, tool_response):
    """Classify where a invoked skill came from without leaking its content.

    Only `tool_input.get("skill")` and a short origin string are returned.
    The full `tool_response` content is parsed once to extract a Source/Base
    directory path, then discarded.
    """
    output = ""
    if isinstance(tool_response, dict):
        output = tool_response.get("output") or ""
    if not isinstance(output, str):
        output = str(output)
    m = SKILL_ORIGIN_RE.search(output)
    if not m:
        return "unknown"
    path = m.group(1).strip()

    if os.path.islink(path):
        try:
            target = os.readlink(path)
        except OSError:
            return "unknown"
        if target.startswith("/opt/"):
            return "system-pkg"
        return "external"

    if not os.path.exists(path):
        return "unknown"

    generated = _generated_skill_names(ROOT)
    if generated is None:
        return "local"

    skill_name = tool_input.get("skill") if isinstance(tool_input, dict) else None
    if skill_name and skill_name in generated:
        return "matrix"
    return "local"


def _run_pre_activation_check():
    """Run pre_activation_check and return {ok, status, payload}.

    status is one of ok|failed|timeout|error and is stored in the audit envelope
    without changing the boolean ok semantics of the hook.
    """
    try:
        env = {**os.environ, "MATRIX_ROOT": ROOT}
        proc = subprocess.run(
            [BIN_MATRIX, "hooks", "pre_activation_check"],
            env=env,
            capture_output=True,
            text=True,
            timeout=20,
            stdin=subprocess.DEVNULL,
        )
        result = {}
        if proc.stdout:
            try:
                result = json.loads(proc.stdout)
            except ValueError:
                pass
        ok = bool(result.get("ok"))
        status = "ok" if ok else "failed"
        return {"ok": ok, "status": status, "payload": result}
    except subprocess.TimeoutExpired as exc:
        print(f"[session_audit] pre_activation_check timed out: {exc}", file=sys.stderr)
        return {"ok": False, "status": "timeout", "payload": {}}
    except Exception as e:
        print(f"[session_audit] pre_activation_check failed: {e}", file=sys.stderr)
        return {"ok": False, "status": "error", "payload": {}}


def _run_detect_orphan_session(project_active):
    """Best-effort orphan detection: returns an orphan session_id or None."""
    try:
        env = {**os.environ, "MATRIX_ROOT": ROOT}
        proc = subprocess.run(
            [
                BIN_MATRIX,
                "hooks",
                "detect_orphan_session",
                json.dumps({"project_active": project_active}),
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
            stdin=subprocess.DEVNULL,
        )
        result = {}
        if proc.stdout:
            try:
                result = json.loads(proc.stdout)
            except ValueError:
                pass
        return result.get("orphan_session_id")
    except Exception as e:
        print(f"[session_audit] detect_orphan_session failed: {e}", file=sys.stderr)
        return None


def _call_audit_event(envelope):
    try:
        env = {**os.environ, "MATRIX_ROOT": ROOT}
        proc = subprocess.run(
            [BIN_MATRIX, "hooks", "audit_event", json.dumps(envelope)],
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
            stdin=subprocess.DEVNULL,
        )
        if proc.returncode != 0:
            print(
                f"[session_audit] audit_event exited {proc.returncode}: {proc.stderr}",
                file=sys.stderr,
            )
        return proc.stdout
    except Exception as e:
        print(f"[session_audit] audit_event invocation failed: {e}", file=sys.stderr)
        return ""


def _run_session_close(session_id):
    """Best-effort session close: must never block or fail the Devin session."""
    try:
        close_payload = {"session_id": session_id} if session_id else {}
        env = {**os.environ, "MATRIX_ROOT": ROOT}
        proc = subprocess.run(
            [BIN_MATRIX, "session", "close", json.dumps(close_payload)],
            env=env,
            capture_output=True,
            text=True,
            timeout=25,
            stdin=subprocess.DEVNULL,
        )
        if proc.returncode != 0:
            print(
                f"[session_audit] session close exited {proc.returncode}: {proc.stderr}",
                file=sys.stderr,
            )
    except Exception as e:
        print(f"[session_audit] session close invocation failed: {e}", file=sys.stderr)


def _release_session_lanes(session_id):
    """Best-effort backstop: release every writer lane held by this session."""
    if not session_id:
        return
    try:
        for path in lane.lanes_for_session(ROOT, session_id):
            try:
                os.remove(path)
            except OSError:
                pass
    except Exception:
        pass


def _run_session_close_async(session_id):
    """Fire-and-forget close for an orphan session; never blocks the current session.

    The session_close chain can run several subprocesses with long timeouts, so
    orphan recovery is intentionally asynchronous. The detect_orphan_session hook
    writes a synchronous deduplication marker before we get here, preventing
    redundant closes during crash-loop bursts.
    """
    try:
        close_payload = {"session_id": session_id} if session_id else {}
        env = {**os.environ, "MATRIX_ROOT": ROOT}
        subprocess.Popen(
            [BIN_MATRIX, "session", "close", json.dumps(close_payload)],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )
    except Exception as e:
        print(
            f"[session_audit] async orphan session close failed: {e}",
            file=sys.stderr,
        )


def _run_validate_routing_signal(session_id):
    """Best-effort routing signal validation; never blocks the session."""
    try:
        env = {**os.environ, "MATRIX_ROOT": ROOT}
        proc = subprocess.run(
            [BIN_MATRIX, "hooks", "validate_routing_signal", json.dumps({"session_id": session_id})],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            stdin=subprocess.DEVNULL,
        )
        result = {}
        if proc.stdout:
            try:
                result = json.loads(proc.stdout)
            except ValueError:
                pass
        return result
    except Exception as e:
        print(f"[session_audit] validate_routing_signal failed: {e}", file=sys.stderr)
        return None


def _post_tool_use_count(root, session_id):
    """Read the audit-owned O(1) counter, rebuilding once on divergence."""
    state_dir = os.path.join(root, "brain", "state")
    log_path = os.path.join(state_dir, "hook-audit.jsonl")
    counter_path = os.path.join(state_dir, "sessions", f"{session_id}-post-tool-count.json")
    try:
        with open(counter_path, encoding="utf-8") as fh:
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
    print(f"[session_audit] rebuilt divergent counter for session {session_id}", file=sys.stderr)
    try:
        os.makedirs(os.path.dirname(counter_path), exist_ok=True)
        stat = os.stat(log_path)
        tmp = f"{counter_path}.tmp-{os.getpid()}"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"count": count, "log_inode": stat.st_ino, "log_size": stat.st_size}, fh)
        os.replace(tmp, counter_path)
    except OSError:
        pass
    return count


def _user_prompt_submit_count(root, session_id):
    """Advance the audit-owned O(1) user-prompt counter, rebuilding on divergence."""
    state_dir = os.path.join(root, "brain", "state")
    log_path = os.path.join(state_dir, "hook-audit.jsonl")
    counter_path = os.path.join(state_dir, "sessions", f"{session_id}-user-prompt-count.json")
    count = None
    try:
        with open(counter_path, encoding="utf-8") as fh:
            data = json.load(fh)
        stat = os.stat(log_path)
        if data.get("log_inode") == stat.st_ino and data.get("log_size", 0) <= stat.st_size:
            count = int(data.get("count", 0)) + 1
    except (OSError, ValueError, TypeError):
        pass
    if count is None:
        count = 0
        if os.path.isfile(log_path):
            with open(log_path, encoding="utf-8") as fh:
                for line in fh:
                    try:
                        entry = json.loads(line)
                    except ValueError:
                        continue
                    if entry.get("session_id") == session_id and entry.get("event") == "user_prompt_submit":
                        count += 1
        print(f"[session_audit] rebuilt divergent user-prompt counter for session {session_id}", file=sys.stderr)
    try:
        os.makedirs(os.path.dirname(counter_path), exist_ok=True)
        stat = os.stat(log_path)
        tmp = f"{counter_path}.tmp-{os.getpid()}"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"count": count, "log_inode": stat.st_ino, "log_size": stat.st_size}, fh)
        os.replace(tmp, counter_path)
    except OSError:
        pass
    return count


def _drift_full_due(turn):
    """Full preamble reinjection cadence for user_prompt_submit (A-minus)."""
    return turn % USERPROMPT_FULL_REINJECT_INTERVAL == 0


def _parse_iso_ts(ts):
    if not ts:
        return None
    ts = ts.strip()
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    try:
        return datetime.datetime.fromisoformat(ts)
    except ValueError:
        return None


def _mutating_since_phase_close(root, session_id):
    """Return (count, last_phase_close_ts_str) of mutating work since the last
    phase_close (or session_start) for this session.
    """
    path = os.path.join(root, "brain", "state", "hook-audit.jsonl")
    if not os.path.isfile(path):
        return 0, None

    last_phase_close_ts = None
    earliest_session_start_ts = None
    entries = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if entry.get("session_id") != session_id:
                continue
            entries.append(entry)
            ev = entry.get("event")
            if ev in ("phase_close", "phase_close_blocked"):
                last_phase_close_ts = entry.get("timestamp")
            if ev == "session_start":
                ts = _parse_iso_ts(entry.get("timestamp"))
                if ts and (earliest_session_start_ts is None or ts < earliest_session_start_ts):
                    earliest_session_start_ts = ts

    cutoff = _parse_iso_ts(last_phase_close_ts) if last_phase_close_ts else earliest_session_start_ts
    count = 0
    for entry in entries:
        if entry.get("event") != "post_tool_use":
            continue
        if entry.get("tool_name") not in MUTANT_WORK_TOOLS:
            continue
        ts = _parse_iso_ts(entry.get("timestamp"))
        if cutoff and ts and ts <= cutoff:
            continue
        count += 1
    return count, last_phase_close_ts


def _nudge_marker_path(root, session_id):
    return os.path.join(root, "brain", "state", "sessions", f"{session_id}-phase-close-nudge.json")


def _already_nudged_for_window(root, session_id, phase_close_ts):
    """A nudge was already sent for the current phase_close window."""
    path = _nudge_marker_path(root, session_id)
    if not os.path.isfile(path):
        return False
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data.get("phase_close_ts") == phase_close_ts
    except Exception:
        return False


def _record_nudge(root, session_id, phase_close_ts, count):
    path = _nudge_marker_path(root, session_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = {
        "nudged_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "phase_close_ts": phase_close_ts,
        "mutating_count": count,
    }
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False)
    except OSError:
        pass


def _b3_nudge_text(root, session_id):
    """Return a non-blocking phase_close nudge if the threshold is crossed."""
    count, last_phase_close_ts = _mutating_since_phase_close(root, session_id)
    if count < MUTANT_WORK_THRESHOLD:
        return None
    if _already_nudged_for_window(root, session_id, last_phase_close_ts):
        return None
    _record_nudge(root, session_id, last_phase_close_ts, count)
    return (
        f"Reminder: this session has performed {count} mutating operation(s) "
        f"since the last phase_close. Consider running `matrix phase close` "
        "to checkpoint progress before continuing."
    )


def _log_flags_state():
    """Snapshot `link flags:state` once per session when any flag is dangerous
    or inert. Best-effort; never blocks and never leaks values."""
    try:
        flags = _flags.all_flags()
    except Exception:
        return
    dangerous = [n for n, f in flags.items() if f["state"] == "dangerous"]
    inert = [n for n, f in flags.items() if f["state"] == "inert"]
    if not dangerous and not inert:
        return
    detail = ""
    if dangerous:
        detail += "dangerous=" + ",".join(sorted(dangerous))
    if inert:
        if detail:
            detail += " "
        detail += "inert=" + ",".join(sorted(inert))
    try:
        env = {**os.environ, "MATRIX_ROOT": ROOT}
        subprocess.run(
            [BIN_MATRIX, "link", "flags:state", "matrix", detail],
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
            stdin=subprocess.DEVNULL,
        )
    except Exception:
        pass


def _boot_warn_tokens(payload):
    """Extract the closed set of boot_warn tokens from a pre_activation payload."""
    if not isinstance(payload, dict):
        return []
    tokens = (payload.get("boot_warn") or {}).get("warns") or []
    if not isinstance(tokens, list):
        return []
    allowed = {
        "the_source",
        "validate_layer2",
        "validate_lessons",
        "surface_budget",
        "model_drift",
        "ttl_expired",
        "snapshot_due",
    }
    return [t for t in tokens if isinstance(t, str) and t in allowed]


def _render_boot_warn_text(payload):
    """Render boot_warn context for additionalContext: ≤6 lines, each with a repair command."""
    if not isinstance(payload, dict):
        return ""
    details = (payload.get("boot_warn") or {}).get("details") or {}
    if not details:
        return ""
    mapping = {
        "validate_lessons": ("lessons archive needs review", "run `bin/matrix hooks validate_lessons`"),
        "surface_budget": ("a shared-surface doc is over its size budget", "slim AGENTS.md/DEVIN.md/neo.md"),
        "model_drift": ("generated-vs-installed model drift", "run `bin/matrix build --target=devin && bin/matrix install --target=devin`"),
        "ttl_expired": ("a TTL override has expired", "run `bin/matrix link ttl:<name> <subject> until=<new-date>`"),
        "validate_layer2": ("Layer-2 CLI-neutrality drift", "run `bin/matrix hooks validate_layer2`"),
        "the_source": ("SYSTEM_TRUTH/onboarding is stale", "run `bin/matrix hooks the_source`"),
        "snapshot_due": ("metrics snapshot is due", "run the harness-health-report extractor, then `bin/matrix link metrics:snapshot matrix path=<output>`"),
    }
    lines = []
    for token in ["surface_budget", "validate_lessons", "model_drift", "ttl_expired", "validate_layer2", "the_source", "snapshot_due"]:
        if token not in details:
            continue
        label, fix = mapping.get(token, (token, ""))
        detail = details[token]
        extra = ""
        if token == "model_drift" and isinstance(detail, dict) and detail.get("drift"):
            names = [d.get("agent") or d.get("skill") or "?" for d in detail["drift"]]
            extra = f" ({', '.join(names)})"
        elif token == "ttl_expired" and isinstance(detail, dict) and detail.get("expired"):
            events = [f"{e.get('event')}:{e.get('subject')}" for e in detail["expired"]]
            extra = f" ({', '.join(events)})"
        elif token == "snapshot_due" and isinstance(detail, dict):
            extra = f" ({detail.get('real_work_sessions', 0)} sessions, {detail.get('days', 0)} days)"
        lines.append(f"WARN {token}: {label}{extra} — {fix}")
    # Cap to 6 lines/900 bytes.
    lines = lines[:6]
    text = "\n".join(lines)
    if len(text) > 900:
        text = text[:900] + "…"
    return text


def main():
    raw = ""
    if not sys.stdin.isatty():
        try:
            raw = sys.stdin.read()
        except Exception:
            raw = ""
    if not raw.strip():
        return

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[session_audit] invalid JSON on stdin: {e}", file=sys.stderr)
        sys.exit(0)

    event_name = payload.get("hook_event_name")
    if not event_name:
        return

    event = DEVIN_EVENT_MAP.get(event_name)
    if not event:
        # Only the wired Devin events are forwarded; do not log unknown ones.
        return

    session_id = _session_id(ROOT, event, payload)
    project_active = _scope_project()

    pre_result = None
    orphan_session_id = None
    if event == "session_start":
        if _flag_value("hooks.pre_activation_check"):
            pre_result = _run_pre_activation_check()
        else:
            pre_result = {"ok": None, "status": "disabled", "payload": {}}
        orphan_session_id = _run_detect_orphan_session(project_active)
        if orphan_session_id:
            _run_session_close_async(orphan_session_id)
        _log_flags_state()

    envelope = {
        "event": event,
        "session_id": session_id,
        "project_active": project_active,
        "pre_activation_check_ok": pre_result.get("ok") if pre_result else None,
        "pre_activation_check_status": pre_result.get("status") if pre_result else None,
        "boot_warn": _boot_warn_tokens(pre_result.get("payload") if pre_result else {}),
    }

    if event in ("pre_tool_use", "post_tool_use"):
        tool_name = payload.get("tool_name")
        tool_input = payload.get("tool_input", {})
        tool_response = payload.get("tool_response", {})
        envelope["tool_name"] = tool_name
        invocation_id = payload.get("tool_use_id") or payload.get("toolUseId")
        if isinstance(invocation_id, str) and invocation_id.strip():
            envelope["subagent_invocation_id"] = invocation_id
        if event == "post_tool_use":
            envelope["tool_paths"] = _extract_tool_paths(tool_name, tool_input)
            # Release the per-file writer lane for every surface path this
            # edit touched (best-effort; only when holder == session_id).
            if tool_name in {"edit", "write", "multi_edit"}:
                for p in envelope.get("tool_paths") or []:
                    rel = lane.normalize_relpath(ROOT, p)
                    if rel is not None:
                        lane.release(ROOT, rel, session_id)

        # For shell-like tools, parse write targets in memory and only persist
        # argv[0] + first subcommand plus a parsed-target flag. The full command
        # line is never written to the audit log (secret leak surface).
        if tool_name in {"exec", "run_command", "run-command"} and isinstance(tool_input, dict):
            cmd = tool_input.get("command")
            if isinstance(cmd, str):
                if cmd.strip().startswith(ALLOWED_MUTANT_PREFIX):
                    targets, unparsed = [], False
                else:
                    targets, unparsed = _write_targets(cmd, ROOT)
                head = " ".join(cmd.split()[:2])
                existing_paths = envelope.get("tool_paths") or []
                seen = set()
                merged = []
                for p in existing_paths + targets:
                    if isinstance(p, str) and p not in seen:
                        seen.add(p)
                        merged.append(p)
                envelope["tool_paths"] = merged
                envelope["tool_command_head"] = head
                envelope["tool_command_unparsed"] = unparsed

        if tool_name == "run_subagent":
            try:
                if isinstance(tool_input, dict):
                    for key in ("profile", "subagent_type", "agent", "agent_type", "name"):
                        value = tool_input.get(key)
                        if isinstance(value, str) and value.strip():
                            envelope["subagent_profile"] = value
                            break
            except Exception:
                pass

        if tool_name == "skill":
            try:
                origin = classify_skill_origin(tool_input, tool_response)
                envelope["invoked_artifact"] = tool_input.get("skill")
                envelope["invoked_origin"] = origin
            except Exception:
                pass

    _call_audit_event(envelope)

    # B2: periodic routing-signal validation every N post_tool_use events.
    if event == "post_tool_use" and session_id:
        if _post_tool_use_count(ROOT, session_id) % ROUTING_SIGNAL_INTERVAL == 0:
            _run_validate_routing_signal(session_id)

    if event == "session_end":
        _run_session_close(session_id)
        _release_session_lanes(session_id)

    # Build hookSpecificOutput.additionalContext. B1 (activation reinjection) and
    # B3 (phase_close nudge) are independent mechanisms but share this channel.
    # When both fire in the same turn their texts are concatenated with a blank
    # line; neither suppresses the other. This keeps B3 usable even if the
    # activation_inject experiment is later disabled.
    contexts = []

    # B3: nudge when mutating work since the last phase_close exceeds threshold.
    nudge = None
    if event == "user_prompt_submit" and session_id:
        nudge = _b3_nudge_text(ROOT, session_id)

    # B1: reinject activation preamble on session_start / user_prompt_submit.
    if _activation_inject_enabled() and _activation_reinject_scope():
        preamble = ""
        if event == "session_start":
            preamble = _render_activation_preamble(ROOT)
        elif event == "user_prompt_submit" and session_id:
            turn = _user_prompt_submit_count(ROOT, session_id)
            if _activation_inject_userprompt_full() or _drift_full_due(turn):
                preamble = _render_activation_preamble(ROOT)
            else:
                preamble = _render_sentinel_text(session_id, turn)
        if preamble:
            contexts.append(preamble)

    if nudge:
        contexts.append(nudge)

    # D-boot WARN channel: always injected on session_start inside the reinjection scope,
    # regardless of the activation_inject experiment flag.
    if event == "session_start" and pre_result and _activation_reinject_scope():
        warn_text = _render_boot_warn_text(pre_result.get("payload"))
        if warn_text:
            contexts.append(warn_text)

    if contexts:
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": event_name,
                        "additionalContext": "\n\n".join(contexts),
                    }
                },
                ensure_ascii=False,
            )
        )

    # Never block the user's Devin session; this is ground-truth logging only.
    sys.exit(0)


if __name__ == "__main__":
    main()
