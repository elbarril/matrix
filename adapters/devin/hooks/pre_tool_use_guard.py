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
import fnmatch
import json
import os
import subprocess
import sys

_candidate = os.path.dirname(os.path.abspath(__file__))
for _ in range(3):
    _candidate = os.path.dirname(_candidate)
sys.path.insert(0, os.path.join(_candidate, "hooks"))
import _common as common  # noqa: E402
import _writer_lane as lane  # noqa: E402
import pre_exec_guard  # noqa: E402

ROOT = common.resolve_root()
BIN_MATRIX = os.path.join(ROOT, "bin", "matrix")

SHELL_TOOLS = {"exec", "run_command", "run-command"}
NATIVE_EDIT_TOOLS = {"edit", "write", "multi_edit"}

# Shared-surface constants (spec Q2-D section 1.a). Done-criteria grep these
# verbatim.
SHARED_SURFACE_EXACT = ("AGENTS.md", "DEVIN.md", "brain/data/lessons.md",
                        "brain/data/capability-map.md")
SHARED_SURFACE_GLOBS = ("brain/agents/*.md",)
SHARED_SURFACE_PREFIXES = ("hooks/", "bin/", "adapters/")
PROJECT_LESSON_PREFIX = "brain/data/lessons/"

DEFAULT_LANE_TTL_S = 120

# Secret-deny read guidance (spec 2026-09-07): Devin's Read(...) deny matcher
# blocks read/grep/glob tools and exec commands that read content with a
# literal path (`cat`, `ls`), but NOT predicates (`test -f`), `source`, or
# `$HOME` indirection. This check adds user-visible guidance BEFORE the Layer-1
# pre_exec_guard. Patterns come from the managed-deny sidecar per event (no
# cache); any sidecar problem fails open (allow, no error log).
SECRET_DENY_SIDECAR = os.path.join(
    os.path.expanduser("~"), ".config", "devin", ".matrix-managed-deny.json"
)
SECRET_DENY_READ_VERBS = {"cat", "head", "tail", "less", "more", "grep"}
SECRET_DENY_READ_VERBS_SPECIAL = {"sed", "ls"}


def _secret_deny_managed_patterns():
    """Return the sidecar's managed[] deny patterns (Read(...) wrapper
    stripped), or None on any failure — the caller fails open to allow."""
    if not os.path.isfile(SECRET_DENY_SIDECAR):
        return None
    try:
        with open(SECRET_DENY_SIDECAR, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    managed = data.get("managed")
    if not isinstance(managed, list):
        return None
    patterns = []
    for p in managed:
        if not isinstance(p, str):
            continue
        p = p.strip()
        if p.startswith("Read(") and p.endswith(")"):
            p = p[len("Read("):-1]
        if p:
            patterns.append(p)
    return patterns


def _secret_deny_literal_path(token):
    """True only for tokens that look like a literal path the deny matcher
    resolves (leading ~, /, ./ or ../). Tokens with indirection characters
    ($, parens, quotes) fail open — skip them."""
    if not isinstance(token, str) or not token:
        return False
    if any(ch in token for ch in "$()'\"`"):
        return False
    return token.startswith(("~", "/", "./", "../"))


def _secret_deny_path_matches(pattern_abs, path_abs):
    """fnmatch on the full absolute path; for directory patterns ending in
    `**`, also accept the path equal to the pattern without `**` or falling
    under that directory prefix."""
    if pattern_abs.endswith("**"):
        prefix = pattern_abs[:-2]
        if path_abs == prefix.rstrip("/") or path_abs.startswith(prefix):
            return True
    return fnmatch.fnmatchcase(path_abs, pattern_abs)


def _secret_deny_rel_hint(path_abs, home, raw_token):
    try:
        rel = os.path.relpath(path_abs, home)
    except ValueError:
        rel = None
    if rel is not None and not rel.startswith(".."):
        return "$HOME/" + rel
    return raw_token


def _secret_deny_read_block(command):
    """Return (verb, pattern, rel_hint) when `command` reads a secret-deny
    path with a literal path argument; None otherwise (allow). Fail-open on
    any parse/sidecar problem — this hook only adds guidance on top of
    Devin's native matcher."""
    if not isinstance(command, str) or not command.strip():
        return None
    patterns = _secret_deny_managed_patterns()
    if not patterns:
        return None
    tokens = pre_exec_guard._tokenize(command)
    if tokens is None:
        return None
    home = os.path.expanduser("~")
    for seg in pre_exec_guard._segment(tokens):
        for i, verb in enumerate(seg):
            if verb not in SECRET_DENY_READ_VERBS and verb not in SECRET_DENY_READ_VERBS_SPECIAL:
                continue
            args = seg[i + 1:]
            if verb == "sed" and any(
                a == "-i" or a == "--in-place" or (a.startswith("-i") and a != "-i")
                for a in args
            ):
                # sed -i is a mutation, not a read; pre_exec_guard owns it.
                continue
            for arg in args:
                if not _secret_deny_literal_path(arg):
                    continue
                if verb == "ls" and arg.endswith("/"):
                    # Directory listing is not a file-content read.
                    continue
                path_abs = os.path.expanduser(arg)
                for pattern in patterns:
                    if _secret_deny_path_matches(os.path.expanduser(pattern), path_abs):
                        return verb, pattern, _secret_deny_rel_hint(path_abs, home, arg)
    return None


def _secret_deny_read_message(pattern, rel_hint):
    return (
        f"comando lee una ruta protegida por secret-deny ({pattern}). "
        f"Alternativas: test -f \"{rel_hint}\" para existencia, "
        f"source \"{rel_hint}\" para cargar el token, o el script de la skill. "
        "Nunca cat/ls sobre rutas de credenciales."
    )


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


def _extract_tool_paths(tool_name, tool_input):
    """Extract the target path(s) of a native edit tool (same shape as
    session_audit._extract_tool_paths; the raw PreToolUse tool_input keys for
    edit/write/multi_edit are file_path/path/paths/edits)."""
    if tool_name not in NATIVE_EDIT_TOOLS:
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


def _classify_surface(rel_path):
    """Classify a normalized rel path against the shared-surface constants.

    Returns "core" for the exact/glob/prefix surface, "project" for a
    brain/data/lessons/<x>.md project lesson file, or None when the path is
    not shared surface. `brain/data/lessons/*.md` (project lesson files) are
    shared surface but classified separately (spec 1.a/1.e): only the core
    lessons.md is exact-match protected.
    """
    if rel_path in SHARED_SURFACE_EXACT:
        return "core"
    for pattern in SHARED_SURFACE_GLOBS:
        if __import__("fnmatch").fnmatchcase(rel_path, pattern):
            return "core"
    for prefix in SHARED_SURFACE_PREFIXES:
        if rel_path.startswith(prefix):
            return "core"
    if rel_path.startswith(PROJECT_LESSON_PREFIX) and rel_path.endswith(".md"):
        return "project"
    return None


def _kill_switch_active():
    value = os.environ.get("MATRIX_SHARED_SURFACE_ALLOW", "").strip().lower()
    return value in ("1", "true")


def _resolve_mode():
    """Run `bin/matrix scope` (subprocess, timeout 10) and return (mode, project).

    Returns (None, None) on any failure or unexpected output; the caller
    treats that as fail-closed BLOCK for shared-surface writes.
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
    except Exception:
        return None, None
    if proc.returncode != 0:
        return None, None
    line = (proc.stdout or "").splitlines()[0].strip() if proc.stdout else ""
    parts = line.split("\t")
    mode = parts[0].strip() if parts else ""
    project = parts[1].strip() if len(parts) > 1 else ""
    if mode in ("workspace", "bound", "bound-unregistered"):
        return mode, project
    return None, None


def _incident_writer_collision(rel_path, holder):
    """Log a real writer collision to the Link ledger (spec 2.c). Best-effort;
    only called when a held lane blocks a different session's write."""
    try:
        subprocess.run(
            [BIN_MATRIX, "link", "incident:writer-collision", "matrix",
             f"target={rel_path}", f"holder={holder}"],
            env={**os.environ, "MATRIX_ROOT": ROOT},
            capture_output=True,
            text=True,
            timeout=10,
            stdin=subprocess.DEVNULL,
        )
    except Exception:
        pass


def _block(reason, guard_reason, session_id, tool_name):
    _audit_decision(session_id, tool_name, "block", guard_reason)
    print(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False))
    sys.exit(2)


def _run_shell_guard(tool_name, tool_input, session_id):
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


def _run_shared_surface_guard(tool_name, tool_input, session_id):
    """Gate native edit tools (edit/write/multi_edit) against the shared
    surface (spec Q2-D section 1). Fast path: if no target path is shared
    surface, allow with 0 subprocess. Slow path (≥1 surface path): resolve
    mode via `bin/matrix scope`, apply the bound-session restriction with the
    proactive lessons promotion exception and the kill-switch, then take the
    per-file writer lane for every surface target (all-or-nothing).
    """
    if session_id is None:
        session_id = common.current_session_id(ROOT)

    raw_paths = _extract_tool_paths(tool_name, tool_input)
    rel_paths = []
    seen = set()
    for raw in raw_paths:
        rel = lane.normalize_relpath(ROOT, raw)
        if rel is None or rel in seen:
            continue
        seen.add(rel)
        rel_paths.append(rel)

    surface_paths = [rel for rel in rel_paths if _classify_surface(rel)]
    if not surface_paths:
        # Fast path: nothing on the shared surface — allow, 0 subprocess.
        print(json.dumps({"decision": "allow"}, ensure_ascii=False))
        sys.exit(0)

    mode, project = _resolve_mode()
    if mode is None:
        _block(
            "shared-surface write blocked: cannot resolve workspace/bound mode "
            "(scope failed)",
            "guard invocation failed",
            session_id,
            tool_name,
        )

    kill_switch = _kill_switch_active()
    blocked_rel = None
    for rel in sorted(surface_paths):
        if mode == "workspace":
            # Workspace keeps full access to the shared surface (under lane).
            break
        if _classify_surface(rel) == "project":
            lesson_name = rel[len(PROJECT_LESSON_PREFIX):-len(".md")]
            if mode == "bound-unregistered":
                blocked_rel = rel
                break
            if lesson_name != project:
                blocked_rel = rel
                break
            continue
        if rel == "brain/data/lessons.md":
            # Proactive promotion exception (rule neo.md 123): core lessons.md
            # stays writable from bound, under the lane.
            continue
        blocked_rel = rel
        break

    if blocked_rel is not None and not kill_switch:
        _block(
            f"shared-surface write blocked in bound session: {blocked_rel} "
            "(use workspace mode or MATRIX_SHARED_SURFACE_ALLOW=1)",
            f"shared_surface_block:{blocked_rel}",
            session_id,
            tool_name,
        )

    ttl_s = DEFAULT_LANE_TTL_S
    try:
        ttl_s = int(os.environ.get("MATRIX_WRITER_LANE_TTL_S", str(DEFAULT_LANE_TTL_S)))
    except ValueError:
        pass

    acquired = []
    try:
        for rel in sorted(surface_paths):
            result = lane.acquire(ROOT, rel, session_id, ttl_s)
            if result.get("ok"):
                acquired.append(rel)
                continue
            holder = result.get("holder")
            since = result.get("since")
            _incident_writer_collision(rel, holder)
            for acquired_rel in acquired:
                lane.release(ROOT, acquired_rel, session_id)
            reason = f"writer lane busy: {rel}"
            if holder is not None and since:
                reason += f" (held by {holder} since {since})"
            _block(reason, f"writer_lane_busy:{rel}", session_id, tool_name)
    except Exception:
        for acquired_rel in acquired:
            lane.release(ROOT, acquired_rel, session_id)
        _block("guard invocation failed", "guard invocation failed", session_id, tool_name)

    _audit_decision(session_id, tool_name, "allow", None)
    print(json.dumps({"decision": "allow"}, ensure_ascii=False))
    sys.exit(0)


def main():
    payload = _read_stdin_json()
    tool_name = payload.get("tool_name")
    tool_input = payload.get("tool_input")
    session_id = payload.get("session_id")
    if not isinstance(tool_input, dict):
        tool_input = {}

    # Shell tools → secret-deny read guidance first, then pre_exec_guard
    # (Layer-1). The secret-deny check only blocks with guidance; everything
    # else continues the unchanged flow.
    if tool_name in SHELL_TOOLS:
        command = tool_input.get("command")
        if isinstance(command, str):
            block = _secret_deny_read_block(command)
            if block:
                verb, pattern, rel_hint = block
                _block(
                    _secret_deny_read_message(pattern, rel_hint),
                    f"secret_deny_read:{verb}:{pattern}",
                    session_id,
                    tool_name,
                )
        _run_shell_guard(tool_name, tool_input, session_id)

    # Native edit tools → shared-surface gate + writer lane (Q2-D).
    if tool_name in NATIVE_EDIT_TOOLS:
        _run_shared_surface_guard(tool_name, tool_input, session_id)

    # Any other tool is out of scope for this guard.
    print(json.dumps({"decision": "allow"}, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()
