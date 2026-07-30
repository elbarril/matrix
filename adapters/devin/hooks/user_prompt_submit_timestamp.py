#!/usr/bin/env python3
"""Devin CLI UserPromptSubmit hook — stamps the turn-start clock for
stop_notify.py's elapsed-time gate. Fires on every user message, on every
Devin CLI session on the machine (Matrix-bound or not) — must be as close
to free as possible for the common (non-Matrix) case.

Same hard invariant as stop_notify.py: never print to stdout, always
exit 0.
"""
import json
import os
import sys
import time

# Resolve the Matrix root the same way session_audit.py / session_end_notify.py do.
_candidate = os.path.dirname(os.path.abspath(__file__))
for _ in range(3):
    _candidate = os.path.dirname(_candidate)
sys.path.insert(0, os.path.join(_candidate, "hooks"))
import _common as common  # noqa: E402
import _hardline_notify_common as common_notify  # noqa: E402


def _run():
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:
        return
    if payload.get("hook_event_name") != "UserPromptSubmit":
        return

    project_dir = os.environ.get("DEVIN_PROJECT_DIR")
    if not project_dir or not os.path.isdir(project_dir):
        return

    if not common_notify.is_brain_linked(project_dir):
        return

    root = common.resolve_root()
    state_file = common_notify.state_path(root, project_dir)
    state = common_notify.read_state(state_file)
    state["last_user_prompt_ts"] = time.time()
    common_notify.write_state(state_file, state)


def main():
    try:
        _run()
    except Exception as e:
        print(f"[user_prompt_submit_timestamp] unexpected error: {type(e).__name__}", file=sys.stderr)
    sys.exit(0)


if __name__ == "__main__":
    main()
