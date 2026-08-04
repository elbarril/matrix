"""Seraph — shared helpers for portable enforcement hooks.

Hooks follow a JSON in / JSON out contract and are CLI-agnostic. Input is read
from argv[1] (a JSON string) or stdin; output is a JSON object on stdout. Exit
code is 0 on PASS, 1 on BLOCK/FAIL. No third-party dependencies.
"""

import fnmatch
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


def _load_registry(root):
    """Read .registry.json from the Matrix root, returning a dict on failure."""
    path = os.path.join(root, ".registry.json")
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (ValueError, OSError):
        return {}


def _registry_project(registry, name):
    """Find a project entry by name in a loaded registry dict."""
    if not isinstance(registry, dict):
        return None
    for proj in registry.get("projects", []):
        if proj.get("name") == name:
            return proj
    return None


def _load_yaml(path):
    """Load a YAML file, falling back to empty dict if yaml is unavailable."""
    try:
        import yaml
        with open(path, encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
    except Exception:
        return {}


def resolve_bound_target(project_name, root=None):
    """Resolve the bound_target for a project from .registry.json.

    Esta lectura de bound_target desde .registry.json es una segunda implementación
    en paralelo a la resolución equivalente en bash dentro de bin/matrix (jq sobre
    el mismo campo). Si bin/matrix cambia el shape de .registry.json o la semántica
    de bound_target, este resolutor debe actualizarse en el mismo commit.

    Falls back to "devin" when bound_target is missing or null, matching
    registry_bound_target() in bin/matrix.
    """
    if root is None:
        root = resolve_root()
    registry = _load_registry(root)
    proj = _registry_project(registry, project_name)
    if not proj:
        return None
    target = proj.get("bound_target")
    if not target or target == "null":
        target = "devin"
    return target


def adapter_gitignore_entries(target, root=None):
    """Return the gitignore_entries list declared for an adapter target.

    Reads adapters/<target>/adapter.yaml and extracts binding.gitignore_entries.
    Returns None if the file is missing or the value is not a non-empty list
    of strings.
    """
    if root is None:
        root = resolve_root()
    path = os.path.join(root, "adapters", target, "adapter.yaml")
    cfg = _load_yaml(path)
    if not isinstance(cfg, dict):
        return None
    binding = cfg.get("binding")
    if not isinstance(binding, dict):
        return None
    entries = binding.get("gitignore_entries")
    if not isinstance(entries, list) or not all(
        isinstance(item, str) and item for item in entries
    ):
        return None
    return entries


def entry_covered(entry, gitignore_lines):
    """Return True if an adapter gitignore entry is covered by real .gitignore lines.

    Ignores blank lines and comments, parses positive and negative rules,
    and matches the entry with fnmatch (including a trailing-slash variant for
    directory rules).
    """
    positives, negatives = [], []
    for ln in gitignore_lines:
        raw = (ln.split("#", 1)[0]).strip()
        if not raw:
            continue
        if raw.startswith("!"):
            negatives.append(raw[1:])
        else:
            positives.append(raw)

    def matches(pat):
        return fnmatch.fnmatch(entry, pat) or fnmatch.fnmatch(entry + "/", pat)

    for pat in positives:
        if matches(pat):
            # Re-inclusion cancels the positive match.
            for neg in negatives:
                if matches(neg):
                    return False
            return True
    return False


def gitignore_drift(project_name, root=None):
    """Compare adapter gitignore_entries against the real .gitignore of a project.

    Returns a dict when the project exists and its adapter binding can be read:
        {
            "applicable": True,
            "project": project_name,
            "project_path": "...",
            "target": "...",
            "entries": [...],   # adapter-declared entries
            "missing": [...],  # entries not covered by the real .gitignore
            "ok": True/False,
        }

    Returns None when the project is not in .registry.json, its path does not
    exist, or the adapter binding cannot be read. A missing .gitignore file is
    treated as the limiting case of "all adapter entries missing" (every entry
    appears in missing).
    """
    if root is None:
        root = resolve_root()
    registry = _load_registry(root)
    proj = _registry_project(registry, project_name)
    if not proj:
        return None
    project_path = proj.get("path")
    if not project_path or not os.path.isdir(project_path):
        return None
    target = resolve_bound_target(project_name, root=root)
    if not target:
        return None
    entries = adapter_gitignore_entries(target, root=root)
    if entries is None:
        return None

    gi_path = os.path.join(project_path, ".gitignore")
    lines = []
    if os.path.isfile(gi_path):
        try:
            with open(gi_path, encoding="utf-8") as fh:
                lines = fh.read().splitlines()
        except OSError:
            lines = []

    missing = [e for e in entries if not entry_covered(e, lines)]
    return {
        "applicable": True,
        "project": project_name,
        "project_path": project_path,
        "target": target,
        "entries": entries,
        "missing": missing,
        "ok": not missing,
    }


def emit(result):
    """Print the result JSON and exit with the right code."""
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result.get("ok") else 1)
