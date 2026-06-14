#!/usr/bin/env python3
"""The Trainman — shared adapter builder.

Reads the agnostic agents in brain/agents/*.md and renders thin-pointer native
artifacts for a target CLI. Thin-pointer means the generated file does not copy
the brain; it points at it and tells the host CLI how to invoke it. Change the
brain, the pointers still resolve. Change the CLI, swap the renderer.

Usage:
  python3 adapters/_build.py --target=claude
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
    name = os.path.splitext(os.path.basename(path))[0]
    desc = ""
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
    return name, desc


def agents():
    out = []
    for f in sorted(os.listdir(AGENTS_DIR)):
        if f.endswith(".md"):
            stem = f[:-3]
            name, desc = frontmatter(os.path.join(AGENTS_DIR, f))
            out.append((stem, name, desc))
    return out


def render_claude(outdir):
    """Claude Code: thin-pointer slash commands under generated/.claude/commands/."""
    cmddir = os.path.join(outdir, ".claude", "commands")
    os.makedirs(cmddir, exist_ok=True)
    written = []
    for stem, name, desc in agents():
        body = (
            f"---\ndescription: {desc}\n---\n\n"
            f"# /{stem}\n\n"
            f"Read and follow `brain/agents/{stem}.md` (agnostic agent definition). "
            f"Run its `<activation>` block first. Bind capabilities via "
            f"`brain/data/capability-map.md`.\n"
        )
        p = os.path.join(cmddir, f"{stem}.md")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(body)
        written.append(p)
    return written


def render_devin(outdir):
    """Devin: master → Skill, specialists → Subagents, as thin pointers."""
    written = []
    for stem, name, desc in agents():
        if stem == MASTER:
            d = os.path.join(outdir, ".agents", "skills", stem)
            os.makedirs(d, exist_ok=True)
            p = os.path.join(d, "SKILL.md")
            kind = "Skill (master)"
        else:
            d = os.path.join(outdir, ".agents", "agents", stem)
            os.makedirs(d, exist_ok=True)
            p = os.path.join(d, "AGENT.md")
            kind = "Subagent (specialist)"
        body = (
            f"---\nname: {name}\ndescription: {desc}\n---\n\n"
            f"# {name} — Devin {kind}\n\n"
            f"Thin pointer. The behavior lives in `brain/agents/{stem}.md`. "
            f"Read it, run its `<activation>` block, and bind capabilities via "
            f"`brain/data/capability-map.md` (the Devin column).\n"
        )
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(body)
        written.append(p)
    return written


RENDERERS = {"claude": render_claude, "devin": render_devin}


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
