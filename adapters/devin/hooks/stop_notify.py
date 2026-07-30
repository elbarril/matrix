#!/usr/bin/env python3
"""Devin CLI Stop hook — best-effort Telegram notification for long
unattended turns on Matrix-bound projects.

HARD INVARIANT: never writes to stdout, always exits 0. A Stop hook that
writes {"decision": "block", ...} to stdout or exits nonzero/2 forces the
agent to keep looping (Devin CLI docs). This script has no legitimate
reason to ever emit hookSpecificOutput, so it enforces silence structurally:
every code path funnels through main()'s outer try/except with all
diagnostics on stderr only.
"""
import datetime
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


def _format_elapsed(seconds):
    total_minutes = int(seconds // 60)
    hours, minutes = divmod(total_minutes, 60)
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def _format_message(project_name, elapsed, last_prompt_ts):
    elapsed_human = _format_elapsed(elapsed)
    last_prompt_time = datetime.datetime.fromtimestamp(last_prompt_ts).astimezone().strftime("%H:%M")
    timestamp = datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")
    return (
        f"⏳ {project_name}\n"
        f"Turno largo terminado — esperando tu respuesta\n"
        f"Duración: {elapsed_human} (desde {last_prompt_time})\n"
        f"{timestamp}"
    )


def _run():
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:
        return
    if payload.get("hook_event_name") != "Stop":
        return

    if common_notify.is_hardline_dispatched():
        return

    project_dir = os.environ.get("DEVIN_PROJECT_DIR")
    if not project_dir or not os.path.isdir(project_dir):
        return

    if not common_notify.is_brain_linked(project_dir):
        return

    root = common.resolve_root()
    state_file = common_notify.state_path(root, project_dir)
    state = common_notify.read_state(state_file)

    last_prompt_ts = state.get("last_user_prompt_ts")
    if not isinstance(last_prompt_ts, (int, float)):
        return

    elapsed = time.time() - last_prompt_ts
    if elapsed < 0:
        return

    # Read secrets ONCE, locally, before any subprocess call.
    secrets_path = common_notify.SECRETS_PATH_DEFAULT
    if not os.path.isfile(secrets_path):
        return
    try:
        secrets = common_notify.read_secrets_file(secrets_path)
    except Exception:
        return

    threshold = common_notify.get_threshold_seconds(secrets)
    if elapsed < threshold:
        return

    # --- Only turns clearing the bar reach here. Now do the expensive checks. ---

    project_name = common_notify.bound_project_name(root, project_dir)
    if not project_name:
        return

    if not common_notify.bridge_running(root):
        return

    creds = common_notify.get_telegram_credentials_from(secrets)
    if creds is None:
        print("[stop_notify] secrets file present but incomplete", file=sys.stderr)
        return
    token, chat_id = creds

    text = _format_message(project_name, elapsed, last_prompt_ts)

    try:
        common_notify.send_message(token, chat_id, text)
    except Exception as e:
        print(f"[stop_notify] send failed: {type(e).__name__}", file=sys.stderr)
        return

    now = time.time()
    state["last_notified_ts"] = now
    common_notify.write_state(state_file, state)


def main():
    try:
        _run()
    except Exception as e:
        print(f"[stop_notify] unexpected error: {type(e).__name__}", file=sys.stderr)
    sys.exit(0)


if __name__ == "__main__":
    main()
