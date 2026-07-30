#!/usr/bin/env python3
"""The Trainman — shared adapter builder.

Reads the agnostic agents in brain/agents/*.md and the federated ships in
brain/subsystems/*/AGENTS.md, then renders thin-pointer native artifacts for a
target CLI. Thin-pointer means the generated file does not copy the brain; it
points at it and tells the host CLI how to invoke it.

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
SUBSYSTEMS_DIR = os.path.join(ROOT, "brain", "subsystems")
# Agents that are not user-facing routed specialists.
NON_ROUTED = {"lock"}
MASTER = "neo"


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
                break
            if ":" in stripped:
                k, v = stripped.split(":", 1)
                block[k.strip()] = parse_scalar_list(v) if v.strip().startswith("[") else v.strip()
    return block


# This deliberately duplicates hooks/ parsing to preserve Layer 3's separation from Layer 1.
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


def ship_manifest(path):
    """Parse the YAML frontmatter of a ship's AGENTS.md as a manifest dict."""
    manifest = {}
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    if not (lines and lines[0].strip() == "---"):
        return manifest
    for ln in lines[1:]:
        if ln.strip() == "---":
            break
        if ":" not in ln:
            continue
        k, v = ln.split(":", 1)
        k = k.strip()
        v = v.strip()
        if v.startswith("["):
            manifest[k] = parse_scalar_list(v)
        else:
            manifest[k] = v.strip('"').strip("'")
    return manifest


def ships():
    """Discover federated ships under brain/subsystems/<ship>/AGENTS.md."""
    out = []
    if not os.path.isdir(SUBSYSTEMS_DIR):
        return out
    for name in sorted(os.listdir(SUBSYSTEMS_DIR)):
        ship_dir = os.path.join(SUBSYSTEMS_DIR, name)
        if not os.path.isdir(ship_dir):
            continue
        agents_md = os.path.join(ship_dir, "AGENTS.md")
        if not os.path.isfile(agents_md):
            continue
        manifest = ship_manifest(agents_md)
        if not manifest.get("ship"):
            continue
        out.append({
            "ship": manifest["ship"],
            "dir": ship_dir,
            "manifest": manifest,
            "captain": manifest.get("captain", ""),
            "crew": manifest.get("crew", []),
        })
    return out


def ship_agent_entry(ship, agent_name, ship_dir):
    """Read a ship agent's frontmatter and return a rendering tuple."""
    agent_file = os.path.join(ship_dir, "agents", f"{agent_name}.md")
    if not os.path.isfile(agent_file):
        return None
    name, desc, model_tier, capabilities = frontmatter(agent_file)
    stem = f"{ship}-{name}"
    return (stem, name, desc, model_tier, capabilities, agent_file)


def required_nesting(ship, captain, crew):
    """Compute max-nesting values for agents that spawn subordinates.

    The manifest currently describes a flat captain+crew tree.  The captain is
    depth 1 from Neo; crew are depth 2.  A captain that spawns depth-2 agents
    needs `max-nesting: 2`.  Leaves get no max-nesting field.
    """
    if not captain:
        return {}
    depths = {captain: 1}
    children = {captain: list(crew)}
    for member in crew:
        depths[member] = 2
        children[member] = []

    def deepest_descendant(node):
        d = 0
        for c in children.get(node, []):
            d = max(d, 1 + deepest_descendant(c))
        return d

    expected = {}
    for node in depths:
        sub = deepest_descendant(node)
        if sub > 0:
            # max-nesting value = depth of the deepest descendant from root
            expected[node] = depths[node] + sub
    return expected


def resolve_model(target, model_policy_tier):
    policy = load_yaml_block(os.path.join(ROOT, "adapters", target, "adapter.yaml"), "model_policy")
    template_name = os.environ.get("MATRIX_ADAPTER_TEMPLATE")
    if template_name:
        template = load_yaml_block(
            os.path.join(ROOT, "adapters", target, "adapter.yaml"),
            f"model_template_{template_name}",
        )
        if template:
            return (
                template.get(model_policy_tier)
                or template.get("auto")
                or policy.get(model_policy_tier)
                or policy.get("auto")
            )
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


def resolve_nesting_field(target):
    """Return the Devin frontmatter field name for nesting depth."""
    nesting = load_yaml_block(os.path.join(ROOT, "adapters", target, "adapter.yaml"), "nesting")
    return nesting.get("field") or "max-nesting"


def _compose_routing_doctrine(roster, fleet_block, target):
    """Return the routing-doctrine section for a master skill artifact.

    The generated text is the operational form of Neo's profile-discipline rule
    and fallback caveat. Kept identical for the current target; a second
    renderer would call this with its own target name.
    """
    return (
        f"## Routing to specialists\n\n"
        f"Neo never lets the user talk to specialists directly. To delegate, "
        f"spawn a subagent that reads the specialist's brain file and runs its "
        f"`<activation>` block. For these named specialists, if the profile name "
        f"below appears in this session's list of available `run_subagent` "
        f"profiles, ALWAYS pass that exact name — never substitute "
        f"`subagent_general`/`subagent_explore` for one of them out of habit. "
        f"Only fall back to a general subagent pointed at the file when the named "
        f"profile is genuinely absent from that list (e.g. this machine hasn't run "
        f"`matrix install --target={target}` yet):\n\n"
        f"{roster}\n\n"
        f"{fleet_block}\n\n"
        f"Log every route/handoff to the Link ledger via `bin/matrix`.\n"
    )


def render_devin(outdir):
    """Devin: master → Skill, specialists → Subagents, ships → subagents."""
    written = []
    brain = os.path.join(ROOT, "brain")
    agent_dir = os.path.join(brain, "agents")
    capmap = os.path.join(brain, "data", "capability-map.md")
    excluded = NON_ROUTED | {MASTER}
    specialists = [s for s, _n, _d, _m, _c in agents() if s not in excluded]

    # Build the fleet section for Neo's skill.
    fleet_lines = ["## The fleet", ""]
    ship_list = ships()
    if ship_list:
        for sh in ship_list:
            m = sh["manifest"]
            fleet_lines.append(f"- **{sh['ship']}** — captain `{sh['captain']}`. Trigger: {m.get('route-when', '')}")
        fleet_lines.append("")
        fleet_lines.append("A ship's crew is reached only by its own captain (via `run_subagent`). Neo delegates the whole request to the captain and presents the graded result.")
        fleet_lines.append("")
    else:
        fleet_lines.append("- (none registered)")
        fleet_lines.append("")
    fleet_block = "\n".join(fleet_lines)

    for stem, name, desc, model_tier, capabilities in agents():
        agent_file = os.path.join(agent_dir, f"{stem}.md")
        model = resolve_model("devin", model_tier)
        model_line = f"model: {model}\n" if model else ""
        if stem == MASTER:
            d = os.path.join(outdir, ".agents", "skills", stem)
            os.makedirs(d, exist_ok=True)
            p = os.path.join(d, "SKILL.md")
            roster = "\n".join(f"- `{s}` → `{os.path.join(agent_dir, s + '.md')}`" for s in specialists)
            contract_file = os.path.join(ROOT, "AGENTS.md")
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
                f"{_compose_routing_doctrine(roster, fleet_block, 'devin')}"
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

    # Render federated ship agents.
    nesting_field = resolve_nesting_field("devin")
    for sh in ship_list:
        ship = sh["ship"]
        ship_dir = sh["dir"]
        captain = sh["captain"]
        crew = sh["crew"]
        expected_nesting = required_nesting(ship, captain, crew)
        for agent_name in [captain] + list(crew):
            entry = ship_agent_entry(ship, agent_name, ship_dir)
            if not entry:
                continue
            stem, name, desc, model_tier, capabilities, agent_file = entry
            model = resolve_model("devin", model_tier)
            model_line = f"model: {model}\n" if model else ""
            allowed = resolve_allowed_tools("devin", capabilities)
            allowed_block = (
                "allowed-tools:\n" + "".join(f"  - {t}\n" for t in allowed) if allowed else ""
            )
            nesting_value = expected_nesting.get(agent_name)
            nesting_line = f"{nesting_field}: {nesting_value}\n" if nesting_value else ""
            d = os.path.join(outdir, ".agents", "agents", stem)
            os.makedirs(d, exist_ok=True)
            p = os.path.join(d, "AGENT.md")
            if agent_name == captain:
                reach_line = (
                    f"This agent is the captain of the `{ship}` ship. It is reached by "
                    f"**Neo** through `run_subagent` (profile `{stem}`) and may spawn its own crew."
                )
            else:
                reach_line = (
                    f"This agent is internal to the `{ship}` ship. It is reached only by "
                    f"its captain (`{captain}`) through `run_subagent` (profile `{stem}`). "
                    f"It is not a routing target for Neo."
                )
            body = (
                f"---\nname: {stem}\ndescription: {desc}\n{model_line}{allowed_block}{nesting_line}---\n\n"
                f"# {name} — Devin Subagent (ship crew)\n\n"
                f"Thin pointer. Read and follow the crew member's brain definition, "
                f"and run its `<activation>` block FIRST:\n\n"
                f"    {agent_file}\n\n"
                f"Bind capabilities to Devin tools via the Devin column of:\n\n"
                f"    {capmap}\n\n"
                f"{reach_line}\n"
            )
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(body)
            written.append(p)

    return written


RENDERERS = {"devin": render_devin}


def main():
    target = ""
    template = ""
    for a in sys.argv[1:]:
        if a.startswith("--target="):
            target = a.split("=", 1)[1]
        elif a.startswith("--template="):
            template = a.split("=", 1)[1]
    if template:
        os.environ["MATRIX_ADAPTER_TEMPLATE"] = template
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
