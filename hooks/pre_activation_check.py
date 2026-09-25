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
import subprocess
import time

from _common import (
    ROSTER,
    SUPPORTING_AGENTS,
    _load_registry,
    emit,
    ledger_tail_events,
    model_override_active,
    read_input,
    resolve_bound_target,
    resolve_root,
    snapshot_window,
    ttl_scan,
)
from import_boundaries import check_boundaries

try:
    from _flags import DEFAULTS as _FLAGS_DEFAULTS
    from _flags import get_flag as _get_flag
    from _flags import load_status as _flags_load_status
except Exception:
    _FLAGS_DEFAULTS = {}
    _get_flag = None
    _flags_load_status = None

try:
    from validate_ship import validate as validate_ship
except Exception:
    validate_ship = None

try:
    from install_integrity_check import check_install_integrity, model_drift
except Exception:
    check_install_integrity = None
    model_drift = None

try:
    from validate_layer2 import validate as validate_layer2
except Exception:
    validate_layer2 = None

try:
    from validate_lessons import validate as validate_lessons
except Exception:
    validate_lessons = None

try:
    from surface_budget import validate as validate_surface_budget
except Exception:
    validate_surface_budget = None

try:
    import the_source as the_source_mod
except Exception:
    the_source_mod = None

def _flags_value(name):
    """Effective boolean of a feature flag; falls back to the loader default."""
    if _get_flag is None:
        return bool(_FLAGS_DEFAULTS.get(name, False))
    try:
        return bool(_get_flag(name)["value"])
    except Exception:
        return bool(_FLAGS_DEFAULTS.get(name, False))


def _safe_config_text(path):
    """Return the raw text of a config file, or None when unreadable (D1).

    Guards the config text read so a binary/non-UTF-8 config is a visible
    flags_config warn, never a traceback (lesson 71). When None, the text-based
    checks (config_has_user/config_has_language) are skipped — a corrupt config
    must not behave differently for a reason that is only its encoding.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except (OSError, UnicodeDecodeError, ValueError):
        return None


def _git_exclude_path(project_path):
    """Return the absolute .git/info/exclude path for a project, or None."""
    try:
        proc = subprocess.run(
            ["git", "-C", project_path, "rev-parse", "--git-path", "info/exclude"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if proc.returncode != 0:
            return None
        p = proc.stdout.strip()
        if not p:
            return None
        if not os.path.isabs(p):
            p = os.path.join(project_path, p)
        return p
    except Exception:
        return None


def _legacy_binding_artifacts(root, registry, artifacts_on):
    """Return {project: [artifact labels]} for projects with legacy no-binding
    leftovers. With binding.artifacts=on those files are expected (only a
    broken `_brain` symlink is still a WARN). Warn-only; never blocks."""
    out = {}
    brain_real = os.path.realpath(os.path.join(root, "brain"))
    for proj in (registry or {}).get("projects", []):
        if proj.get("type") != "local":
            continue
        name = proj.get("name")
        path = proj.get("path")
        if not name or not path or not os.path.isdir(path):
            continue
        found = []
        brain_link = os.path.join(path, "_brain")
        if os.path.lexists(brain_link):
            if os.path.islink(brain_link):
                actual = os.path.realpath(brain_link)
                if actual == brain_real:
                    if not artifacts_on:
                        found.append("_brain (symlink to brain)")
                else:
                    found.append("_brain (broken or other target)")
            else:
                found.append("_brain (not a symlink)")
        agents_local = os.path.join(path, "AGENTS.local.md")
        if os.path.isfile(agents_local) and not artifacts_on:
            try:
                with open(agents_local, encoding="utf-8") as fh:
                    if "<!-- MATRIX:BEGIN" in fh.read():
                        found.append("AGENTS.local.md (managed block)")
            except OSError:
                pass
        if not artifacts_on:
            exf = _git_exclude_path(path)
            if exf and os.path.isfile(exf):
                try:
                    with open(exf, encoding="utf-8") as fh:
                        if "# === MATRIX:EXCLUDE:BEGIN" in fh.read():
                            found.append(".git/info/exclude (managed block)")
                except OSError:
                    pass
        if found:
            out[name] = found
    return out


BOOT_WARN_ORDER = [
    "surface_budget",
    "validate_lessons",
    "model_drift",
    "ttl_expired",
    "validate_layer2",
    "the_source",
    "snapshot_due",
    "flags_config",
]


def _boot_warn(root, target="devin"):
    """Run the WARN-only boot health channel.

    Never writes to errors/checks and never changes the hook's ok. Uses an
    internal 6-second deadline; remaining emitters are reported in skipped.
    """
    warns = []
    details = {}
    skipped = []
    start = time.perf_counter()

    if not _flags_value("hooks.boot_warn"):
        return {
            "warns": [],
            "details": {},
            "skipped": list(BOOT_WARN_ORDER),
            "elapsed_ms": 0,
        }

    budget = float(
        os.environ.get("BOOT_WARN_BUDGET_S", os.environ.get("MATRIX_BOOT_WARN_BUDGET_S", 6.0))
    )
    deadline = start + budget

    def hit_deadline():
        return time.perf_counter() > deadline

    def add_warn(token, detail):
        if token not in warns:
            warns.append(token)
        details[token] = detail

    events = ledger_tail_events(root)
    now = time.time()

    # 1. surface_budget (cheap — 3 getsize baratos; nunca alimenta el ok global)
    if hit_deadline():
        skipped.append("surface_budget")
    else:
        try:
            if validate_surface_budget:
                v = validate_surface_budget({})
                warned = [s.get("name") for s in v.get("surfaces", []) if s.get("status") != "ok"]
                if not v.get("ok") or warned:
                    add_warn(
                        "surface_budget",
                        {
                            "ok": v.get("ok"),
                            "warned": warned,
                            "fix": "slim AGENTS.md/DEVIN.md/neo.md",
                        },
                    )
        except Exception as exc:
            add_warn("surface_budget", {"error": str(exc), "fix": "slim AGENTS.md/DEVIN.md/neo.md"})

    # 2. validate_lessons (cheap)
    if hit_deadline():
        skipped.append("validate_lessons")
    else:
        try:
            if validate_lessons:
                v = validate_lessons({})
                if not v.get("ok") or v.get("size_warning"):
                    add_warn(
                        "validate_lessons",
                        {
                            "ok": v.get("ok"),
                            "duplicates": v.get("duplicates", []),
                            "size_warning": v.get("size_warning"),
                            "fix": "bin/matrix hooks validate_lessons",
                        },
                    )
        except Exception as exc:
            add_warn("validate_lessons", {"error": str(exc), "fix": "bin/matrix hooks validate_lessons"})

    # 3. model_drift
    if hit_deadline():
        skipped.append("model_drift")
    else:
        try:
            if model_drift:
                md = model_drift(target, root)
                overrides = model_override_active(events)
                if md.get("applicable"):
                    unsuppressed = []
                    for d in md.get("drift", []):
                        name = d.get("agent") or d.get("skill")
                        installed = d.get("installed")
                        override = overrides.get(name)
                        if override and override.get("model") == installed:
                            continue
                        unsuppressed.append(d)
                    if unsuppressed:
                        add_warn(
                            "model_drift",
                            {
                                "drift": unsuppressed,
                                "fix": "bin/matrix build --target=devin && bin/matrix install --target=devin",
                            },
                        )
        except Exception as exc:
            add_warn("model_drift", {"error": str(exc), "fix": "bin/matrix build --target=devin && bin/matrix install --target=devin"})

    # 4. ttl_expired
    if hit_deadline():
        skipped.append("ttl_expired")
    else:
        try:
            ttl = ttl_scan(events)
            expired = ttl.get("expired", [])
            if expired:
                detail = {
                    "expired": expired,
                    "fix": "bin/matrix link ttl:<name> <subject> until=<new-date>",
                }
                for e in expired:
                    if e.get("event") == "ttl:path-decision-reform":
                        detail["path_decision_real_uses"] = e.get("path_decision_real_uses", 0)
                        detail["fix"] = "bin/matrix link ttl:path-decision-reform matrix until=<new-date> motivo=fallback-A-C1"
                add_warn("ttl_expired", detail)
        except Exception as exc:
            add_warn("ttl_expired", {"error": str(exc), "fix": "bin/matrix link ttl:<name> <subject> until=<new-date>"})

    # 5. validate_layer2
    if hit_deadline():
        skipped.append("validate_layer2")
    else:
        try:
            if validate_layer2:
                v = validate_layer2({})
                if not v.get("ok"):
                    add_warn(
                        "validate_layer2",
                        {
                            "errors": v.get("errors", [])[:5],
                            "fix": "bin/matrix hooks validate_layer2",
                        },
                    )
        except Exception as exc:
            add_warn("validate_layer2", {"error": str(exc), "fix": "bin/matrix hooks validate_layer2"})

    # 6. the_source
    if hit_deadline():
        skipped.append("the_source")
    else:
        try:
            if the_source_mod:
                v = the_source_mod.check(root, check=True)
                if not v.get("ok"):
                    add_warn(
                        "the_source",
                        {
                            "in_sync": v.get("in_sync"),
                            "fix": "bin/matrix hooks the_source",
                        },
                    )
        except Exception as exc:
            add_warn("the_source", {"error": str(exc), "fix": "bin/matrix hooks the_source"})

    # 7. snapshot_due
    if hit_deadline():
        skipped.append("snapshot_due")
    else:
        try:
            sw = snapshot_window(root, events=events)
            if sw.get("due"):
                add_warn(
                    "snapshot_due",
                    {
                        "days": sw.get("days"),
                        "real_work_sessions": sw.get("real_work_sessions"),
                        "fix": "run the harness-health-report extractor, then bin/matrix link metrics:snapshot matrix path=<output>",
                    },
                )
        except Exception as exc:
            add_warn("snapshot_due", {"error": str(exc), "fix": "run the harness-health-report extractor, then bin/matrix link metrics:snapshot matrix path=<output>"})

    # 8. flags_config — declared consumer of _flags.load_status (§8, B1b).
    # Non-fatal: a corrupt flags config is surfaced as a warn token, never a
    # block — the loader itself never raises (lesson 71).
    if hit_deadline():
        skipped.append("flags_config")
    else:
        try:
            if _flags_load_status:
                ls = _flags_load_status(root)
                status = ls.get("status")
                if status in ("unreadable", "minimal-fallback"):
                    add_warn(
                        "flags_config",
                        {
                            "status": status,
                            "sources": ls.get("sources"),
                            "fix": "repair brain/config.yaml or adapters/<target>/config.yaml",
                        },
                    )
        except Exception as exc:
            add_warn("flags_config", {"error": str(exc), "fix": "repair the flags config"})

    elapsed = time.perf_counter() - start
    return {
        "warns": warns,
        "details": details,
        "skipped": skipped,
        "elapsed_ms": round(elapsed * 1000),
    }


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
        txt = _safe_config_text(cfg)
        if txt is not None:
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

    # Import-boundary ratchet (hard fail, never boot_warn — a ratchet that only
    # warns is the same trap as a guard degraded to a no-op).
    ib = check_boundaries(root)
    check("import_boundaries", ib.get("ok"), "; ".join(ib.get("errors", [])))

    # Legacy binding artifacts — WARN only, never BLOCK. With binding.artifacts=on
    # the legacy files are expected (only a broken `_brain` symlink still warns).
    registry = _load_registry(root)
    artifacts_on = _flags_value("binding.artifacts")
    legacy = _legacy_binding_artifacts(root, registry, artifacts_on)
    missing_paths = [
        f"{proj.get('name')}: {proj.get('path')}"
        for proj in (registry or {}).get("projects", [])
        if proj.get("type") == "local" and proj.get("path") and not os.path.isdir(proj.get("path"))
    ]
    warns = []
    if legacy:
        detail = "; ".join(
            f"{proj} -> {', '.join(arts)}" for proj, arts in legacy.items()
        )
        warns.append(
            "legacy_binding_artifacts: " + detail
            + " — run `bin/matrix migrate-nobind [<name>|--all]`"
        )
    if missing_paths:
        warns.append("registry_path_missing: " + "; ".join(missing_paths))

    target = data.get("target") or resolve_bound_target(data.get("project")) or "devin"

    # Ship validation (delegated, generic)
    if data.get("ship") and validate_ship:
        v = validate_ship(data)
        checks.extend(v.get("checks", []))
        if not v.get("ok"):
            errors.extend(v.get("errors", []))

    # Install integrity (delegated, generic — opt-in per adapter.yaml)
    if check_install_integrity:
        ii = check_install_integrity(target, root)
        if ii.get("applicable"):
            checks.extend(ii.get("checks", []))
            if not ii.get("ok"):
                errors.extend(ii.get("errors", []))

    # Boot WARN channel — information only, never blocks, no project gate.
    boot_warn = _boot_warn(root, target=target)

    result = {
        "hook": "pre_activation_check",
        "ok": not errors,
        "project": data.get("project"),
        "ship": data.get("ship"),
        "root": root,
        "checks": checks,
        "errors": errors,
        "boot_warn": boot_warn,
        "legacy_binding_artifacts": legacy,
        "registry_path_missing": missing_paths,
        "warns": warns,
    }
    emit(result)


if __name__ == "__main__":
    main()
