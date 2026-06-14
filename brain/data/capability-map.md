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
render:
  master: skill        # → .agents/skills/<name>/SKILL.md
  specialist: subagent # → .agents/agents/<name>/AGENT.md
```

The golden rule: **if a capability has no native equivalent in a CLI, the adapter provides a fallback** (e.g. `code-nav` → `search`). The brain never changes.
