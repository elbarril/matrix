#!/usr/bin/env python3
"""Shared helpers for the Hardline Devin-hook notifier family.

Extracted from session_end_notify.py (Smith-reviewed original) so that
stop_notify.py can reuse the identical Tier-1/Tier-2/bridge/secrets/send
logic without duplicating it a second time. No behavior change versus the
original inline code — this is a pure extraction.

Every function here degrades to a safe "false"/"None"/no-op on any internal
error. Nothing in this module ever raises past its own boundary except
send_message, whose caller is required to catch it (see docstring below).
"""
import hashlib
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

# Resolve the Matrix root the same way session_audit.py does, so the default
# secrets path is repo-relative rather than hardcoded to ~/.config/devin.
_candidate = os.path.dirname(os.path.abspath(__file__))
for _ in range(3):
    _candidate = os.path.dirname(_candidate)
sys.path.insert(0, os.path.join(_candidate, "hooks"))
import _common as common  # noqa: E402

TOKEN_ENV = "MATRIX_HARDLINE_TELEGRAM_BOT_TOKEN"
CHAT_ENV = "MATRIX_HARDLINE_TELEGRAM_ALLOWED_CHAT_ID"
SECRETS_PATH_DEFAULT = os.path.join(common.resolve_root(), "brain", "state", "hardline", "telegram.env")


def ppid_of(pid):
    """Return the parent PID of `pid` from /proc, or None on any failure."""
    try:
        with open(f"/proc/{pid}/stat", "rb") as fh:
            data = fh.read()
    except (OSError, IOError):
        return None
    try:
        start = data.index(b"(")
        end = data.index(b") ", start)
        rest = data[end + 2 :]
        parts = rest.split()
        return int(parts[1])
    except (ValueError, IndexError):
        return None


def ancestor_is_hardline_dispatch():
    """Cheap belt-and-suspenders: /proc ancestry walk (5 levels) for
    'hardline-dispatch.sh'. Identical to the existing implementation."""
    pid = os.getpid()
    for _ in range(5):
        ppid = ppid_of(pid)
        if ppid is None or ppid <= 1:
            return False
        pid = ppid
        try:
            with open(f"/proc/{pid}/cmdline", "rb") as fh:
                cmdline = fh.read().replace(b"\0", b" ").decode("utf-8", errors="replace")
        except (OSError, IOError):
            continue
        if "hardline-dispatch.sh" in cmdline:
            return True
    return False


def is_hardline_dispatched():
    """True if MATRIX_HARDLINE_DISPATCH=1 in the environment OR
    ancestor_is_hardline_dispatch() is True. Combines the OR'd signal
    check that main() currently inlines in session_end_notify.py, so
    every caller does it identically."""
    if os.environ.get("MATRIX_HARDLINE_DISPATCH") == "1":
        return True
    return ancestor_is_hardline_dispatch()


def is_brain_linked(project_dir):
    """Tier 1: os.path.islink(os.path.join(project_dir, '_brain')).
    No subprocess. The near-zero-cost fast path for the common case."""
    return os.path.islink(os.path.join(project_dir, "_brain"))


def bound_project_name(root, project_dir, bin_matrix=None):
    """Tier 2: run `<bin_matrix> bindings --json` (5s timeout), longest-
    prefix-match project_dir against bound==true entries, return
    entry['name'] or None. Identical logic to the existing
    _bound_project_name; bin_matrix defaults to <root>/bin/matrix."""
    if bin_matrix is None:
        bin_matrix = os.path.join(root, "bin", "matrix")
    try:
        env = {**os.environ, "MATRIX_ROOT": root}
        proc = subprocess.run(
            [bin_matrix, "bindings", "--json"],
            env=env,
            capture_output=True,
            text=True,
            timeout=5,
            stdin=subprocess.DEVNULL,
        )
        if proc.returncode != 0:
            return None
        data = json.loads(proc.stdout or "[]")
        if not isinstance(data, list):
            return None
        project_dir = os.path.abspath(project_dir)
        best = None
        for entry in data:
            if not isinstance(entry, dict) or entry.get("bound") is not True:
                continue
            path = entry.get("path")
            if not isinstance(path, str):
                continue
            path = os.path.abspath(path)
            if project_dir == path or project_dir.startswith(path + os.sep):
                if best is None or len(path) > len(best["path"]):
                    best = entry
        return best.get("name") if best else None
    except Exception:
        return None


def bridge_running(root, hardline_ctl=None):
    """Run `<hardline_ctl> status --json` (5s timeout), return
    bool(data['bridge']['running']). hardline_ctl defaults to
    <root>/modules/hardline/hardline-ctl.sh."""
    if hardline_ctl is None:
        hardline_ctl = os.path.join(root, "modules", "hardline", "hardline-ctl.sh")
    try:
        env = {**os.environ, "MATRIX_ROOT": root}
        proc = subprocess.run(
            [hardline_ctl, "status", "--json"],
            env=env,
            capture_output=True,
            text=True,
            timeout=5,
            stdin=subprocess.DEVNULL,
        )
        if proc.returncode != 0:
            return False
        data = json.loads(proc.stdout or "{}")
        if not isinstance(data, dict):
            return False
        return bool(data.get("bridge", {}).get("running"))
    except Exception:
        return False


def read_secrets_file(path):
    """Parse a shell env file into a dict. Raises the same exceptions as
    open()/read() would (FileNotFoundError, OSError, UnicodeDecodeError) —
    callers must wrap in try/except, exactly as the original inline call
    site does today. This function does NOT swallow errors, matching the
    original's behavior (the original relies on main()'s os.path.isfile
    pre-check, not an internal try/except, to avoid the common no-file
    case)."""
    env = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            line = line.removeprefix("export ").strip()
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip("'\"")
    return env


def get_telegram_credentials(secrets_path=SECRETS_PATH_DEFAULT):
    """Convenience wrapper: os.path.isfile check -> read_secrets_file ->
    require both TOKEN_ENV and CHAT_ENV non-empty -> return (token, chat_id)
    or None. Never raises; every failure path returns None."""
    if not os.path.isfile(secrets_path):
        return None
    try:
        secrets = read_secrets_file(secrets_path)
    except Exception:
        return None
    return get_telegram_credentials_from(secrets)


def get_telegram_credentials_from(secrets):
    """Variant of get_telegram_credentials that takes an already-parsed
    dict, so stop_notify.py can read the secrets file exactly once
    (for both the threshold and the credentials). get_telegram_credentials
    becomes a one-line wrapper around this (read file -> call this)."""
    token = secrets.get(TOKEN_ENV)
    chat_id = secrets.get(CHAT_ENV)
    if not token or not chat_id:
        return None
    return (token, chat_id)


def send_message(token, chat_id, text):
    """POST to Telegram sendMessage. Identical to the existing
    _send_message / telegram-bridge.py's send_message. Raises on any
    failure (network, non-ok response) — caller catches, logs exception
    type only (never token/body), and continues."""
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


DEFAULT_THRESHOLD_SECONDS = 1800


def get_threshold_seconds(secrets):
    """Parse MATRIX_HARDLINE_STOP_NOTIFY_THRESHOLD_SECONDS from an
    already-parsed secrets dict. Missing/empty/non-numeric/<=0 all fall
    back to DEFAULT_THRESHOLD_SECONDS (1800). Never raises."""
    raw = secrets.get("MATRIX_HARDLINE_STOP_NOTIFY_THRESHOLD_SECONDS")
    if not raw:
        return DEFAULT_THRESHOLD_SECONDS
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return DEFAULT_THRESHOLD_SECONDS
    if value <= 0:
        return DEFAULT_THRESHOLD_SECONDS
    return value


def state_path(root, project_dir):
    """$MATRIX_ROOT/brain/state/hardline/stop-notify/<sha1(project_dir)>.json"""
    project_dir = os.path.abspath(project_dir)
    digest = hashlib.sha1(project_dir.encode("utf-8")).hexdigest()
    return os.path.join(root, "brain", "state", "hardline", "stop-notify", f"{digest}.json")


def read_state(path):
    """Never raises. Missing/corrupt/unreadable -> {}."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def write_state(path, data):
    """Atomic (temp file + os.replace). Swallows OSError — a failed write
    just means the next hook invocation falls back to 'unknown' state."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        os.replace(tmp, path)
    except OSError:
        pass
