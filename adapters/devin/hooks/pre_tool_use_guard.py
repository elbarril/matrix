#!/usr/bin/env python3
"""Devin CLI hook translator — Layer 3 adapter for Matrix pre_exec_guard.

Reads a Devin PreToolUse event from stdin, forwards a minimal envelope to the
Layer 1 portable hook hooks/pre_exec_guard.py via bin/matrix, and translates
the result into Devin's blocking decision contract.

Devin contract (overview.mdx "Exit Codes"):
- exit 0  → allow the tool call
- exit 2  → block the tool call
- stdout must be JSON: {"decision": "block" | "allow", "reason": "..."}
"""
import json
import os
import subprocess
import sys

_candidate = os.path.dirname(os.path.abspath(__file__))
for _ in range(3):
    _candidate = os.path.dirname(_candidate)
sys.path.insert(0, os.path.join(_candidate, "hooks"))
import _common as common  # noqa: E402

ROOT = common.resolve_root()
BIN_MATRIX = os.path.join(ROOT, "bin", "matrix")


def _read_stdin_json():
    raw = ""
    if not sys.stdin.isatty():
        try:
            raw = sys.stdin.read()
        except Exception:
            raw = ""
    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"[pre_tool_use_guard] invalid JSON on stdin: {exc}", file=sys.stderr)
        return {}


def _audit_decision(session_id, tool_name, decision, reason):
    """Persist the guard's allow/block decision to the shared audit log.

    Redaction contract (never violate): only `guard_decision` ("allow"/
    "block") and `guard_reason` are recorded. `guard_reason` must already be
    limited to a fixed verb + relative path from the public protected-paths
    list (see hooks/pre_exec_guard.py) or the literal "guard invocation
    failed" — never the raw command, tool_input, or exception text. This
    call is best-effort: a failure to audit must never block or alter the
    guard's decision.
    """
    envelope = {
        "event": "pre_tool_use_guard_decision",
        "session_id": session_id,
        "tool_name": tool_name,
        "guard_decision": decision,
        "guard_reason": reason,
    }
    try:
        subprocess.run(
            [BIN_MATRIX, "hooks", "audit_event", json.dumps(envelope)],
            env={**os.environ, "MATRIX_ROOT": ROOT},
            capture_output=True,
            text=True,
            timeout=10,
            stdin=subprocess.DEVNULL,
        )
    except Exception:
        pass


def main():
    payload = _read_stdin_json()
    tool_name = payload.get("tool_name")
    tool_input = payload.get("tool_input")
    session_id = payload.get("session_id")
    if not isinstance(tool_input, dict):
        tool_input = {}

    # Only shell-like tools are in scope for this guard.
    if tool_name not in {"exec", "run_command", "run-command"}:
        print(json.dumps({"decision": "allow"}, ensure_ascii=False))
        sys.exit(0)

    envelope = {
        "tool_name": tool_name,
        "tool_input": tool_input,
        "session_id": session_id,
    }

    try:
        proc = subprocess.run(
            [BIN_MATRIX, "hooks", "pre_exec_guard", json.dumps(envelope)],
            env={**os.environ, "MATRIX_ROOT": ROOT},
            capture_output=True,
            text=True,
            timeout=10,
            stdin=subprocess.DEVNULL,
        )
    except Exception:
        # Fail-open is unsafe for a guard; fail-closed so misconfiguration is
        # obvious. Never log the exception text — literal reason only.
        reason = "guard invocation failed"
        _audit_decision(session_id, tool_name, "block", reason)
        print(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False))
        sys.exit(2)

    result = {}
    if proc.stdout:
        try:
            result = json.loads(proc.stdout)
        except json.JSONDecodeError:
            print(f"[pre_tool_use_guard] non-JSON guard output: {proc.stdout}", file=sys.stderr)

    if result.get("ok"):
        _audit_decision(session_id, tool_name, "allow", None)
        print(json.dumps({"decision": "allow"}, ensure_ascii=False))
        sys.exit(0)

    reason = result.get("reason") or "blocked by pre_exec_guard"
    _audit_decision(session_id, tool_name, "block", reason)
    print(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False))
    sys.exit(2)


if __name__ == "__main__":
    main()
