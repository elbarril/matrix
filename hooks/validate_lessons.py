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
    raw size (~40 KB) or in active (non-placeholder) numbered entries (~60)
    (informational — does NOT flip `ok`; just a nudge to review/split).
  - the core file (`lessons.md`) growing past the mechanical hard cap
    (>64 KB raw or >100 active numbered entries) — flips `ok` to False via
    the `hard_cap` field, reported alongside the advisory `size_warning`.

Severity is intentionally asymmetric: `ok: false` now means one of two
distinct classes of failure — real duplicates (corrupt: two lessons sharing
one identifier breaks the "number is a stable id" invariant lessons.md itself
declares) or the hard cap exceeded (too large: the archive can no longer be
trusted to stay lean). The hard cap is WARN-only through the boot channel: it
reports `ok: false` so the master sees it, but it never blocks activation.
Gaps and the soft size threshold remain advisory since a documented gap or a
big-but-organized file is not, by itself, broken.

Usage:
  python3 hooks/validate_lessons.py
  bin/matrix hooks validate_lessons
"""

import os
import re

from _common import emit, read_input, resolve_root


HEADER_RE = re.compile(r"^(\d+)\.\s+(.*)$")
CORE_SIZE_BYTES_THRESHOLD = 40 * 1024
# Números estables no reutilizables → el conteo solo crece; 60 = margen post-E1 (pointer format) + retiro 2026-09-07 (43 activas).
CORE_ACTIVE_ENTRIES_THRESHOLD = 60
# Hard cap mecánico: segunda clase de ok:false ("demasiado grande"). ~4x y ~2.3x
# sobre el estado actual post-slim (14.6 KB, 43 activas); subirlos exige cadena
# completa porque lessons son never-small por política.
CORE_HARD_CAP_BYTES = 64 * 1024
CORE_HARD_CAP_ACTIVE = 100
CORE_ENTRY_MAX_LINES = 6
CORE_ENTRY_MAX_BYTES = 900


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


def _hard_cap(rel_path, abs_path, headers):
    """Mechanical hard cap for the core lessons file (second class of ok:false).

    Returns {"exceeded": bool, "reasons": [...]}. Unlike the advisory
    size_warning this flips `ok` to False, but it is still WARN-only through
    the boot channel — it never blocks activation by itself.
    """
    if rel_path != os.path.join("brain", "data", "lessons.md"):
        return {"exceeded": False, "reasons": []}
    size = os.path.getsize(abs_path)
    active = sum(1 for h in headers if not h["placeholder"])
    reasons = []
    if size > CORE_HARD_CAP_BYTES:
        reasons.append(f"{size} bytes (> {CORE_HARD_CAP_BYTES} hard cap)")
    if active > CORE_HARD_CAP_ACTIVE:
        reasons.append(f"{active} active entries (> {CORE_HARD_CAP_ACTIVE} hard cap)")
    return {"exceeded": bool(reasons), "reasons": reasons}


def find_long_entries(rel_path, headers, text):
    """Advisory list of active core lessons whose body between its header and
    the next lesson/section header exceeds CORE_ENTRY_MAX_LINES lines or
    CORE_ENTRY_MAX_BYTES bytes — the mechanical proxy for "this looks like
    prose, not a short pointer". The body stops at the next numbered lesson
    header OR the next markdown section header (e.g. the retirement register
    under `## Números retirados ...`), so a trailing section is never counted
    as the last lesson's body. Core lessons.md only; does NOT flip ok
    (spec Q2-D 1.e)."""
    if rel_path != os.path.join("brain", "data", "lessons.md"):
        return []
    lines = text.splitlines()
    entries = []
    for i, h in enumerate(headers):
        if h["placeholder"]:
            continue
        start = h["line"]  # 1-based header line
        next_line = len(lines) + 1
        for j in range(start + 1, len(lines) + 1):
            if HEADER_RE.match(lines[j - 1]) or re.match(r"^#{1,6}\s", lines[j - 1]):
                next_line = j
                break
        body = lines[start:next_line - 1]
        body_lines = len(body)
        body_bytes = len("\n".join(body).encode("utf-8"))
        if body_lines > CORE_ENTRY_MAX_LINES or body_bytes > CORE_ENTRY_MAX_BYTES:
            entries.append(
                {
                    "file": rel_path,
                    "number": h["number"],
                    "lines": body_lines,
                    "bytes": body_bytes,
                }
            )
    return entries


def validate(_data):
    root = resolve_root()
    files = []
    duplicates = []
    unexplained_gaps = []
    long_entries = []
    size_warning = None
    hard_cap = {"exceeded": False, "reasons": []}

    for rel_path, abs_path in lesson_paths(root):
        files.append(rel_path)
        with open(abs_path, encoding="utf-8") as fh:
            text = fh.read()
        headers = parse_headers(text)
        duplicates.extend(find_duplicates(rel_path, headers))
        unexplained_gaps.extend(find_unexplained_gaps(rel_path, headers, text))
        long_entries.extend(find_long_entries(rel_path, headers, text))
        warning = _size_warning(root, rel_path, abs_path, headers)
        if warning:
            size_warning = warning
        cap = _hard_cap(rel_path, abs_path, headers)
        if cap["exceeded"]:
            hard_cap = cap

    return {
        "hook": "validate_lessons",
        "ok": not duplicates and not hard_cap["exceeded"],
        "files": files,
        "duplicates": duplicates,
        "unexplained_gaps": unexplained_gaps,
        "long_entries": long_entries,
        "size_warning": size_warning,
        "hard_cap": hard_cap,
    }


def main():
    emit(validate(read_input()))


if __name__ == "__main__":
    main()
