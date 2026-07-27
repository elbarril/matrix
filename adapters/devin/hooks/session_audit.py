#!/usr/bin/env python3
"""Devin CLI hook translator — Layer 3 adapter for Matrix audit_event.

Reads a Devin lifecycle-event JSON from stdin, extracts only metadata, runs
pre_activation_check on session_start, and forwards a generic envelope to the
Layer 1 portable hook hooks/audit_event.py via bin/matrix.
"""
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


def _load_activation_block(root):
    """Extract the <activation> block from neo.md as plain text."""
    path = os.path.join(root, "brain", "agents", "neo.md")
    if not os.path.isfile(path):
        return ""
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    m = re.search(r"<activation>(.*?)</activation>", text, re.DOTALL)
    return m.group(1).strip() if m else ""


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

        if tool_name == "skill":
            try:
                origin = classify_skill_origin(tool_input, tool_response)
                envelope["invoked_artifact"] = tool_input.get("skill")
                envelope["invoked_origin"] = origin
            except Exception:
                pass

    _call_audit_event(envelope)

    if event == "session_end":
        _run_session_close(session_id)

    # Etapa G / H3 experiment: optionally inject the neo.md <activation>
    # block into SessionStart / UserPromptSubmit via hookSpecificOutput.
    if _activation_inject_enabled() and event in ("session_start", "user_prompt_submit"):
        block = _load_activation_block(ROOT)
        if block:
            print(
                json.dumps(
                    {
                        "hookSpecificOutput": {
                            "hookEventName": event_name,
                            "additionalContext": block,
                        }
                    },
                    ensure_ascii=False,
                )
            )

    # Never block the user's Devin session; this is ground-truth logging only.
    sys.exit(0)


if __name__ == "__main__":
    main()
