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


def main():
    payload = _read_stdin_json()
    tool_name = payload.get("tool_name")
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        tool_input = {}

    # Only shell-like tools are in scope for this guard.
    if tool_name not in {"exec", "run_command", "run-command"}:
        print(json.dumps({"decision": "allow"}, ensure_ascii=False))
        sys.exit(0)

    envelope = {
        "tool_name": tool_name,
        "tool_input": tool_input,
        "session_id": payload.get("session_id"),
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
    except Exception as exc:
        print(f"[pre_tool_use_guard] failed to invoke pre_exec_guard: {exc}", file=sys.stderr)
        # Fail-open is unsafe for a guard; fail-closed so misconfiguration is obvious.
        print(json.dumps({"decision": "block", "reason": f"guard invocation failed: {exc}"}, ensure_ascii=False))
        sys.exit(2)

    result = {}
    if proc.stdout:
        try:
            result = json.loads(proc.stdout)
        except json.JSONDecodeError:
            print(f"[pre_tool_use_guard] non-JSON guard output: {proc.stdout}", file=sys.stderr)

    if result.get("ok"):
        print(json.dumps({"decision": "allow"}, ensure_ascii=False))
        sys.exit(0)

    reason = result.get("reason") or "blocked by pre_exec_guard"
    print(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False))
    sys.exit(2)


if __name__ == "__main__":
    main()
