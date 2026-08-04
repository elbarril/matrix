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

ROOT = common.resolve_root()
BIN_MATRIX = os.path.join(ROOT, "bin", "matrix")

DEVIN_EVENT_MAP = {
    "SessionStart": "session_start",
    "UserPromptSubmit": "user_prompt_submit",
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

# B3: nudge after this many mutating operations without a phase_close.
MUTANT_WORK_THRESHOLD = 16
MUTANT_WORK_TOOLS = {"write", "edit", "multi_edit", "run_command", "run-command", "exec"}


def _load_context(root):
    """Parse the simple top-level .context.yaml without external deps."""
    path = os.path.join(root, ".context.yaml")
    values = {}
    if not os.path.isfile(path):
        return values
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.split("#", 1)[0]
            m = re.match(r"^\s*([A-Za-z0-9_]+)\s*:\s*(.*)\s*$", line)
            if not m:
                continue
            key, raw = m.groups()
            raw = raw.strip()
            if raw in ("null", "~", "None", ""):
                values[key] = None
            elif len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ('"', "'"):
                values[key] = raw[1:-1]
            else:
                values[key] = raw
    return values


def _parse_scalar(raw):
    """Parse a simple YAML scalar value (bool/int/string)."""
    raw = raw.strip()
    if raw in ("true", "True", "yes"):
        return True
    if raw in ("false", "False", "no"):
        return False
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ('"', "'"):
        return raw[1:-1]
    if raw in ("null", "~", "None", ""):
        return None
    return raw


def _load_adapter_config(root):
    """Load adapters/devin/config.yaml. Prefer PyYAML if present; fall back to
    a minimal line parser so this Layer 3 adapter stays dependency-free."""
    path = os.path.join(root, "adapters", "devin", "config.yaml")
    if not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    # PyYAML is installed in this environment, but we keep a minimal fallback
    # so the adapter does not hard-depend on it in other environments.
    try:
        import yaml
        return yaml.safe_load(text) or {}
    except Exception:
        pass
    data = {}
    section = None
    for line in text.splitlines():
        line = line.split("#", 1)[0]
        if not line.strip():
            continue
        # Top-level section with no inline value, e.g. "experiment:"
        m = re.match(r"^([A-Za-z0-9_]+)\s*:\s*$", line)
        if m:
            section = m.group(1)
            data.setdefault(section, {})
            continue
        # Nested key under current section, e.g. "  activation_inject: false"
        if section:
            m = re.match(r"^\s+([A-Za-z0-9_]+)\s*:\s*(.*)$", line)
            if m:
                data[section][m.group(1)] = _parse_scalar(m.group(2))
    return data


def _activation_inject_enabled():
    """Return True when the Etapa G/H3 experiment is active."""
    env = os.environ.get("MATRIX_INJECT_ACTIVATION")
    if env == "1":
        return True
    if env == "0":
        return False
    cfg = _load_adapter_config(ROOT)
    return bool(cfg.get("experiment", {}).get("activation_inject", False))


def _is_workspace_mode(root):
    """True when this session's cwd is the Matrix root itself (AGENTS.md §6
    step 0: "Matrix workspace mode", no external project bound). Devin runs
    hook commands as a child process of the session, so os.getcwd() here is
    the session's own cwd, not this script's location — confirmed live
    (2026-07-28) by a temporary debug spike that logged os.getcwd() during a
    real `devin -p` run started with cwd at the Matrix root.
    """
    cwd = os.path.abspath(os.getcwd())
    root = os.path.abspath(root)
    return cwd == root or cwd.startswith(root + os.sep)


def _activation_reinject_scope():
    """Return True when this session's cwd is either Matrix workspace mode or a
    real bound project (valid `_brain` symlink to this root + AGENTS.local.md
    managed block) — the two cases where per-turn activation reinjection should
    fire (B1-Option 1, matrix-system-health-audit.md).

    Reuses `bin/matrix scope`, a thin wrapper around resolve_scope() — the
    single existing "where am I?" resolver (innermost-root-wins walk from cwd)
    already used by show_status/checkpoints/ledger. This intentionally calls
    into bash instead of re-implementing the walk-up + `_brain`/AGENTS.local.md
    validity check in Python: that logic already has one bash owner
    (resolve_scope/path_is_bound in bin/matrix) and a documented no-duplicate
    rule (see resolve_bound_target()'s docstring in hooks/_common.py) — adding
    a second, divergence-prone copy here would violate it. Falls back to
    workspace-only behavior (the old, narrower condition) if the subprocess
    call fails for any reason, so a broken `bin/matrix` never widens injection
    beyond what was already proven safe.
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
        # "bound-unregistered" is still a real, working binding (valid _brain +
        # managed AGENTS.local.md) — see resolve_scope()'s own comment in
        # bin/matrix; only "broken" and "none" (and any unexpected output)
        # must NOT reinject.
        return mode in ("workspace", "bound", "bound-unregistered")
    except Exception as e:
        print(f"[session_audit] scope resolution failed: {e}", file=sys.stderr)
        return _is_workspace_mode(ROOT)


def _render_activation_preamble(root):
    """Render brain/data/activation-preamble.tmpl — the single source of truth
    also used by the generated neo SKILL.md and by AGENTS.local.md's bound-project
    block (see bin/matrix matrix_block_tmp()). Reusing it here means workspace-mode
    injection, the Neo skill, and bound-project binding all carry one wording."""
    tmpl_path = os.path.join(root, "brain", "data", "activation-preamble.tmpl")
    if not os.path.isfile(tmpl_path):
        return ""
    with open(tmpl_path, encoding="utf-8") as fh:
        text = fh.read()
    contract_path = os.path.join(root, "AGENTS.md")
    neo_path = os.path.join(root, "brain", "agents", "neo.md")
    text = text.replace("{{CONTRACT_PATH}}", contract_path).replace("{{NEO_AGENT_PATH}}", neo_path)
    return text.strip()


SESSION_MARKER = os.path.join("brain", "state", ".current-hook-session")


def _session_id_from_devin(payload, ctx):
    """Devin may provide a real session id in newer CLI versions."""
    for k in SESSION_ID_KEYS:
        v = payload.get(k)
        if v:
            return v
    return ctx.get("session_id")


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


def _session_id(root, event, payload, ctx):
    sid = _session_id_from_devin(payload, ctx)
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
    try:
        env = {**os.environ, "MATRIX_ROOT": ROOT}
        proc = subprocess.run(
            [BIN_MATRIX, "hooks", "pre_activation_check"],
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
        return bool(result.get("ok"))
    except Exception as e:
        print(f"[session_audit] pre_activation_check failed: {e}", file=sys.stderr)
        return False


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
    """Count post_tool_use audit entries for this session."""
    path = os.path.join(root, "brain", "state", "hook-audit.jsonl")
    if not os.path.isfile(path):
        return 0
    count = 0
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if entry.get("session_id") == session_id and entry.get("event") == "post_tool_use":
                count += 1
    return count


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

    ctx = _load_context(ROOT)
    session_id = _session_id(ROOT, event, payload, ctx)
    project_active = ctx.get("active_project")

    pre_ok = None
    if event == "session_start":
        pre_ok = _run_pre_activation_check()
        orphan_session_id = _run_detect_orphan_session(project_active)
        if orphan_session_id:
            _run_session_close_async(orphan_session_id)

    envelope = {
        "event": event,
        "session_id": session_id,
        "project_active": project_active,
        "pre_activation_check_ok": pre_ok,
    }

    if event == "post_tool_use":
        tool_name = payload.get("tool_name")
        tool_input = payload.get("tool_input", {})
        tool_response = payload.get("tool_response", {})
        envelope["tool_name"] = tool_name
        envelope["tool_paths"] = _extract_tool_paths(tool_name, tool_input)

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

    # Build hookSpecificOutput.additionalContext. B1 (activation reinjection) and
    # B3 (phase_close nudge) are independent mechanisms but share this channel.
    # When both fire in the same turn their texts are concatenated with a blank
    # line; neither suppresses the other. This keeps B3 usable even if the
    # activation_inject experiment is later disabled.
    contexts = []

    # B1: reinject activation preamble on session_start / user_prompt_submit.
    if _activation_inject_enabled() and _activation_reinject_scope() and event in ("session_start", "user_prompt_submit"):
        preamble = _render_activation_preamble(ROOT)
        if preamble:
            contexts.append(preamble)

    # B3: nudge when mutating work since the last phase_close exceeds threshold.
    if event == "user_prompt_submit" and session_id:
        nudge = _b3_nudge_text(ROOT, session_id)
        if nudge:
            contexts.append(nudge)

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
