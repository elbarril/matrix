#!/usr/bin/env python3
"""Devin CLI Stop hook — best-effort Telegram notification for every turn.

Fires on every turn (no duration threshold) for registered Matrix project
sessions and Matrix workspace mode, sending the turn's assistant output.

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


OUTPUT_MAX_CHARS = 3800
CONTEXT_MAX_CHARS = 1200
TELEGRAM_MAX_CHARS = 4096
_TRUNCATED_SUFFIX = "… (truncado)"


def _build_message(project, output, now):
    """Build the per-turn Telegram message: header + output + timestamp,
    always <= TELEGRAM_MAX_CHARS. `output` is the turn's assistant text
    (already None when absent); `now` is a tz-aware datetime."""
    ts = now.strftime("%Y-%m-%d %H:%M:%S %z")
    body = output if output is not None else "(sin texto en este turno)"
    text = body[:OUTPUT_MAX_CHARS]
    if len(body) > OUTPUT_MAX_CHARS:
        text += _TRUNCATED_SUFFIX
    header = f"💬 {project}"
    # Belt and suspenders: if the total would exceed the hard limit, recut
    # the output to the remaining room (header and timestamp are kept).
    room = TELEGRAM_MAX_CHARS - len(header) - len(ts) - 2
    if len(text) > room:
        if room > len(_TRUNCATED_SUFFIX):
            text = body[: room - len(_TRUNCATED_SUFFIX)] + _TRUNCATED_SUFFIX
        else:
            text = body[: max(room, 0)]
    message = f"{header}\n{text}\n{ts}"
    # Last resort for a pathological project name: hard-truncate the whole
    # message so the Telegram 4096 limit is never exceeded.
    return message[:TELEGRAM_MAX_CHARS]


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
    project_name = common_notify.bound_project_name(root, project_dir)
    if not project_name:
        return

    if not common_notify.bridge_running(root):
        return

    # Read secrets ONCE, locally, before any subprocess call.
    secrets_path = common_notify.SECRETS_PATH_DEFAULT
    if not os.path.isfile(secrets_path):
        return
    try:
        secrets = common_notify.read_secrets_file(secrets_path)
    except Exception:
        return

    creds = common_notify.get_telegram_credentials_from(secrets)
    if creds is None:
        print("[stop_notify] secrets file present but incomplete", file=sys.stderr)
        return
    token, chat_id = creds

    output = payload.get("last_assistant_message")
    if not isinstance(output, str) or not output:
        output = None

    text = _build_message(project_name, output, datetime.datetime.now().astimezone())

    try:
        message_id = common_notify.send_message(token, chat_id, text)
    except Exception as e:
        print(f"[stop_notify] send failed: {type(e).__name__}", file=sys.stderr)
        return

    # Fase 2: seed the reply thread so a Telegram reply to this message can be
    # recognized by the bridge. kind="turn", session_id=null (the bridge opens
    # a fresh headless run seeded with this truncated context).
    context = output[:CONTEXT_MAX_CHARS] if output is not None else None
    common_notify.add_reply_thread(root, message_id, {
        "project": project_name,
        "session_id": None,
        "context": context,
        "kind": "turn",
        "created_at": time.time(),
    })


def main():
    try:
        _run()
    except Exception as e:
        print(f"[stop_notify] unexpected error: {type(e).__name__}", file=sys.stderr)
    sys.exit(0)


if __name__ == "__main__":
    main()
