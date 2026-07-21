#!/usr/bin/env python3
"""The Trainman — shared adapter builder.

Reads the agnostic agents in brain/agents/*.md and renders thin-pointer native
artifacts for a target CLI. Thin-pointer means the generated file does not copy
the brain; it points at it and tells the host CLI how to invoke it. Change the
brain, the pointers still resolve. Change the CLI, swap the renderer.

Usage:
  python3 adapters/_build.py --target=devin
Output goes to adapters/<target>/generated/.
"""

import os
import sys

ROOT = os.environ.get("MATRIX_ROOT") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)
AGENTS_DIR = os.path.join(ROOT, "brain", "agents")
# Agents that are not user-facing routed specialists.
NON_ROUTED = {"lock"}
MASTER = "neo"


def frontmatter(path):
    """Return (name, description, model_policy, capabilities) from an agent's frontmatter."""
    name = os.path.splitext(os.path.basename(path))[0]
    desc = ""
    model_policy = "auto"
    capabilities = []
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    if lines and lines[0].strip() == "---":
        for ln in lines[1:]:
            if ln.strip() == "---":
                break
            if ln.startswith("name:"):
                name = ln.split(":", 1)[1].strip()
            elif ln.startswith("description:"):
                desc = ln.split(":", 1)[1].strip()
            elif ln.startswith("model_policy:"):
                model_policy = ln.split(":", 1)[1].strip()
            elif ln.startswith("capabilities:"):
                capabilities = parse_scalar_list(ln.split(":", 1)[1])
    return name, desc, model_policy, capabilities


def agents():
    out = []
    for f in sorted(os.listdir(AGENTS_DIR)):
        if f.endswith(".md"):
            stem = f[:-3]
            out.append((stem,) + frontmatter(os.path.join(AGENTS_DIR, f)))
    return out


def parse_scalar_list(raw):
    """Parse a YAML flow-sequence (`[a, b]`) or bare scalar into a list of strings."""
    v = raw.split("#", 1)[0].strip()
    if v.startswith("[") and v.endswith("]"):
        v = v[1:-1]
    if not v:
        return []
    return [item.strip().strip('"').strip("'") for item in v.split(",") if item.strip()]


def load_yaml_block(adapter_yaml, block_key):
    """Parse a simple top-level `<block_key>:` mapping in an adapter.yaml without a
    YAML dependency. Values may be a bare scalar or a `[a, b]` flow-sequence.

    Expects the controlled shape Matrix's adapter.yaml files use:
        <block_key>:
          <sub-key>: <value> | [<value>, <value>, ...]
    """
    block = {}
    if not os.path.isfile(adapter_yaml):
        return block
    in_block = False
    with open(adapter_yaml, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            stripped = line.split("#", 1)[0].strip()
            if not in_block:
                if stripped == f"{block_key}:":
                    in_block = True
                continue
            if not line.startswith((" ", "\t")) and stripped:
                break  # dedented — block ended
            if ":" in stripped:
                k, v = stripped.split(":", 1)
                block[k.strip()] = parse_scalar_list(v) if (v.strip().startswith("[")) else v.strip()
    return block


def resolve_model(target, model_policy_tier):
    policy = load_yaml_block(os.path.join(ROOT, "adapters", target, "adapter.yaml"), "model_policy")
    return policy.get(model_policy_tier) or policy.get("auto")


def resolve_allowed_tools(target, capabilities):
    """Union the Devin allowed-tools categories for a list of abstract capabilities.

    Capabilities with no entry in the map (e.g. `ask-user`, `run-subagent` — see
    capability-map.md) are silently skipped: they are not representable as an
    allowed-tools grant under Devin, so omitting them changes nothing.
    """
    mapping = load_yaml_block(os.path.join(ROOT, "adapters", target, "adapter.yaml"), "allowed_tools")
    seen, out = set(), []
    for cap in capabilities:
        for tool in mapping.get(cap, []) if isinstance(mapping.get(cap), list) else [mapping.get(cap)]:
            if tool and tool not in seen:
                seen.add(tool)
                out.append(tool)
    return out


def render_devin(outdir):
    """Devin: master → Skill, specialists → Subagents, as thin pointers.

    Devin discovers these artifacts from a GLOBAL path (installed by the
    Trainman's install step), so they may be invoked from ANY working
    directory — inside Matrix, inside clients/, or in an unrelated repo.
    Relative paths would not resolve, so the pointers reference the brain by
    ABSOLUTE path (baked from MATRIX_ROOT at build time). The brain's own
    `<activation>` block remains `_brain`-aware for project binding.
    """
    written = []
    brain = os.path.join(ROOT, "brain")
    agent_dir = os.path.join(brain, "agents")
    capmap = os.path.join(brain, "data", "capability-map.md")
    excluded = NON_ROUTED | {MASTER}
    specialists = [s for s, _n, _d, _m, _c in agents() if s not in excluded]
    for stem, name, desc, model_tier, capabilities in agents():
        agent_file = os.path.join(agent_dir, f"{stem}.md")
        model = resolve_model("devin", model_tier)
        model_line = f"model: {model}\n" if model else ""
        if stem == MASTER:
            # The master is a Skill, not a subagent, and needs `run_subagent` /
            # `ask_user_question` — neither is a nameable allowed-tools entry
            # (see capability-map.md), so Neo is intentionally left
            # unrestricted rather than risk silently dropping either one.
            d = os.path.join(outdir, ".agents", "skills", stem)
            os.makedirs(d, exist_ok=True)
            p = os.path.join(d, "SKILL.md")
            roster = "\n".join(f"- `{s}` → `{os.path.join(agent_dir, s + '.md')}`" for s in specialists)
            contract_file = os.path.join(ROOT, "AGENTS.md")
            # Activation preamble source of truth: brain/data/activation-preamble.tmpl
            tmpl = os.path.join(brain, "data", "activation-preamble.tmpl")
            with open(tmpl, encoding="utf-8") as fh:
                core = fh.read()
            core = core.replace("{{CONTRACT_PATH}}", contract_file).replace("{{NEO_AGENT_PATH}}", agent_file)
            body = (
                f"---\nname: {name}\ndescription: {desc}\n{model_line}---\n\n"
                f"# {name} — Devin Skill (master)\n\n"
                f"{core}\n"
                f"Bind capabilities to Devin tools via the Devin column of:\n\n"
                f"    {capmap}\n\n"
                f"## Matrix root (resolve from any working directory)\n\n"
                f"This skill is global and may run from any project. The Matrix "
                f"system lives at an absolute path; use it for orchestration, state, "
                f"and the ledger regardless of cwd:\n\n"
                f"    MATRIX_ROOT = {ROOT}\n"
                f"    orchestrator = {os.path.join(ROOT, 'bin', 'matrix')}\n"
                f"    config       = {os.path.join(brain, 'config.yaml')}\n\n"
                f"If the current project has a `_brain` symlink (created by "
                f"`matrix select`), prefer it for project binding; otherwise fall "
                f"back to the absolute paths above.\n\n"
                f"## Routing to specialists\n\n"
                f"Neo never lets the user talk to specialists directly. To delegate, "
                f"spawn a subagent that reads the specialist's brain file and runs its "
                f"`<activation>` block. Prefer the matching installed subagent profile; "
                f"if unavailable, use a general subagent pointed at the file:\n\n"
                f"{roster}\n\n"
                f"Log every route/handoff to the Link ledger via `bin/matrix`.\n"
            )
        else:
            d = os.path.join(outdir, ".agents", "agents", stem)
            os.makedirs(d, exist_ok=True)
            p = os.path.join(d, "AGENT.md")
            allowed = resolve_allowed_tools("devin", capabilities)
            allowed_block = (
                "allowed-tools:\n" + "".join(f"  - {t}\n" for t in allowed) if allowed else ""
            )
            body = (
                f"---\nname: {name}\ndescription: {desc}\n{model_line}{allowed_block}---\n\n"
                f"# {name} — Devin Subagent (specialist)\n\n"
                f"Thin pointer. Read and follow the specialist's brain definition, "
                f"and run its `<activation>` block FIRST:\n\n"
                f"    {agent_file}\n\n"
                f"Bind capabilities to Devin tools via the Devin column of:\n\n"
                f"    {capmap}\n"
            )
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(body)
        written.append(p)
    return written


RENDERERS = {"devin": render_devin}


def main():
    target = ""
    for a in sys.argv[1:]:
        if a.startswith("--target="):
            target = a.split("=", 1)[1]
    if target not in RENDERERS:
        print(f"[trainman] unknown target '{target}'. Known: {', '.join(RENDERERS)}")
        sys.exit(1)
    outdir = os.path.join(ROOT, "adapters", target, "generated")
    written = RENDERERS[target](outdir)
    print(f"[trainman] target={target} → {len(written)} artifact(s) under {outdir}")
    for p in written:
        print("  " + os.path.relpath(p, ROOT))


if __name__ == "__main__":
    main()
