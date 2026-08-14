#!/usr/bin/env python3
"""Seraph · pre_exec_guard — best-effort block on mutating shell commands
against protected core paths.

Input JSON:
  {"tool_name": "exec", "tool_input": {"command": "rm -rf brain/data/"}}

Output JSON (Layer-1 contract):
  {"hook": "pre_exec_guard", "ok": true}
  {"hook": "pre_exec_guard", "ok": false, "reason": "blocked rm near protected path: brain/data"}

This is a tokenizer-based best-effort guard, not a real shell parser. It only
covers the mutating operations called out in the architecture design: rm,
rmdir, mv, truncate, sed -i, git rm, and output redirection (> / >>) to a
protected path.

Audit contract (see adapters/devin/hooks/pre_tool_use_guard.py): every
`reason` this module returns is built only from a fixed verb plus the
relative path of an entry in `protected_paths()` (a public, non-secret
list). Never build a reason from the raw command string or tool_input --
the adapter persists `reason` verbatim to the shared audit log.
"""

import os
import shlex
import sys

from _common import emit, read_input, resolve_root

# Only these native tool names carry a shell command string.
SHELL_TOOLS = {"exec", "run_command", "run-command"}

# Mutating command names this guard recognizes as a single token (bare verb).
_MUTATING_VERBS = {"rm", "rmdir", "mv", "truncate"}

# Shell control operators that start a new command segment. A mutating verb
# only counts when it sits in command position (index 0) of a segment, and
# its arguments never cross into a different segment.
_CONTROL_OPS = {";", "&&", "||", "|", "&"}


def protected_paths(root):
    """Return absolute paths that this guard treats as protected core state."""
    paths = [
        os.path.join(root, "brain", "data"),
        os.path.join(root, "brain", "state"),
        os.path.join(root, "brain", "agents"),
        os.path.join(root, "AGENTS.md"),
        os.path.join(root, "hooks"),
        os.path.join(root, "adapters"),
    ]
    ships_dir = os.path.join(root, "brain", "subsystems")
    if os.path.isdir(ships_dir):
        for name in os.listdir(ships_dir):
            ag = os.path.join(ships_dir, name, "AGENTS.md")
            if os.path.isfile(ag):
                paths.append(ag)
    return [os.path.abspath(p) for p in paths]


def is_protected_target(path, protected):
    """True if `path` (relative or absolute) resolves under a protected path."""
    abs_path = os.path.abspath(path)
    for p in protected:
        if abs_path == p or abs_path.startswith(p + os.sep):
            return True
    return False


def _tokenize(command):
    """Split `command` into shell-style tokens, respecting quotes so a single
    quoted argument (e.g. a checkpoint note that merely *mentions* `rm` or a
    protected path in prose) stays one token instead of being torn into bare
    words. Returns None if the command can't be parsed with confidence (e.g.
    unbalanced quotes) — callers must treat that as "can't verify, don't
    block" (this guard is best-effort and must fail open on parse failure,
    never fail closed on prose it can't understand)."""
    try:
        return shlex.split(command)
    except ValueError:
        return None


def _token_mentions_protected(token, protected, root):
    """True only if `token` itself — not the raw command string — names (or
    is a path prefix of) a protected location. A long quoted sentence that
    happens to contain a protected path as a substring does NOT count; the
    token has to actually look like that path (relative or absolute)."""
    for p in protected:
        rel = os.path.relpath(p, root)
        if token == p or token == rel:
            return p
        if token.startswith(p + os.sep) or token.startswith(rel + os.sep):
            return p
    return None


def _segment(tokens):
    """Split `tokens` into command segments on shell control operators.

    Each control operator (`;`, `&&`, `||`, `|`, `&`) starts a fresh segment.
    A mutating verb's arguments must never be read from a different segment
    than the one it appears in — this is what stops a verb mentioned in a
    prior/unrelated segment (or in prose after it) from absorbing a
    protected path that actually belongs to a different command."""
    segments = [[]]
    for tok in tokens:
        if tok in _CONTROL_OPS:
            segments.append([])
        else:
            segments[-1].append(tok)
    return [seg for seg in segments if seg]


def _check(command, protected, root):
    tokens = _tokenize(command)
    if tokens is None:
        # Can't parse with confidence — best-effort guard fails open rather
        # than blocking prose it can't safely reason about.
        return True, ""

    # 1. Output redirections: dest is the token immediately after > or >>.
    for i, tok in enumerate(tokens):
        if tok in (">", ">>") and i + 1 < len(tokens):
            dest = tokens[i + 1]
            if is_protected_target(dest, protected):
                return False, f"blocked {tok} redirection to protected path: {dest}"

    # 2. Mutating commands whose ARGUMENTS (real tokens, not substrings of an
    #    unrelated quoted string) include a protected path. A verb only
    #    counts in command position (index 0) of its own segment, and its
    #    arguments are read from that same segment only — never from tokens
    #    that belong to a different command across a control operator.
    for seg in _segment(tokens):
        if not seg:
            continue
        head = seg[0]

        # Bare verbs: rm, rmdir, mv, truncate — exact token match at index 0.
        if head in _MUTATING_VERBS:
            for arg in seg[1:]:
                mentioned = _token_mentions_protected(arg, protected, root)
                if mentioned:
                    rel = os.path.relpath(mentioned, root)
                    return False, f"blocked {head} near protected path: {rel}"
        # git rm <path>
        if head == "git" and len(seg) > 1 and seg[1] == "rm":
            for arg in seg[2:]:
                mentioned = _token_mentions_protected(arg, protected, root)
                if mentioned:
                    rel = os.path.relpath(mentioned, root)
                    return False, f"blocked git rm near protected path: {rel}"
        # sed -i / -i.bak / --in-place <path>
        if head == "sed":
            has_inplace = any(
                a == "--in-place" or a == "-i" or (a.startswith("-i") and a != "-i")
                for a in seg[1:]
            )
            if has_inplace:
                for arg in seg[1:]:
                    mentioned = _token_mentions_protected(arg, protected, root)
                    if mentioned:
                        rel = os.path.relpath(mentioned, root)
                        return False, f"blocked sed -i near protected path: {rel}"

    return True, ""


def main():
    data = read_input()
    root = resolve_root()
    tool_name = data.get("tool_name", "")

    # Non-shell tools are not in scope.
    if tool_name not in SHELL_TOOLS:
        emit({"hook": "pre_exec_guard", "ok": True, "tool_name": tool_name})
        return

    tool_input = data.get("tool_input") or {}
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not command:
        emit({"hook": "pre_exec_guard", "ok": True, "tool_name": tool_name, "note": "no command string"})
        return

    protected = protected_paths(root)
    ok, reason = _check(command, protected, root)
    result = {"hook": "pre_exec_guard", "ok": ok, "tool_name": tool_name}
    if not ok:
        result["reason"] = reason
    else:
        result["note"] = "no protected-path mutation pattern matched"
    emit(result)


if __name__ == "__main__":
    main()
