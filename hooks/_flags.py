#!/usr/bin/env python3
"""Seraph — unified flag loader (single source of truth for feature flags).

Precedence (highest wins):
  env MATRIX_<NAME> > adapters/<target>/config.yaml#flags > brain/config.yaml#flags > DEFAULTS

`brain/config.yaml` is gitignored per-machine and may not exist or lack a
`flags:` section; the loader synthesizes defaults in that case and never
overwrites user:/language:/timezone:.

API (Python, imported by hooks):
  get_flag(name) -> {value, source, high_risk, risk, depends_on, state, state_reason}
  all_flags()    -> {name: {...}}

CLI (for bash, via bin/matrix):
  python3 hooks/_flags.py list          -> JSON array of all flags
  python3 hooks/_flags.py get <name>    -> JSON of one flag
  python3 hooks/_flags.py table         -> aligned plain-text table
  python3 hooks/_flags.py validate      -> JSON of dangerous/inert; exit 1 if any
"""
import json
import os
import re
import sys

# The 11 flags from the v2 matrix (design appendix C). Defaults never change
# the 10 original v1 values; #11 `binding.artifacts` is new and off.
DEFAULTS = {
    "activation.reinject": True,
    "activation.reinject_full": False,
    "gate.shared_surface": True,
    "gate.writer_lane": True,
    "gate.pre_exec_guard": True,
    "gate.secret_deny": False,
    "hooks.pre_activation_check": True,
    "hooks.boot_warn": True,
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


def _load_yaml(path):
    try:
        import yaml
        with open(path, encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
    except Exception:
        return _load_yaml_minimal(path)


def _target(root):
    return os.environ.get("MATRIX_ADAPTER_TARGET", "devin")


def _section_flags(path):
    cfg = _load_yaml(path)
    flags = cfg.get("flags") if isinstance(cfg, dict) else None
    return flags if isinstance(flags, dict) else {}


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

    brain_flags = _section_flags(os.path.join(root, "brain", "config.yaml"))
    if name in brain_flags:
        value = _bool(brain_flags[name])
        source = "brain"

    adapter_flags = _section_flags(os.path.join(root, "adapters", _target(root), "config.yaml"))
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
        print(json.dumps(bad, ensure_ascii=False, indent=2))
        return 1 if bad else 0
    sys.exit(1)


if __name__ == "__main__":
    sys.exit(main())
