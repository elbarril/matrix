#!/usr/bin/env python3
"""Seraph — unified flag loader (single source of truth for feature flags).

Precedence (highest wins):
  env MATRIX_<NAME> > adapters/<target>/config.yaml#flags > brain/config.yaml#flags > DEFAULTS

`brain/config.yaml` is gitignored per-machine and may not exist or lack a
`flags:` section; the loader synthesizes defaults in that case and never
overwrites user:/language:/timezone:.

API (Python, imported by hooks):
  get_flag(name) -> {value, source, high_risk, risk, depends_on, state, state_reason, load_status}
  all_flags()    -> {name: {...}}
  load_status()  -> merged + per-source flag-config load status (never raises)

CLI (for bash, via bin/matrix):
  python3 hooks/_flags.py list          -> JSON array of all flags
  python3 hooks/_flags.py get <name>    -> JSON of one flag
  python3 hooks/_flags.py table         -> aligned plain-text table
  python3 hooks/_flags.py validate      -> JSON of dangerous/inert + load_status; exit 1 if any dangerous/inert

Load status is non-fatal (B1b): a corrupt flags config never blocks activation.
It is surfaced with a real diagnostic to stderr and as `load_status` on every
flag dict, in `flags --validate`, and in the boot-warn channel
(pre_activation_check._boot_warn, token `flags_config`). A healthy config that
simply lacks a `flags:` section is `absent`, not an error.
"""
import json
import os
import re
import sys

# The v2 matrix flags (design appendix C); see `DEFAULTS` below. Defaults never
# change the 10 original v1 values; `binding.artifacts` is new and off.
DEFAULTS = {
    "activation.reinject": True,
    "activation.reinject_full": False,
    "gate.shared_surface": True,
    "gate.writer_lane": True,
    "gate.pre_exec_guard": True,
    "gate.secret_deny": False,
    "hooks.pre_activation_check": True,
    "hooks.boot_warn": True,
    "hooks.session_extras": False,
    "memory.tree": True,
    "views.scoped": True,
    "binding.artifacts": False,
}

# v2 appendix D — a flag whose dependency is off is inert.
DEPENDS_ON = {
    "activation.reinject_full": "activation.reinject",
    "gate.writer_lane": "gate.shared_surface",
    "hooks.boot_warn": "hooks.pre_activation_check",
}

# v2 table C — risk column.
RISK = {
    "activation.reinject": "",
    "activation.reinject_full": "",
    "gate.shared_surface": "high",
    "gate.writer_lane": "high",
    "gate.pre_exec_guard": "high",
    "gate.secret_deny": "high",
    "hooks.pre_activation_check": "medium",
    "hooks.boot_warn": "",
    "hooks.session_extras": "",
    "memory.tree": "",
    "views.scoped": "",
    "binding.artifacts": "",
}

# Security-down flags (off is dangerous) and the risky-up flag (on is dangerous).
SECURITY_DOWN = {"gate.shared_surface", "gate.writer_lane", "gate.pre_exec_guard"}
RISKY_UP = {"gate.secret_deny"}

# Legacy boolean env aliases -> (flag, modern env name). WARN once per process.
LEGACY_ENV = {
    "MATRIX_INJECT_ACTIVATION": ("activation.reinject", "MATRIX_ACTIVATION_REINJECT"),
    "BOOT_WARN_ENABLED": ("hooks.boot_warn", "MATRIX_HOOKS_BOOT_WARN"),
    "MATRIX_BOOT_WARN": ("hooks.boot_warn", "MATRIX_HOOKS_BOOT_WARN"),
}

_warned_legacy = set()

# Load-status diagnostic throttling: report each (path, status) once per
# process, because get_flag/all_flags re-read both config files per flag and an
# unreadable config would otherwise flood stderr.
_warned_load = set()

# Per-source load statuses, ordered by severity for the merge rule (B1b).
# `unreadable` > `minimal-fallback` > `ok` > `absent`.
_LOAD_STATUS_ORDER = {
    "absent": 0,
    "ok": 1,
    "minimal-fallback": 2,
    "unreadable": 3,
}


def resolve_root():
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


def _parse_scalar(raw):
    raw = raw.strip()
    if raw in ("true", "True", "yes", "on"):
        return True
    if raw in ("false", "False", "no", "off"):
        return False
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ('"', "'"):
        return raw[1:-1]
    if raw in ("null", "~", "None", ""):
        return None
    return raw


def _load_yaml_minimal(path):
    """Minimal section parser for the two config files we read: top-level
    `key:` and two-space nested `  dotted.key: value`. PyYAML is preferred but
    this keeps the loader dependency-free for any hook environment."""
    data = {}
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return data
    section = None
    for raw in lines:
        line = raw.split("#", 1)[0]
        if not line.strip():
            continue
        m = re.match(r"^([A-Za-z0-9_.-]+)\s*:\s*$", line)
        if m:
            section = m.group(1)
            data.setdefault(section, {})
            continue
        if section:
            m = re.match(r"^\s+([A-Za-z0-9_.-]+)\s*:\s*(.*)$", line)
            if m:
                data[section][m.group(1)] = _parse_scalar(m.group(2))
    return data


def _report_load(status, path, exc):
    """Print the real diagnostic for a degraded/unreadable load, once per process."""
    key = (path, status)
    if key in _warned_load:
        return
    _warned_load.add(key)
    if status == "minimal-fallback":
        print(
            f"[flags] yaml parse failed, minimal fallback used: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        print(f"[flags] path={path}", file=sys.stderr)
    elif status == "unreadable":
        print(
            f"[flags] config unreadable: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        print(f"[flags] sys.executable={sys.executable}", file=sys.stderr)
        print(f"[flags] sys.path[0:5]={sys.path[:5]}", file=sys.stderr)


def _load_yaml(path):
    """Load a config YAML as (data, status). Never raises (lesson 71).

    status is one of:
      ok                PyYAML parsed the file (data is the mapping, {} if empty)
      absent            file missing (or no flags section — see _section_flags)
      minimal-fallback  PyYAML failed, the minimal parser resolved
      unreadable        both parsers failed (data == {})
    """
    if not os.path.isfile(path):
        return {}, "absent"
    try:
        import yaml
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        return (data if data is not None else {}), "ok"
    except Exception as exc:
        try:
            minimal = _load_yaml_minimal(path)
        except Exception:
            # The minimal parser is best-effort too (e.g. non-UTF-8 bytes
            # raise on read); never let it crash the loader (B1b no-raise).
            minimal = {}
        if minimal:
            _report_load("minimal-fallback", path, exc)
            return minimal, "minimal-fallback"
        _report_load("unreadable", path, exc)
        return {}, "unreadable"


def _target(root):
    return os.environ.get("MATRIX_ADAPTER_TARGET", "devin")


def _section_flags(path):
    """Return (flags, section_status) for one config file. Never raises.

    section_status preserves the loader status so corruption is never hidden:
    `unreadable` and `minimal-fallback` keep their status even when no `flags:`
    section survives. `absent` means a legitimate absence (missing file, or a
    cleanly parsed file with no flags section).
    """
    cfg, load_status = _load_yaml(path)
    if load_status == "unreadable":
        return {}, "unreadable"
    flags = cfg.get("flags") if isinstance(cfg, dict) else None
    if isinstance(flags, dict):
        return flags, load_status
    if load_status == "minimal-fallback":
        return {}, "minimal-fallback"
    return {}, "absent"


def _merge_load_status(statuses):
    """Worst-wins merge of per-source flag-config load statuses.

    unreadable > minimal-fallback > ok > absent. A source with a successful
    flags section ('ok') is a real provider; 'absent' (missing file or no
    flags section) contributes nothing. The merged status is the worst source,
    so a corrupt adapter config is never hidden by a healthy brain config.
    """
    if not statuses:
        return "absent"
    return max(statuses, key=lambda s: _LOAD_STATUS_ORDER.get(s, 0))


def load_status(root=None):
    """Return merged + per-source flag-config load status. Never raises (B1b).

    The declared consumer of this severity field is the boot-warn channel
    pre_activation_check._boot_warn (token `flags_config`, §8); `bin/matrix
    flags --validate` lists it too. `absent` merges "no file" and "no flags
    section": both are legitimate absences, documented in _section_flags.
    """
    if root is None:
        root = resolve_root()
    source_paths = {
        "brain": os.path.join(root, "brain", "config.yaml"),
        "adapter:" + _target(root): os.path.join(root, "adapters", _target(root), "config.yaml"),
    }
    statuses = []
    per_source = {}
    for label, path in source_paths.items():
        _, status = _section_flags(path)
        per_source[label] = {"path": path, "status": status}
        statuses.append(status)
    return {
        "status": _merge_load_status(statuses),
        "sources": per_source,
    }


def _env_name(name):
    return "MATRIX_" + name.replace(".", "_").upper()


def _bool(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes", "on")
    return bool(v)


def _state(name, value, depends_on, root):
    if depends_on:
        parent = get_flag(depends_on, root=root)
        if parent and not parent["value"]:
            return "inert", "requires " + depends_on
    if name in SECURITY_DOWN and not value:
        return "dangerous", name + " is off"
    if name in RISKY_UP and value:
        return "dangerous", name + " is on"
    return "active", ""


def get_flag(name, root=None):
    if name not in DEFAULTS:
        return None
    if root is None:
        root = resolve_root()
    value = DEFAULTS[name]
    source = "default"

    brain_flags, brain_status = _section_flags(os.path.join(root, "brain", "config.yaml"))
    if name in brain_flags:
        value = _bool(brain_flags[name])
        source = "brain"

    adapter_flags, adapter_status = _section_flags(
        os.path.join(root, "adapters", _target(root), "config.yaml")
    )
    if name in adapter_flags:
        value = _bool(adapter_flags[name])
        source = "adapter:" + _target(root)

    env_val = os.environ.get(_env_name(name))
    if env_val is not None and env_val != "":
        value = _bool(env_val)
        source = "env"
    else:
        # Legacy boolean aliases apply ONLY when the modern env is absent —
        # the modern MATRIX_<NAME> always wins over a deprecated alias.
        for legacy, (flag, modern) in LEGACY_ENV.items():
            if flag == name and legacy in os.environ and os.environ.get(legacy) != "":
                if legacy not in _warned_legacy:
                    print(f"[flags] {legacy} is deprecated; use {modern}", file=sys.stderr)
                    _warned_legacy.add(legacy)
                value = _bool(os.environ[legacy])
                source = "env"

    depends_on = DEPENDS_ON.get(name)
    state, state_reason = _state(name, value, depends_on, root)
    return {
        "name": name,
        "value": value,
        "source": source,
        "high_risk": RISK.get(name) == "high",
        "risk": RISK.get(name, ""),
        "depends_on": depends_on,
        "state": state,
        "state_reason": state_reason,
        "load_status": _merge_load_status([brain_status, adapter_status]),
    }


def all_flags(root=None):
    return {name: get_flag(name, root=root) for name in sorted(DEFAULTS)}


def _print_table(root=None):
    rows = list(all_flags(root).values())
    header = ("FLAG", "VALUE", "SOURCE", "RISK", "STATE", "DEPENDS_ON")
    widths = [len(header[0]), 5, len(header[2]), 4, 6, 10]
    for r in rows:
        widths[0] = max(widths[0], len(r["name"]))
        widths[2] = max(widths[2], len(r["source"]))
        widths[4] = max(widths[4], len(r["state"]))
        widths[5] = max(widths[5], len(r["depends_on"] or ""))
    fmt = "  ".join("{:<%d}" % w for w in widths)
    print(fmt.format(*header))
    for r in rows:
        print(fmt.format(
            r["name"],
            "on" if r["value"] else "off",
            r["source"],
            r["risk"] or "-",
            r["state"],
            r["depends_on"] or "",
        ))
    for r in rows:
        if r["state"] in ("dangerous", "inert"):
            print(f"  [{r['state']}] {r['name']}: {r['state_reason']}")
    ls = load_status()
    if ls["status"] not in ("ok", "absent"):
        print(f"  [load_status] {ls['status']}: " + json.dumps(ls["sources"], ensure_ascii=False))


def main():
    if len(sys.argv) < 2:
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "list":
        print(json.dumps(list(all_flags().values()), ensure_ascii=False, indent=2))
        return 0
    if cmd == "get":
        if len(sys.argv) < 3:
            sys.exit(1)
        flag = get_flag(sys.argv[2])
        if flag is None:
            sys.exit(1)
        print(json.dumps(flag, ensure_ascii=False, indent=2))
        return 0
    if cmd == "table":
        _print_table()
        return 0
    if cmd == "validate":
        bad = [f for f in all_flags().values() if f["state"] in ("dangerous", "inert")]
        print(json.dumps({
            "flags": bad,
            "load_status": load_status(),
        }, ensure_ascii=False, indent=2))
        return 1 if bad else 0
    sys.exit(1)


if __name__ == "__main__":
    sys.exit(main())
