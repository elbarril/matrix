#!/usr/bin/env python3
"""Long-poll Telegram messages into the Hardline inbox without exposing bot secrets.

Completion notification tracking is persisted to disk (same atomic write-then-replace
pattern as the offset file), so a bridge restart can still notify for requests accepted
before that restart. The only loss window left is the few milliseconds between accepting
a message (append_inbox) and persisting its tracking entry (save_tracked) — if the
process dies exactly there, that one event completes and is visible in queue.jsonl /
the status webapp, but Telegram never learns which chat to notify.
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INBOX_PATH = ROOT / "modules" / "hardline" / "inbox.log"
OFFSET_PATH = ROOT / "brain" / "state" / "hardline" / "telegram-offset"
TRACKED_PATH = ROOT / "brain" / "state" / "hardline" / "telegram-tracked.json"
QUEUE_PATH = ROOT / "brain" / "state" / "hardline" / "queue.jsonl"
TOKEN_ENV = "MATRIX_HARDLINE_TELEGRAM_BOT_TOKEN"
CHAT_ENV = "MATRIX_HARDLINE_TELEGRAM_ALLOWED_CHAT_ID"
PROJECT_RE = re.compile(r"^[A-Za-z0-9._-]+$")
TERMINAL_STATES = {
    "acked-success",
    "acked-failed",
    "acked-refused-generic",
    "acked-needs-human",
    "acked-crashed",
    "orphaned",
}


def dedupe_key(project, raw_line):
    return hashlib.sha256(f"{project}\0{raw_line}".encode("utf-8")).hexdigest()


def parse_message(message):
    """Return a monitor-ready line, or None for a message outside the bridge grammar."""
    if not isinstance(message, dict):
        return None
    text = message.get("text")
    if not isinstance(text, str) or "\n" in text or "\r" in text:
        return None
    parts = text.strip().split(None, 1)
    if len(parts) != 2:
        return None
    project, task = parts
    if not PROJECT_RE.fullmatch(project) or not task.strip():
        return None
    return f"{project}|{task.strip()}"


def iter_valid_updates(payload, allowed_chat_id=None, include_chat_id=False):
    if not isinstance(payload, dict) or payload.get("ok") is not True:
        raise ValueError("Telegram response is not a successful getUpdates payload")
    updates = payload.get("result")
    if not isinstance(updates, list):
        raise ValueError("Telegram response has no result array")
    for update in updates:
        if not isinstance(update, dict) or not isinstance(update.get("update_id"), int):
            continue
        message = update.get("message")
        chat = message.get("chat") if isinstance(message, dict) else None
        chat_id = chat.get("id") if isinstance(chat, dict) else None
        line = None if allowed_chat_id is not None and str(chat_id) != allowed_chat_id else parse_message(message)
        if include_chat_id:
            yield update["update_id"], line, chat_id
        else:
            yield update["update_id"], line


def load_offset():
    try:
        value = OFFSET_PATH.read_text(encoding="utf-8").strip()
        return int(value) if value else None
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        print("[telegram-bridge] invalid offset state; refusing to risk duplicate delivery", file=sys.stderr)
        raise SystemExit(1)


def save_offset(offset):
    OFFSET_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = OFFSET_PATH.with_suffix(".tmp")
    temporary.write_text(f"{offset}\n", encoding="utf-8")
    temporary.replace(OFFSET_PATH)


def load_tracked():
    try:
        return json.loads(TRACKED_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError) as error:
        print(f"[telegram-bridge] invalid tracked state; starting empty: {error}", file=sys.stderr)
        return {}


def save_tracked(tracked):
    TRACKED_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = TRACKED_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(tracked), encoding="utf-8")
    temporary.replace(TRACKED_PATH)


def append_inbox(line):
    INBOX_PATH.parent.mkdir(parents=True, exist_ok=True)
    with INBOX_PATH.open("a", encoding="utf-8") as inbox:
        inbox.write(f"{line}\n")
        inbox.flush()
        os.fsync(inbox.fileno())


def terminal_events():
    try:
        with QUEUE_PATH.open(encoding="utf-8") as queue:
            events = [json.loads(line) for line in queue if line.strip()]
    except FileNotFoundError:
        return {}
    return {
        event.get("dedupe_key"): event
        for event in events
        if event.get("state") in TERMINAL_STATES and isinstance(event.get("dedupe_key"), str)
    }


def notification_text(event):
    project = event.get("project", "Hardline")
    task = str(event.get("raw_line", ""))[:100]
    state = event.get("state")
    if state == "acked-success":
        return f"✅ {project}: listo — {task}"
    if state == "acked-needs-human":
        reason = event.get("outcome_note") or "el agente indicó que no puede continuar sin una decisión humana"
        return f"⚠️ {project}: necesita tu decisión — {task}\nMotivo: {reason}"
    if state == "acked-refused-generic":
        reason = event.get("reject_reason") or "rechazado antes de ejecutarse por una validación temprana"
        return f"🚫 {project}: rechazado antes de ejecutarse — {task}\nMotivo: {reason}"
    if state == "acked-failed":
        return f"❌ {project}: terminó con error — {task}\nMotivo: se detectó lenguaje de fallo explícito en la salida del agente"
    if state == "acked-crashed":
        return f"💥 {project}: el proceso se interrumpió — {task}\nMotivo: sin salida utilizable o el proceso terminó de forma anómala (código de salida inesperado o posible kill)"
    if state == "orphaned":
        return f"⏱️ {project}: se agotó el tiempo — {task}\nMotivo: no terminó dentro del límite de tiempo configurado"
    return f"❔ {project}: estado desconocido \"{state}\" — revisar 'matrix hardline queue' — {task}"


def send_message(token, chat_id, text):
    body = urllib.parse.urlencode({"chat_id": str(chat_id), "text": text}).encode("utf-8")
    request = urllib.request.Request(
        "https://api.telegram.org/bot" + token + "/sendMessage",
        data=body,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        payload = json.load(response)
    if not isinstance(payload, dict) or payload.get("ok") is not True:
        raise ValueError("Telegram response is not a successful sendMessage payload")


def notify_terminal_events(token, tracked):
    completed = terminal_events()
    changed = False
    for key, chat_id in list(tracked.items()):
        event = completed.get(key)
        if event is None:
            continue
        send_message(token, chat_id, notification_text(event))
        del tracked[key]
        changed = True
    if changed:
        save_tracked(tracked)


def get_updates(token, offset):
    parameters = {"timeout": "50", "allowed_updates": json.dumps(["message"])}
    if offset is not None:
        parameters["offset"] = str(offset)
    url = "https://api.telegram.org/bot" + token + "/getUpdates?" + urllib.parse.urlencode(parameters)
    request = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def parse_args():
    parser = argparse.ArgumentParser(description="Long-poll Telegram into the Hardline inbox.")
    parser.add_argument("--once", action="store_true", help="perform one getUpdates request, then exit")
    parser.add_argument(
        "--show-chat-ids",
        action="store_true",
        help="print source chat IDs from one getUpdates request; no inbox writes; save its cursor",
    )
    parser.add_argument(
        "--parse-response",
        metavar="PATH",
        help="test-only: print valid inbox lines from a saved getUpdates JSON response; no network or writes",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    if args.parse_response:
        try:
            payload = json.loads(Path(args.parse_response).read_text(encoding="utf-8"))
            for _, line in iter_valid_updates(payload):
                if line is not None:
                    print(line)
        except (OSError, json.JSONDecodeError, ValueError) as error:
            print(f"telegram-bridge: cannot parse test response: {error}", file=sys.stderr)
            return 1
        return 0

    token = os.environ.get(TOKEN_ENV, "").strip()
    if not token:
        print(f"telegram-bridge: {TOKEN_ENV} must be set; refusing to start.", file=sys.stderr)
        return 1
    allowed_chat_id = os.environ.get(CHAT_ENV, "").strip() or None
    offset = load_offset()
    tracked = load_tracked()

    while True:
        try:
            payload = get_updates(token, offset)
            if args.show_chat_ids:
                if not isinstance(payload, dict) or payload.get("ok") is not True:
                    raise ValueError("Telegram response is not a successful getUpdates payload")
                updates = payload.get("result", [])
                highest_update_id = offset
                for update in updates:
                    if isinstance(update, dict) and isinstance(update.get("update_id"), int):
                        highest_update_id = max(highest_update_id or 0, update["update_id"] + 1)
                    message = update.get("message") if isinstance(update, dict) else None
                    chat = message.get("chat") if isinstance(message, dict) else None
                    if isinstance(chat, dict) and "id" in chat:
                        print(chat["id"])
                if highest_update_id is not None:
                    save_offset(highest_update_id)
                return 0
            for update_id, line, chat_id in iter_valid_updates(payload, allowed_chat_id, include_chat_id=True):
                if line is not None:
                    append_inbox(line)
                    project, raw_line = line.split("|", 1)
                    tracked[dedupe_key(project, raw_line)] = chat_id
                    save_tracked(tracked)
                offset = update_id + 1
                save_offset(offset)
            notify_terminal_events(token, tracked)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError, ValueError):
            print("[telegram-bridge] Telegram request failed; retrying in 5 seconds.", file=sys.stderr)
            if args.once:
                return 1
            time.sleep(5)
            continue
        except OSError as error:
            print(f"[telegram-bridge] local inbox or offset write failed: {error}", file=sys.stderr)
            return 1
        if args.once:
            return 0


if __name__ == "__main__":
    sys.exit(main())
