#!/usr/bin/env python3
"""Seraph · pre_activation_check — the guardian at the gate.

Validates prerequisites before any agent acts: contract present, config valid,
the roster intact, and the state directory ready. Halts (exit 1) with a clear
list of what is missing.

Usage:
  python3 hooks/pre_activation_check.py '{"project":"mck"}'
  bin/matrix hooks pre_activation_check
"""

import os

from _common import (
    _load_registry,
    _registry_project,
    emit,
    exclude_drift,
    read_input,
    resolve_bound_target,
    resolve_root,
)

try:
    from validate_ship import validate as validate_ship
except Exception:
    validate_ship = None

try:
    from install_integrity_check import check_install_integrity
except Exception:
    check_install_integrity = None

ROSTER = ["neo", "oracle", "morpheus", "architect", "trinity", "smith"]

# Infrastructure agents that deliberately live as installable subagent files in
# brain/agents/ but are NOT subject to roster discipline (see
# brain/data/contract-catalog.md "Supporting cast" — retire-one-to-add-one
# applies only to ROSTER above).
# docs/SYSTEM_TRUTH.md lists these alongside the roster with their own description.
# Add a name here ONLY if brain/data/contract-catalog.md already documents it as
# supporting-cast infrastructure — never to silently permit an undocumented new file.
SUPPORTING_AGENTS = ["lock"]


def _workspace_warm_projects(root):
    """Return (name, path) tuples from brain/state/workspace.yaml without PyYAML."""
    path = os.path.join(root, "brain", "state", "workspace.yaml")
    if not os.path.isfile(path):
        return []
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return []
    projects = []
    current_name = None
    for raw in lines:
        stripped = raw.strip()
        if stripped.startswith("- name:"):
            current_name = stripped.split(":", 1)[1].strip().strip('"').strip("'")
        elif stripped.startswith("path:") and current_name is not None:
            p = stripped.split(":", 1)[1].strip().strip('"').strip("'")
            projects.append((current_name, p))
            current_name = None
    return projects


def _brain_symlink_error(project_path, brain_dir, brain_real):
    """Return a human error string if _brain is missing or points elsewhere."""
    brain_link = os.path.join(project_path, "_brain")
    if not os.path.lexists(brain_link):
        return None
    if not os.path.islink(brain_link):
        return "_brain exists but is not a symlink"
    actual = os.path.realpath(brain_link)
    if actual != brain_real:
        target = os.readlink(brain_link)
        if not os.path.exists(brain_link):
            return f"_brain is a dangling symlink (points to {target}); should point to {brain_dir}"
        return f"_brain points to {target}; should point to {brain_dir}"
    return None


def main():
    data = read_input()
    root = resolve_root()
    checks, errors = [], []

    def check(label, ok, detail=""):
        checks.append({"check": label, "ok": bool(ok), "detail": "" if ok else detail})
        if not ok:
            errors.append(label + (f": {detail}" if detail else ""))

    # Contract
    check("contract_present", os.path.isfile(os.path.join(root, "AGENTS.md")),
          "AGENTS.md missing at root")

    # Config (any of project _brain/config or brain/config)
    cfg = os.path.join(root, "brain", "config.yaml")
    check("config_present", os.path.isfile(cfg), f"missing {cfg}")
    if os.path.isfile(cfg):
        with open(cfg, encoding="utf-8") as fh:
            txt = fh.read()
        check("config_has_user", "user:" in txt, "config.yaml has no 'user:'")
        check("config_has_language", "language:" in txt, "config.yaml has no 'language:'")

    # Roster intact
    agents_dir = os.path.join(root, "brain", "agents")
    missing = [a for a in ROSTER if not os.path.isfile(os.path.join(agents_dir, a + ".md"))]
    unexpected = []
    if os.path.isdir(agents_dir):
        unexpected = sorted(
            f for f in os.listdir(agents_dir)
            if f.endswith(".md") and f[:-3] not in ROSTER + SUPPORTING_AGENTS
        )
    roster_detail_parts = []
    if missing:
        roster_detail_parts.append("missing agents: " + ", ".join(missing))
    if unexpected:
        roster_detail_parts.append("unexpected agent files: " + ", ".join(unexpected))
    check("roster_intact", not missing and not unexpected, "; ".join(roster_detail_parts))

    # State directory
    state = os.path.join(root, "brain", "state")
    check("state_dir", os.path.isdir(state), f"missing {state}")

    # Brain symlink integrity for all active / local / requested projects
    brain_dir = os.path.join(root, "brain")
    brain_real = os.path.realpath(brain_dir)
    registry = _load_registry(root)
    candidate_paths = {}
    for proj in (registry or {}).get("projects", []):
        if proj.get("type") == "local":
            path = proj.get("path")
            if path and os.path.isdir(path):
                candidate_paths.setdefault(path, proj.get("name"))
    for name, path in _workspace_warm_projects(root):
        if path and os.path.isdir(path):
            candidate_paths.setdefault(path, name)
    requested = data.get("project")
    if requested:
        req_proj = _registry_project(registry, requested)
        if req_proj:
            req_path = req_proj.get("path")
            if req_path and os.path.isdir(req_path):
                candidate_paths.setdefault(req_path, requested)
    broken = [
        f"{name}: {err}"
        for path, name in candidate_paths.items()
        if (err := _brain_symlink_error(path, brain_dir, brain_real))
    ]
    if broken:
        detail = (
            "broken _brain symlinks in " + "; ".join(broken) + ". "
            "Fix with `bin/matrix select <name>` or recreate with "
            f"`ln -sfn {brain_dir} <project>/_brain`"
        )
    else:
        detail = ""
    check("brain_symlinks_intact", not broken, detail)

    # Ship validation (delegated, generic)
    if data.get("ship") and validate_ship:
        v = validate_ship(data)
        checks.extend(v.get("checks", []))
        if not v.get("ok"):
            errors.extend(v.get("errors", []))

    # Install integrity (delegated, generic — opt-in per adapter.yaml)
    if check_install_integrity:
        target = data.get("target") or resolve_bound_target(data.get("project")) or "devin"
        ii = check_install_integrity(target, root)
        if ii.get("applicable"):
            checks.extend(ii.get("checks", []))
            if not ii.get("ok"):
                errors.extend(ii.get("errors", []))

    # Exclude drift — informational only, warn-only. The result lives in its own
    # field and never feeds into the global `ok` of the hook.
    drift = None
    if data.get("project"):
        drift = exclude_drift(data["project"], root=root)

    result = {
        "hook": "pre_activation_check",
        "ok": not errors,
        "project": data.get("project"),
        "ship": data.get("ship"),
        "root": root,
        "checks": checks,
        "errors": errors,
        "exclude_drift": drift,
    }
    emit(result)


if __name__ == "__main__":
    main()
