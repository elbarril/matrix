#!/usr/bin/env python3
"""Devin CLI SessionEnd hook — best-effort Telegram notification for bound projects.

Fires only when ALL of these are true:
- the session was NOT started by the Hardline dispatcher (no duplicate ack)
- DEVIN_PROJECT_DIR points to a Matrix-bound project
- the Hardline Telegram bridge is running
- the Telegram secrets file is present and complete

This is intentionally separate from session_audit.py so a slow/failing Telegram
POST can never delay or break the audit trail / session close logic.
"""
import datetime
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


# Resolve the Matrix root the same way session_audit.py does.
_candidate = os.path.dirname(os.path.abspath(__file__))
for _ in range(3):
    _candidate = os.path.dirname(_candidate)
sys.path.insert(0, os.path.join(_candidate, "hooks"))
import _common as common  # noqa: E402
import _hardline_notify_common as common_notify  # noqa: E402

ROOT = common.resolve_root()
BIN_MATRIX = os.path.join(ROOT, "bin", "matrix")
HARDLINE_CTL = os.path.join(ROOT, "modules", "hardline", "hardline-ctl.sh")
SECRETS_PATH = os.path.expanduser("~/.config/devin/hardline/telegram.env")

TOKEN_ENV = "MATRIX_HARDLINE_TELEGRAM_BOT_TOKEN"
CHAT_ENV = "MATRIX_HARDLINE_TELEGRAM_ALLOWED_CHAT_ID"


# _ppid_of, _ancestor_is_hardline_dispatch, _bound_project_name,
# _bridge_running, _read_secrets_file, _send_message all REMOVED —
# now live in _hardline_notify_common.py and are called as
# common_notify.<name>(...) below. No behavior change.


SUPPRESS_WINDOW_SECONDS = 60


def _recently_notified_by_stop(root, project_dir):
    """True if stop_notify.py sent a notification for this project within
    the last SUPPRESS_WINDOW_SECONDS. Never raises; any read failure ->
    False (fail toward sending, not toward silence, since a missed
    SessionEnd message is worse than one extra message)."""
    try:
        path = common_notify.state_path(root, project_dir)
        state = common_notify.read_state(path)
        last_notified = state.get("last_notified_ts")
        if not isinstance(last_notified, (int, float)):
            return False
        return (time.time() - last_notified) < SUPPRESS_WINDOW_SECONDS
    except Exception:
        return False


def _now_str():
    return datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def main():
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:
        sys.exit(0)

    if payload.get("hook_event_name") != "SessionEnd":
        sys.exit(0)

    if common_notify.is_hardline_dispatched():
        sys.exit(0)

    project_dir = os.environ.get("DEVIN_PROJECT_DIR")
    if not project_dir or not os.path.isdir(project_dir):
        sys.exit(0)

    if not os.path.islink(os.path.join(project_dir, "_brain")):
        sys.exit(0)

    root = common.resolve_root()
    project_name = common_notify.bound_project_name(root, project_dir)
    if not project_name:
        sys.exit(0)

    if not common_notify.bridge_running(root):
        sys.exit(0)

    if _recently_notified_by_stop(root, project_dir):
        sys.exit(0)

    if not os.path.isfile(SECRETS_PATH):
        sys.exit(0)
    secrets = common_notify.read_secrets_file(SECRETS_PATH)
    token = secrets.get(TOKEN_ENV)
    chat_id = secrets.get(CHAT_ENV)
    if not token or not chat_id:
        print("[session_end_notify] secrets file present but incomplete", file=sys.stderr)
        sys.exit(0)

    reason = str(payload.get("reason") or "sin motivo reportado")[:200]
    text = f"🔔 {project_name}\nSesión finalizada — {reason}\n{_now_str()}"

    try:
        common_notify.send_message(token, chat_id, text)
    except Exception as e:
        print(f"[session_end_notify] send failed: {type(e).__name__}", file=sys.stderr)

    sys.exit(0)


if __name__ == "__main__":
    main()
