#!/usr/bin/env python3
"""Seraph · import_boundaries — the hooks-layer import ratchet.

Rule (enforced by THIS hook, co-located so the rule ships with its
enforcement — lesson 73): the `hooks/` kernel may expose only the sanctioned
internal modules listed in `SANCTIONED_MODULES`, and no new private-symbol
edge, underscore-module edge, or cross-boundary edge (hooks/ <-> adapters/*/
hooks/) may appear without being declared in `hooks/import_debt.json`.

Three edges are violations unless declared:
  (a) a private symbol (name starting with `_`) imported from another local
      module;
  (b) an import of a local module whose name starts with `_` in the `hooks/`
      boundary that is not in `SANCTIONED_MODULES`;
  (c) an edge crossing the `hooks/` <-> `adapters/*/hooks/` boundary whose
      destination module is not in `SANCTIONED_MODULES`.

The hook does NOT distinguish imports inside try/except: an edge is an edge.
The try/except pattern *is* the evasion vector this ratchet exists to kill, so
wrapping an import in try/except never exempts it.

`hooks/import_debt.json` is the only escape hatch. The hook never auto-adds an
edge; an edge is declared by editing the file with `intentional: true` and a
`note`. An edge declared there that no longer exists in the graph is reported
as `stale_debt` (info) and is deleted in the same commit that removed it.

`ok:false` only when `import_debt.json` is invalid JSON, when a scanned file
cannot be parsed, or when a new undeclared edge exists (FAIL, not WARN — a
ratchet that only warns is the same trap as a guard degraded to a no-op).

Usage:
  bin/matrix hooks import_boundaries               # check (FAIL on new edges)
  bin/matrix hooks import_boundaries --emit-debt   # dump the AST graph for the mechanical seed
"""

import ast
import json
import os
import sys

from _common import emit, resolve_root

# Sanctioned internal modules of the hooks/ kernel. Adapters may import these
# across the boundary; everything else (a new `_foo.py`, or a public hook
# module imported from an adapter) must be declared as debt. Keep this list
# small and named — a broad allow-list would make the ratchet a linter.
SANCTIONED_MODULES = ("_common", "_flags", "_writer_lane", "_tokenizer")


def _iter_scan_files(root):
    """Yield (boundary, relpath, abspath) for every scanned Python file."""
    hooks_dir = os.path.join(root, "hooks")
    if os.path.isdir(hooks_dir):
        for name in sorted(os.listdir(hooks_dir)):
            if name.endswith(".py"):
                yield "hooks", os.path.join("hooks", name), os.path.join(hooks_dir, name)
    adapters_dir = os.path.join(root, "adapters")
    if os.path.isdir(adapters_dir):
        for target in sorted(os.listdir(adapters_dir)):
            hooks_sub = os.path.join(adapters_dir, target, "hooks")
            if not os.path.isdir(hooks_sub):
                continue
            for name in sorted(os.listdir(hooks_sub)):
                if name.endswith(".py"):
                    rel = os.path.join("adapters", target, "hooks", name)
                    yield f"adapter:{target}", rel, os.path.join(hooks_sub, name)


def _local_module_map(root):
    """Map module basename -> (boundary, relpath) for every scanned module."""
    out = {}
    for boundary, rel, _ in _iter_scan_files(root):
        mod = os.path.basename(rel)[:-3]
        out.setdefault(mod, (boundary, rel))
    return out


def _edge_key(src_rel, dst_rel, label):
    return f"{src_rel} -> {dst_rel}::{label}"


def _analyze_file(path, boundary, relpath, local_modules):
    """Return (edges, violations) for one scanned file.

    edges is the full set of local-import edge keys (needed for stale_debt);
    violations is a list of dicts for edges that break the ratchet rules.
    """
    edges = set()
    violations = []
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=path)

    def record(kind, edge, reason):
        violations.append({"edge": edge, "kind": kind, "reason": reason})

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if not node.module:
                continue
            info = _local_module_map_get(local_modules, node.module)
            if info is None:
                continue
            dst_boundary, dst_rel = info
            top = node.module.split(".")[0]
            for alias in node.names:
                label = alias.name
                if label == "*":
                    continue
                edge = _edge_key(relpath, dst_rel, label)
                edges.add(edge)
                if label.startswith("_"):
                    record("private_symbol", edge,
                           f"{relpath} imports private symbol {label} from {dst_rel}")
                if top.startswith("_") and dst_boundary == "hooks" and top not in SANCTIONED_MODULES:
                    record("underscore_module", edge,
                           f"{dst_rel} is an internal module outside the sanctioned set")
                if dst_boundary != boundary and top not in SANCTIONED_MODULES:
                    record("cross_boundary", edge,
                           f"{relpath} crosses into {dst_rel} outside the sanctioned set")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                modname = alias.name
                info = _local_module_map_get(local_modules, modname)
                if info is None:
                    continue
                dst_boundary, dst_rel = info
                edge = _edge_key(relpath, dst_rel, modname)
                edges.add(edge)
                top = modname.split(".")[0]
                if top.startswith("_") and dst_boundary == "hooks" and top not in SANCTIONED_MODULES:
                    record("underscore_module", edge,
                           f"{dst_rel} is an internal module outside the sanctioned set")
                if dst_boundary != boundary and top not in SANCTIONED_MODULES:
                    record("cross_boundary", edge,
                           f"{relpath} crosses into {dst_rel} outside the sanctioned set")
    return edges, violations


def _local_module_map_get(local_modules, modname):
    """Resolve a (possibly dotted) import name to its local module info."""
    if not modname:
        return None
    return local_modules.get(modname.split(".")[0])


def check_boundaries(root):
    """Return the ratchet result dict. Never calls sys.exit (caller emits).

    ok:false when import_debt.json is invalid JSON, a scanned file cannot be
    parsed, or a new undeclared edge exists. stale_debt is informational and
    never fails the check.
    """
    local_modules = _local_module_map(root)
    all_edges = set()
    all_violations = []
    unparseable = []
    for boundary, rel, abspath in _iter_scan_files(root):
        try:
            edges, violations = _analyze_file(abspath, boundary, rel, local_modules)
        except (OSError, SyntaxError) as exc:
            unparseable.append(f"{rel}: {exc}")
            continue
        all_edges.update(edges)
        all_violations.extend(violations)

    # Deduplicate violations by edge (first reason wins).
    seen = {}
    for v in all_violations:
        seen.setdefault(v["edge"], v)
    violations = list(seen.values())

    debt_path = os.path.join(root, "hooks", "import_debt.json")
    declared = {}
    readable = True
    debt_error = ""
    if os.path.isfile(debt_path):
        try:
            with open(debt_path, encoding="utf-8") as fh:
                raw = json.load(fh)
            declared = (raw or {}).get("edges") or {}
            if not isinstance(declared, dict):
                raise ValueError("'edges' must be an object")
        except (ValueError, OSError) as exc:
            readable = False
            debt_error = f"hooks/import_debt.json is not valid JSON: {exc}"

    declared_keys = set(declared)
    new_edges = [v for v in violations if v["edge"] not in declared_keys]
    stale_debt = [
        {"edge": k, "note": (declared.get(k) or {}).get("note", "")}
        for k in sorted(declared_keys - all_edges)
    ]

    errors = []
    if not readable:
        errors.append(debt_error)
    for e in new_edges:
        errors.append(f"new import edge not declared: {e['edge']} ({e['kind']})")
    for u in unparseable:
        errors.append(f"cannot parse: {u}")

    ok = readable and not errors
    return {
        "hook": "import_boundaries",
        "ok": ok,
        "errors": errors,
        "new_edges": new_edges,
        "violations": violations,
        "stale_debt": stale_debt,
        "unparseable": unparseable,
        "graph_edges": len(all_edges),
        "declared": len(declared_keys),
        "import_debt_path": debt_path,
        "readable": readable,
    }


def main():
    emit_debt = "--emit-debt" in sys.argv
    root = resolve_root()
    result = check_boundaries(root)
    result["mode"] = "emit-debt" if emit_debt else "check"
    if emit_debt:
        result["ok"] = True
        result["note"] = (
            "emit-debt: graph dump for the mechanical seed. Annotate each "
            "violation with intentional:true + note in hooks/import_debt.json."
        )
    emit(result)


if __name__ == "__main__":
    main()
