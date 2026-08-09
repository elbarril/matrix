#!/usr/bin/env python3
"""Seraph · install_integrity_check — generic install-integrity guard.

Reads adapters/<target>/adapter.yaml's `install_integrity:` block and validates
that the target CLI's on-disk install is wired as declared. Layer 1 logic is
CLI-agnostic; CLI-specific paths/substrings live in the adapter's adapter.yaml.

Never reads or logs secret file contents. Only structural JSON/path checks.
"""

import json
import os
import re

from _common import _load_yaml


def _roster_and_supporting():
    """Import roster names lazily to avoid a circular import with
    pre_activation_check.py, which imports this module via optional import."""
    import pre_activation_check

    return pre_activation_check.ROSTER + pre_activation_check.SUPPORTING_AGENTS


def _expand_path(raw, root):
    raw = os.path.expanduser(raw)
    if os.path.isabs(raw):
        return raw
    return os.path.join(root, raw)


def _template_path(template, base_dir, name):
    raw = template.replace("{installed_agents_dir}", base_dir)
    raw = raw.replace("{installed_skills_dir}", base_dir)
    raw = raw.replace("{agent}", name)
    raw = raw.replace("{skill}", name)
    return _expand_path(raw, "")


def _roster_form_map(render, root):
    """Map each roster + supporting-agent name to its rendered install form.

    The master is identified by reading each agent file and looking for an
    explicit 'Master' declaration (e.g. Neo's 'Master agent — ...' description
    and '<role>Master of...' persona). Its form is taken from render.master;
    everything else defaults to render.specialist. This keeps 'neo' out of
    Layer 1 code — the master identity is derived from the agent contract.
    """
    if not isinstance(render, dict):
        render = {}
    default_form = render.get("specialist", "subagent")
    master_form = render.get("master", "skill")

    master_name = None
    for name in _roster_and_supporting():
        path = os.path.join(root, "brain", "agents", name + ".md")
        if not os.path.isfile(path):
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            if re.search(r"\bMaster\b", text, re.IGNORECASE):
                master_name = name
                break
        except OSError:
            continue

    return {
        name: (master_form if name == master_name else default_form)
        for name in _roster_and_supporting()
    }


def check_install_integrity(target, root):
    """
    Reads adapters/<target>/adapter.yaml's `install_integrity:` block.
    Returns:
      {"applicable": bool, "target": str, "checks": [...], "errors": [...], "ok": bool}
    - applicable=False (ok=True) when the adapter declares no `install_integrity:`
      block at all — this is the opt-out path for adapters that don't need it,
      and for a not-yet-built second adapter.
    - Every sub-check is an independent entry in `checks`; any failed sub-check
      appends to `errors` and forces `ok=False`.
    - Never reads or logs secret file contents. Only structural JSON/path checks.
    - Roster names come from hooks/pre_activation_check.py's ROSTER +
      SUPPORTING_AGENTS; rendered-form mapping comes from the adapter's
      `render:` block.
    """
    checks = []
    errors = []

    adapter_yaml = os.path.join(root, "adapters", target, "adapter.yaml")
    cfg = _load_yaml(adapter_yaml)
    if not isinstance(cfg, dict):
        cfg = {}

    ii = cfg.get("install_integrity")
    if not isinstance(ii, dict):
        return {
            "applicable": False,
            "target": target,
            "checks": [],
            "errors": [],
            "ok": True,
        }

    def check(label, ok, detail=""):
        checks.append({"check": label, "ok": bool(ok), "detail": "" if ok else detail})
        if not ok:
            errors.append(label + (f": {detail}" if detail else ""))

    artifacts = cfg.get("artifacts", {}) if isinstance(cfg, dict) else {}
    installed_agents_dir = artifacts.get("installed_agents_dir", "")
    installed_skills_dir = artifacts.get("installed_skills_dir", "")
    render = cfg.get("render", {})
    form_map = _roster_form_map(render, root)

    # 1. config_readable
    config_path = ii.get("config_path")
    config = None
    if config_path:
        expanded = _expand_path(config_path, root)
        if not os.path.isfile(expanded):
            check("config_readable", False, f"{expanded} not found")
        else:
            try:
                with open(expanded, encoding="utf-8") as fh:
                    config = json.load(fh)
                check("config_readable", True)
            except (ValueError, OSError) as e:
                check("config_readable", False, f"{expanded} is not valid JSON: {e}")
    else:
        check("config_readable", False, "config_path missing in install_integrity block")

    # 2. hook_wired:<event>
    required_hooks = ii.get("required_hooks", {})
    if isinstance(required_hooks, dict):
        for event, substring in required_hooks.items():
            if not isinstance(config, dict):
                check(f"hook_wired:{event}", False, "config not loaded")
                continue
            event_hooks = config.get("hooks", {}).get(event)
            if not isinstance(event_hooks, list) or not event_hooks:
                check(f"hook_wired:{event}", False, f"no hooks defined for {event}")
                continue
            found = False
            for wrapper in event_hooks:
                if not isinstance(wrapper, dict):
                    continue
                inner_hooks = wrapper.get("hooks", [])
                if not isinstance(inner_hooks, list):
                    continue
                for hook in inner_hooks:
                    if isinstance(hook, dict) and substring in hook.get("command", ""):
                        found = True
                        break
                if found:
                    break
            check(f"hook_wired:{event}", found,
                  f"no command containing '{substring}' found in {event} hooks")

    # 3. mcp_readable (optional per-adapter)
    mcp_config_path = ii.get("mcp_config_path")
    if mcp_config_path is None:
        # Adapter deliberately has no MCP block; skip 3 and 4 silently.
        mcp_config = None
    else:
        expanded = _expand_path(mcp_config_path, root)
        mcp_config = None
        if not os.path.isfile(expanded):
            check("mcp_readable", False, f"{expanded} not found")
        else:
            try:
                with open(expanded, encoding="utf-8") as fh:
                    mcp_config = json.load(fh)
                check("mcp_readable", True)
            except (ValueError, OSError) as e:
                check("mcp_readable", False, f"{expanded} is not valid JSON: {e}")

    # 4. mcp_server_present:<name>
    if mcp_config is not None:
        mcp_servers = mcp_config.get("mcpServers", {}) if isinstance(mcp_config, dict) else {}
        for server in ii.get("required_mcp_servers", []):
            check(
                f"mcp_server_present:{server}",
                isinstance(mcp_servers, dict) and server in mcp_servers,
                f"server '{server}' not found under mcpServers",
            )

    # 5a. agent_installed:<name> (subagent form)
    agent_template = ii.get("installed_agent_path_template")
    if agent_template and installed_agents_dir:
        for name, form in form_map.items():
            if form != render.get("specialist", "subagent"):
                continue
            path = _template_path(agent_template, installed_agents_dir, name)
            expanded = _expand_path(path, root)
            check(
                f"agent_installed:{name}",
                os.path.isfile(expanded),
                f"{expanded} not found",
            )

    # 5b. skill_installed:<name> (skill form)
    skill_template = ii.get("installed_skill_path_template")
    if skill_template and installed_skills_dir:
        for name, form in form_map.items():
            if form != render.get("master", "skill"):
                continue
            path = _template_path(skill_template, installed_skills_dir, name)
            expanded = _expand_path(path, root)
            check(
                f"skill_installed:{name}",
                os.path.isfile(expanded),
                f"{expanded} not found",
            )

    return {
        "applicable": True,
        "target": target,
        "checks": checks,
        "errors": errors,
        "ok": not errors,
    }


if __name__ == "__main__":
    import sys

    from _common import resolve_root

    target = sys.argv[1] if len(sys.argv) > 1 else "devin"
    result = check_install_integrity(target, resolve_root())
    from _common import emit

    emit(result)
