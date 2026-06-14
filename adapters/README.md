# adapters/ — The Trainman (Layer 3)

> "You do not move unless I say so." The Trainman controls transit between worlds. Here, the worlds are CLIs.

Each adapter is a **thin, replaceable** binding between the agnostic brain (Layer 2) and one host CLI. An adapter declares two things:

1. **A capability → tool map** (`adapter.yaml`) — how the abstract capabilities (`read`, `edit`, `search`, `code-nav`, `run-subagent`, `run-command`, `ask-user`) bind to that CLI's real tools, plus a `model_policy` map.
2. **A builder** (`build.sh`) — renders each agent in `brain/agents/*.md` into the CLI's native artifact (thin pointers that reference the brain, never copies of it).

## Layout

```text
adapters/
├── _build.py            # shared renderer (claude, devin)
├── claude/
│   ├── adapter.yaml
│   ├── build.sh         # → generated/.claude/commands/<agent>.md
│   └── generated/       # build output (gitignored)
└── devin/
    ├── adapter.yaml
    ├── build.sh         # → generated/.agents/skills|agents/...
    └── generated/
```

## Build

```bash
bin/matrix build --target=claude
bin/matrix build --target=devin
```

## Adding a new CLI

1. Create `adapters/<cli>/adapter.yaml` with the capability map.
2. Add a `render_<cli>` function in `_build.py` and a one-line `adapters/<cli>/build.sh`.
3. `bin/matrix build --target=<cli>`.

That is the whole cost of supporting a new CLI: ~one renderer + one yaml. The brain does not change.
