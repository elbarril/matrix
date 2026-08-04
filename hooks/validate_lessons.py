#!/usr/bin/env python3
"""Seraph · validate_lessons — sanity-check the lessons archive.

Parses `brain/data/lessons.md` (the core pool) and every project lesson file
under `brain/data/lessons/*.md` (excluding `_template.md`) for numbered
lesson headers (`^\\d+\\.\\s`, with or without a bold title after the number)
and reports:

  - duplicate numbers within the same file (real error — flips `ok` to False).
  - numbering gaps that are not explained by a placeholder line mentioning
    the missing number, e.g. `31. (número retirado — ...)` (informational —
    does NOT flip `ok`; a documented placeholder for a retired/moved number
    is intentional per `lessons.md`'s own header note).
  - the core file (`lessons.md`) growing past a soft threshold, either in
    raw size (~40 KB) or in active (non-placeholder) numbered entries (~30)
    (informational — does NOT flip `ok`; just a nudge to review/split).

Severity is intentionally asymmetric: only real duplicates are a hard
warn-level failure (`ok: false`) because two lessons sharing one identifier
breaks the "number is a stable id" invariant lessons.md itself declares.
Gaps and size are advisory since a documented gap or a big-but-organized
file is not, by itself, broken.

Usage:
  python3 hooks/validate_lessons.py
  bin/matrix hooks validate_lessons
"""

import os
import re

from _common import emit, read_input, resolve_root


HEADER_RE = re.compile(r"^(\d+)\.\s+(.*)$")
CORE_SIZE_BYTES_THRESHOLD = 40 * 1024
CORE_ACTIVE_ENTRIES_THRESHOLD = 30


def lesson_paths(root):
    """Yield (relative_path, absolute_path) for the core file + project lesson files."""
    core = os.path.join(root, "brain", "data", "lessons.md")
    if os.path.isfile(core):
        yield os.path.relpath(core, root), core
    lessons_dir = os.path.join(root, "brain", "data", "lessons")
    if os.path.isdir(lessons_dir):
        for name in sorted(os.listdir(lessons_dir)):
            if not name.endswith(".md") or name == "_template.md":
                continue
            path = os.path.join(lessons_dir, name)
            if os.path.isfile(path):
                yield os.path.relpath(path, root), path


def _is_placeholder(header_text):
    """A placeholder header's content (after an optional bold marker) starts with '('."""
    content = header_text.lstrip()
    if content.startswith("**"):
        content = content[2:].lstrip()
    return content.startswith("(")


def parse_headers(text):
    """Return a list of {line, number, placeholder} for each numbered header line."""
    headers = []
    for line_no, line in enumerate(text.splitlines(), 1):
        m = HEADER_RE.match(line)
        if not m:
            continue
        headers.append(
            {
                "line": line_no,
                "number": int(m.group(1)),
                "placeholder": _is_placeholder(m.group(2)),
            }
        )
    return headers


def find_duplicates(rel_path, headers):
    """Return one entry per number that appears on more than one header line."""
    by_number = {}
    for h in headers:
        by_number.setdefault(h["number"], []).append(h["line"])
    duplicates = []
    for number, lines in sorted(by_number.items()):
        if len(lines) > 1:
            duplicates.append({"file": rel_path, "number": number, "lines": lines})
    return duplicates


def find_unexplained_gaps(rel_path, headers, text):
    """Return gaps in the numbering that no placeholder mention explains.

    A gap is "explained" if the raw file text contains the literal pattern
    `"<N>. ("` anywhere (the convention already used in lessons.md for
    retired/moved numbers like 31 and 33), even if that mention is not a
    header of its own (e.g. referenced inline from a neighboring entry).
    """
    numbers = sorted({h["number"] for h in headers})
    if len(numbers) < 2:
        return []
    gaps = []
    present = set(numbers)
    lo, hi = numbers[0], numbers[-1]
    for n in range(lo, hi + 1):
        if n in present:
            continue
        if f"{n}. (" in text:
            continue
        gaps.append({"file": rel_path, "number": n})
    return gaps


def _size_warning(root, rel_path, abs_path, headers):
    """Advisory message if the core lessons file is past the soft threshold."""
    if rel_path != os.path.join("brain", "data", "lessons.md"):
        return None
    size = os.path.getsize(abs_path)
    active = sum(1 for h in headers if not h["placeholder"])
    reasons = []
    if size > CORE_SIZE_BYTES_THRESHOLD:
        reasons.append(f"{size} bytes (> {CORE_SIZE_BYTES_THRESHOLD})")
    if active > CORE_ACTIVE_ENTRIES_THRESHOLD:
        reasons.append(f"{active} active entries (> {CORE_ACTIVE_ENTRIES_THRESHOLD})")
    if not reasons:
        return None
    return (
        f"{rel_path} is past the soft review threshold: "
        + "; ".join(reasons)
        + ". Consider reviewing/splitting."
    )


def validate(_data):
    root = resolve_root()
    files = []
    duplicates = []
    unexplained_gaps = []
    size_warning = None

    for rel_path, abs_path in lesson_paths(root):
        files.append(rel_path)
        with open(abs_path, encoding="utf-8") as fh:
            text = fh.read()
        headers = parse_headers(text)
        duplicates.extend(find_duplicates(rel_path, headers))
        unexplained_gaps.extend(find_unexplained_gaps(rel_path, headers, text))
        warning = _size_warning(root, rel_path, abs_path, headers)
        if warning:
            size_warning = warning

    return {
        "hook": "validate_lessons",
        "ok": not duplicates,
        "files": files,
        "duplicates": duplicates,
        "unexplained_gaps": unexplained_gaps,
        "size_warning": size_warning,
    }


def main():
    emit(validate(read_input()))


if __name__ == "__main__":
    main()
