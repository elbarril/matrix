# capability-map.md — The Construct & the Trainman reference

The brain speaks in **abstract capabilities**. Adapters (the Trainman) bind each capability to a host CLI's real tool. This file is the canonical list of capabilities and the binding contract.

## Capabilities (what agents may request)

| Capability | Meaning | Cost note (The Construct) |
|---|---|---|
| `read` | Read a file or range | Prefer ranges over whole files |
| `edit` | Modify a file | Symbol-scoped edits when possible |
| `search` | Text/glob search across the tree | Narrow the scope; avoid full-tree scans |
| `code-nav` | Symbol-level navigation/edit (definition, references, rename) | 5–10× cheaper than reading whole files |
| `run-subagent` | Delegate to another agent | Use for large artifacts (>~10 KB) with a word cap |
| `run-command` | Execute a shell command | For the reality check (E2E), builds, tests |
| `ask-user` | Ask the user a question | Ask once; never loop on ambiguity |
| `browser` | Render a page and capture visual evidence (screenshots, DOM state) | Only for UI/visual verification (Smith); no-op if the adapter has no binding |
| `docs-lookup` | Fetch current, version-pinned library/framework/API documentation | Cheaper *and* more accurate than a generic web search for this specific case (Oracle) |

## Model policy (per agent / per turn)

| `model_policy` | Use for | Maps to (adapter decides) |
|---|---|---|
| `cheap` | Mechanical work: edits to spec, formatting, git plumbing | the cheapest capable model |
| `reasoning` | Planning, architecture, research, evaluation | the strongest model |
| `auto` | Mixed; the builder decides per step | adapter heuristic |

## Trainman binding contract

Each adapter under `adapters/<cli>/` declares a mapping from the capabilities above to that CLI's native tools, plus how to render an agent (`brain/agents/*.md`) into the CLI's native artifact. Example (Devin):

```yaml
# adapters/devin/adapter.yaml
capabilities:
  read: read_file
  edit: [edit, multi_edit, write]
  search: [grep_search, find_by_name]
  code-nav: codebase_search        # fallback: search
  run-subagent: run_subagent
  run-command: run_command
  ask-user: ask_user_question
  browser: mcp__chrome-browser     # visual QA; no-op if unconfigured
  docs-lookup: mcp__context7       # version-pinned library docs
render:
  master: skill        # → .agents/skills/<name>/SKILL.md
  specialist: subagent # → .agents/agents/<name>/AGENT.md
```

The golden rule: **if a capability has no native equivalent in a CLI, the adapter provides a fallback** (e.g. `code-nav` → `search`). The brain never changes.

## Least-privilege: `allowed-tools` on generated artifacts

Beyond documenting the mapping above, the Devin adapter also declares an `allowed_tools:` block in `adapters/devin/adapter.yaml` — a second mapping, from capability to Devin's actual frontmatter tool categories (`read`, `edit`, `write`, `grep`, `glob`, `exec`, and `mcp__server__tool` patterns; this is a smaller, fixed vocabulary, distinct from the tool-call names in the `capabilities:` map above). The Trainman resolves each agent's declared `capabilities:` through this second map and writes the union as `allowed-tools:` frontmatter. In generated **`AGENT.md` subagent profiles**, this is a real least-privilege restriction: for example, `edit` and `write` are distinct grants. In generated **`SKILL.md` root skills** (such as Neo), do not claim the field is a complete sandbox; the enforceable restriction documented for that surface is `permissions.deny`, which currently covers `read` only, not `grep` or `exec`.

`ask-user` is intentionally excluded from `allowed_tools` — it is unconditionally withheld from subagents (see below). `run-subagent` is not an `allowed-tools` grant; instead, agents that need to spawn subagents are represented by a `max-nesting` frontmatter field, derived from the ship manifest's `captain`/`crew` graph by the Trainman.

## Devin-specific: `run-subagent` in nestable artifacts

Under Devin, `run_subagent`/`read_subagent` are disabled inside a subagent by default. They become available when the subagent profile carries a `max-nesting` frontmatter field whose value is at least the depth of the children it needs to spawn. The Trainman derives this value from the ship manifest's `captain`/`crew` graph (`depth_from_root + subtree_depth`) and injects it **only** into the captain's artifact. Crew leaves do not carry the field, because they have no subordinates to spawn. This is the Devin representation of the abstract `run-subagent` capability; it is not an `allowed-tools` grant.

## Devin-specific constraint: `ask-user` inside subagents

Devin **never** allows a subagent to call `ask_user_question` — it is withheld from every subagent unconditionally, regardless of `allowed-tools` or permissions (platform rule, not configurable). Several specialists (Architect, Keymaker, Morpheus, Oracle, Trinity) declare the `ask-user` capability in the agnostic brain, but under the Devin adapter they run as **subagents** (`.agents/agents/<name>/AGENT.md`), so they cannot exercise it directly.

Resolution for the Devin adapter: a specialist that needs to ask the user stops and returns the question to **Neo** (the master skill — not a subagent, so it retains `ask_user_question`) instead of calling it itself. Neo relays the question, gets the answer, and re-delegates. This is a Devin-adapter concern only; the brain's `ask-user` capability declaration does not change, because another CLI's adapter may not have this restriction.

## Model policy → Devin frontmatter

The Trainman resolves each agent's `model_policy` tier (`cheap`/`reasoning`/`auto`) through the adapter's `model_policy` map and writes the result as `model: <name>` in the generated `SKILL.md`/`AGENT.md` frontmatter (see `extensibility/skills` and `subagents` in the Devin CLI docs — both support a `model` override field). Re-run `bin/matrix build --target=devin && bin/matrix install --target=devin` after changing `adapters/devin/adapter.yaml`'s `model_policy` map for the change to take effect globally.
