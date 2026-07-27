#!/usr/bin/env python3
"""Seraph · validate_layer2 — enforce the Layer-2 CLI-neutrality rule.

Usage:
  python3 hooks/validate_layer2.py
  bin/matrix hooks validate_layer2
"""

import os
import re
from pathlib import Path

from _common import emit, read_input, resolve_root


DENYLIST = [
    (re.compile(r"\bDevin\b", re.IGNORECASE), "names the CLI 'Devin'"),
    (re.compile(r"\bClaude Code\b", re.IGNORECASE), "names the CLI 'Claude Code'"),
    (re.compile(r"\brun_subagent\b", re.IGNORECASE), "Devin-native tool call `run_subagent`"),
    (re.compile(r"\bread_subagent\b", re.IGNORECASE), "Devin-native tool call `read_subagent`"),
    (re.compile(r"\bsubagent_general\b", re.IGNORECASE), "Devin-native fallback profile name"),
    (re.compile(r"\bsubagent_explore\b", re.IGNORECASE), "Devin-native fallback profile name"),
    (re.compile(r"\bask_user_question\b", re.IGNORECASE), "Devin-native tool call `ask_user_question`"),
    (re.compile(r"\brun_command\b", re.IGNORECASE), "Devin-native tool call `run_command` (distinct from the capability `run-command`)"),
    (re.compile(r"\bfind_by_name\b", re.IGNORECASE), "Devin-native tool call `find_by_name`"),
    (re.compile(r"\bfind_file_by_name\b", re.IGNORECASE), "Devin-native tool call `find_file_by_name`"),
    (re.compile(r"\bgrep_search\b", re.IGNORECASE), "Devin-native tool call `grep_search`"),
    (re.compile(r"\bcodebase_search\b", re.IGNORECASE), "Devin-native tool call `codebase_search`"),
    (re.compile(r"\bread_file\b", re.IGNORECASE), "Devin-native tool call `read_file`"),
    (re.compile(r"\bmulti_edit\b", re.IGNORECASE), "Devin-native tool call `multi_edit`"),
    (re.compile(r"\bmcp__[a-zA-Z0-9_-]+\b", re.IGNORECASE), "Devin-native MCP tool naming convention"),
    (re.compile(r"\bmax[-_]nesting\b", re.IGNORECASE), "Devin-only frontmatter field `max-nesting`"),
    (re.compile(r"--target=devin\b", re.IGNORECASE), "hardcoded Devin target value (should be `--target=<cli>`)"),
    (re.compile(r"\bsessions\.db\b", re.IGNORECASE), "Devin-internal session-store artifact"),
    (re.compile(r"\bis_background\b", re.IGNORECASE), "Devin-specific execution flag"),
    (re.compile(r"--permission-mode\s+dangerous", re.IGNORECASE), "Devin-specific CLI flag"),
    (re.compile(r"\bsubagents\.mdx\b", re.IGNORECASE), "Devin documentation filename"),
]
ESCAPE_INLINE = "<!-- adapter-note"
ESCAPE_BEGIN = re.compile(r"<!--\s*adapter-note:begin\b")
ESCAPE_END = re.compile(r"<!--\s*adapter-note:end\s*-->")


EXCLUDE_GLOBS = [
    "brain/output/**",
    "brain/state/**",
    "brain/subsystems/*/corpus/**",
]


def is_excluded(rel_path):
    """Return True if rel_path matches a glob-exclude pattern."""
    parts = Path(rel_path).parts
    if len(parts) >= 2 and parts[0] == "brain" and parts[1] in ("output", "state"):
        return True
    if (
        len(parts) >= 4
        and parts[0] == "brain"
        and parts[1] == "subsystems"
        and parts[3] == "corpus"
    ):
        return True
    return False


def markdown_paths(root):
    """Yield the scoped Layer-2 markdown files in stable order."""
    agents = os.path.join(root, "AGENTS.md")
    if os.path.isfile(agents) and not is_excluded("AGENTS.md"):
        yield agents
    brain = os.path.join(root, "brain")
    for dirpath, dirnames, filenames in os.walk(brain):
        # Prune excluded directories to avoid walking them at all.
        rel_dir = os.path.relpath(dirpath, root)
        pruned = []
        for d in sorted(dirnames):
            child_rel = os.path.join(rel_dir, d) if rel_dir != "." else d
            if is_excluded(child_rel + "/"):
                continue
            pruned.append(d)
        dirnames[:] = pruned
        for filename in sorted(filenames):
            if filename.endswith(".md"):
                path = os.path.join(dirpath, filename)
                rel = os.path.relpath(path, root)
                if not is_excluded(rel):
                    yield path


def check_file(root, path):
    """Return all CLI-neutrality errors for one markdown file."""
    errors = []
    in_escaped_block = False
    begin_line = None
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    relative = os.path.relpath(path, root)

    for line_no, line in enumerate(lines, 1):
        if ESCAPE_BEGIN.search(line):
            in_escaped_block = True
            begin_line = line_no
            continue
        if ESCAPE_END.search(line):
            in_escaped_block = False
            begin_line = None
            continue
        if in_escaped_block or ESCAPE_INLINE in line:
            continue
        for pattern, reason in DENYLIST:
            if pattern.search(line):
                errors.append(f"{relative}:{line_no}: {reason} — {line.strip()[:100]}")

    if in_escaped_block:
        errors.append(
            f"{relative}:{begin_line}: adapter-note:begin has no matching :end before EOF"
        )
    return errors


def validate(_data):
    root = resolve_root()
    errors = []
    files = []
    for path in markdown_paths(root):
        files.append(os.path.relpath(path, root))
        errors.extend(check_file(root, path))
    return {"hook": "validate_layer2", "ok": not errors, "files": files, "errors": errors}


def main():
    emit(validate(read_input()))


if __name__ == "__main__":
    main()
