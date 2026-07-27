# capability-map.md — The Construct & the Trainman reference

The brain speaks in **abstract capabilities**. Adapters (the Trainman) bind each capability to a host CLI's real tool. This file is the canonical list of capabilities and the binding contract.

## Capabilities (what agents may request)

| Capability | Meaning | Cost note (The Construct) |
|---|---|---|
| `read` | Read a file or range | Prefer ranges over whole files |
| `edit` | Modify a file | Symbol-scoped edits when possible. An adapter may bind this to a tool set that also **creates** files; that widening is accepted rather than split into a separate `write` capability (a vocabulary change rippling through every agent — unearned, Foundation 4). An agent that must not create files says so in its own `<boundaries>`. **Live subagent note (2026-07-27):** the `write` grant was **CONFIRMED ABSENT** for subagents under the current adapter despite this declared mapping; source: the current adapter's own reference doc at the repo root, "Least-privilege `allowed-tools`". |
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

Each adapter under `adapters/<cli>/` declares a mapping from the capabilities above to that CLI's native tools, plus how to render an agent (`brain/agents/*.md`) into the CLI's native artifact:

```yaml
# adapters/<cli>/adapter.yaml (illustrative shape, not a real CLI's tool names)
capabilities:
  read: <native read tool>
  edit: [<native edit tool>, <native create tool>]
  search: [<native grep tool>, <native find tool>]
  code-nav: <native semantic-search tool>   # fallback: search
  run-subagent: <native delegate tool>
  run-command: <native shell tool>
  ask-user: <native ask-user tool>
  browser: <native browser MCP binding>     # visual QA; no-op if unconfigured
  docs-lookup: <native docs MCP binding>    # version-pinned library docs
render:
  master: <native master-artifact kind>       # e.g. one file per master agent
  specialist: <native specialist-artifact kind> # e.g. one file per specialist
```

The golden rule: **if a capability has no native equivalent in a CLI, the adapter provides a fallback** (e.g. `code-nav` → `search`). The brain never changes. See the current adapter's own reference doc at the repo root for its real tool names and its live `adapter.yaml`.

## Least-privilege: the concept

Beyond documenting the capability mapping above, an adapter may also declare a second, narrower mapping from capability to the host CLI's own least-privilege grant vocabulary (its real frontmatter/permission categories — typically a smaller, fixed set than the tool-call names in the `capabilities:` map above). The Trainman resolves each agent's declared `capabilities:` through that second map and writes the result as the generated artifact's tool-grant frontmatter, so a read-only specialist cannot exercise `edit` or `run-command` even if the underlying platform would otherwise allow it.

Two capabilities typically resist a simple grant-list treatment and need adapter-specific handling instead (see the current adapter's own reference doc at the repo root for how it resolves each): `ask-user` (some host CLIs unconditionally withhold user-prompting from anything but the master agent) and `run-subagent` (some host CLIs require an explicit nesting-depth declaration before a delegate may itself delegate further). Both are least-privilege concerns in the abstract, but their concrete mechanics are adapter-specific and documented there, not here.

## Model policy → adapter frontmatter

The Trainman resolves each agent's `model_policy` tier (`cheap`/`reasoning`/`auto`) through the adapter's `model_policy` map and writes the result as the model field in the generated artifact's frontmatter, so the tier assignment in the brain never has to change — only the adapter's mapping. See the current adapter's own reference doc at the repo root for its concrete model table and the rebuild/reinstall step required after changing that map.
