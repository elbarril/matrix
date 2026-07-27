"""Seraph — shared helpers for portable enforcement hooks.

Hooks follow a JSON in / JSON out contract and are CLI-agnostic. Input is read
from argv[1] (a JSON string) or stdin; output is a JSON object on stdout. Exit
code is 0 on PASS, 1 on BLOCK/FAIL. No third-party dependencies.
"""

import json
import os
import sys


def resolve_root():
    """Resolve the Matrix root: $MATRIX_ROOT, else walk up to brain/ + AGENTS.md."""
    env = os.environ.get("MATRIX_ROOT")
    if env and os.path.isdir(os.path.join(env, "brain")):
        return env
    d = os.path.dirname(os.path.abspath(__file__))
    d = os.path.dirname(d)  # hooks/ -> root
    cur = d
    while cur != "/":
        if os.path.isdir(os.path.join(cur, "brain")) and os.path.isfile(
            os.path.join(cur, "AGENTS.md")
        ):
            return cur
        cur = os.path.dirname(cur)
    return d


def parse_scalar_list(raw):
    """Parse a scalar YAML-style inline list."""
    v = raw.split("#", 1)[0].strip()
    if v.startswith("[") and v.endswith("]"):
        v = v[1:-1]
    if not v:
        return []
    return [item.strip().strip('"').strip("'") for item in v.split(",") if item.strip()]


def parse_frontmatter(path):
    """Return a dict of the YAML frontmatter in a markdown file."""
    data = {}
    if not os.path.isfile(path):
        return data
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    if not lines or lines[0].strip() != "---":
        return data
    for ln in lines[1:]:
        if ln.strip() == "---":
            break
        if ":" not in ln:
            continue
        k, v = ln.split(":", 1)
        k = k.strip()
        v = v.strip()
        if v.startswith("["):
            data[k] = parse_scalar_list(v)
        else:
            data[k] = v.strip('"').strip("'")
    return data


def read_input():
    """Read hook input as a dict from argv[1] (JSON) or stdin. Empty -> {}."""
    raw = ""
    if len(sys.argv) > 1 and sys.argv[1].strip():
        raw = sys.argv[1]
    elif not sys.stdin.isatty():
        try:
            raw = sys.stdin.read()
        except Exception:
            raw = ""
    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return {}


def current_session_id(root=None):
    """Return the synthetic session id from the marker file, or None."""
    if root is None:
        root = resolve_root()
    marker = os.path.join(root, "brain", "state", ".current-hook-session")
    if not os.path.isfile(marker):
        return None
    try:
        with open(marker, encoding="utf-8") as fh:
            sid = fh.read().strip()
        return sid or None
    except OSError:
        return None


def emit(result):
    """Print the result JSON and exit with the right code."""
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result.get("ok") else 1)
