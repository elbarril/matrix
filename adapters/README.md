# adapters/ — The Trainman (Layer 3)

> "You do not move unless I say so." The Trainman controls transit between worlds. Today there is exactly one world: Devin.

Each adapter is a **thin, replaceable** binding between the agnostic brain (Layer 2) and one host CLI. An adapter declares three things:

1. **A capability → tool map** (`adapter.yaml`) — how the abstract capabilities (`read`, `edit`, `search`, `code-nav`, `run-subagent`, `run-command`, `ask-user`, `browser`, `docs-lookup`, ...) bind to that CLI's real tools, plus a `model_policy` map and (optionally) an `allowed_tools` map for least-privilege scoping.
2. **A builder** (`build.sh`) — renders each agent in `brain/agents/*.md` into the CLI's native artifact (thin pointers that reference the brain by absolute path, never copies of it), including a `model:` frontmatter field resolved from the agent's `model_policy` tier, and — for Devin — an `allowed-tools:` grant resolved from the agent's declared `capabilities:`.
3. **An installer** (`install.sh`) — deploys the generated artifacts into the host CLI's discovery path so they are actually invocable. For Devin this means the global path (`~/.config/devin/skills|agents/`), making Neo reachable from any project.

## Layout

```text
adapters/
├── _build.py            # shared renderer (currently: devin only)
└── devin/
    ├── adapter.yaml      # capability map + model_policy
    ├── build.sh          # → generated/.agents/skills|agents/...
    ├── install.sh        # generated/ → ~/.config/devin/skills|agents/
    └── generated/        # build output (gitignored)
```

## Build & install

```bash
bin/matrix build   --target=devin [--template=<nombre>]  # generate artifacts (gitignored)
bin/matrix install --target=devin                          # deploy into the CLI discovery path
```

`build` accepts an optional `--template=<nombre>` flag (Layer 1) that selects
one of the cost/quality presets declared in `adapters/devin/adapter.yaml`:

| Template | `cheap` | `reasoning` | `auto` |
|----------|---------|-------------|--------|
| `gratis` | `swe-1-7-medium` | `swe-1-7-medium` | `swe-1-7-medium` |
| `barato` | `swe-1-7-medium` | `swe-1-6-fast` | `swe-1-7-medium` |
| `equilibrado` | `swe-1-7-medium` | `sonnet` | `adaptive` |
| `caro` | `sonnet` | `opus` | `adaptive` |

The default is `gratis`. The last explicit or defaulted choice is persisted in
`brain/state/adapter-templates.json` (per-target) and reused on subsequent
builds unless overridden with `--template=`.

`build` is pure at Layer 3: `_build.py`/`build.sh` themselves write only under
`generated/`. The `--template` side-effect (validation + persistence in
`brain/state/adapter-templates.json`) is deliberately mediated by `bin/matrix`
(Layer 1), the only component authorized to write `brain/state/`.

`install` is what makes the artifacts discoverable; it is idempotent and copies
self-contained pointers. Re-run both after changing an agent's
`name`/`description`/`model_policy`, the roster, or
`adapters/devin/adapter.yaml`'s `model_policy` map.

## Adding a new CLI

Only Devin is implemented today, but the abstraction is designed to make a
second one cheap:

1. Create `adapters/<cli>/adapter.yaml` with the capability map + `model_policy`.
2. Add a `render_<cli>` function in `_build.py`, register it in `RENDERERS`, and add a one-line `adapters/<cli>/build.sh`.
3. Add `adapters/<cli>/install.sh` to deploy into that CLI's discovery path.
4. `bin/matrix build --target=<cli>` then `bin/matrix install --target=<cli>`.

That is the whole cost of supporting a new CLI: ~one renderer + one yaml + one installer. The brain does not change.
