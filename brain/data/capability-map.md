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
  edit: [edit, multi_edit]
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

Beyond documenting the mapping above, the Devin adapter also declares an `allowed_tools:` block in `adapters/devin/adapter.yaml` — a second mapping, from capability to Devin's actual frontmatter tool categories (`read`, `edit`, `grep`, `glob`, `exec`, and `mcp__server__tool` patterns; this is a smaller, fixed vocabulary, distinct from the tool-call names in the `capabilities:` map above). The Trainman resolves each agent's declared `capabilities:` through this second map and writes the union as `allowed-tools:` frontmatter, so every generated `SKILL.md`/`AGENT.md` is scoped to only what that agent actually declared needing — "Restricting tools makes skills/subagents safer and more predictable" (Devin CLI docs).

`ask-user` and `run-subagent` are intentionally excluded from `allowed_tools` — see the constraint below and the Nesting Depth rule (subagents cannot spawn subagents by default); neither is a grantable `allowed-tools` entry, so including them would be a no-op.

## Devin-specific constraint: `ask-user` inside subagents

Devin **never** allows a subagent to call `ask_user_question` — it is withheld from every subagent unconditionally, regardless of `allowed-tools` or permissions (platform rule, not configurable). Several specialists (Architect, Keymaker, Morpheus, Oracle, Trinity) declare the `ask-user` capability in the agnostic brain, but under the Devin adapter they run as **subagents** (`.agents/agents/<name>/AGENT.md`), so they cannot exercise it directly.

Resolution for the Devin adapter: a specialist that needs to ask the user stops and returns the question to **Neo** (the master skill — not a subagent, so it retains `ask_user_question`) instead of calling it itself. Neo relays the question, gets the answer, and re-delegates. This is a Devin-adapter concern only; the brain's `ask-user` capability declaration does not change, because another CLI's adapter may not have this restriction.

## Model policy → Devin frontmatter

The Trainman resolves each agent's `model_policy` tier (`cheap`/`reasoning`/`auto`) through the adapter's `model_policy` map and writes the result as `model: <name>` in the generated `SKILL.md`/`AGENT.md` frontmatter (see `extensibility/skills` and `subagents` in the Devin CLI docs — both support a `model` override field). Re-run `bin/matrix build --target=devin && bin/matrix install --target=devin` after changing `adapters/devin/adapter.yaml`'s `model_policy` map for the change to take effect globally.
