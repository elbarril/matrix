# Matrix — Personal Intelligence Engine (CLI-agnostic)

Matrix is your personal intelligence layer: one root repo holds the brain, projects live outside and are pulled on demand, and a `_brain` symlink bridges the active project to the intelligence. It is **agnostic to the agentic CLI** — the same brain runs under Devin, Claude Code, Cursor, Codex, or anything next, changing only a thin adapter.

> Themed after the Matrix trilogy. Every component is named after the character or place whose function it mirrors. See [`AGENTS.md`](AGENTS.md) for the canonical contract.

## The three layers

```text
adapters/        LAYER 3 · "The Trainman"  — transit between CLI worlds (thin, replaceable)
brain/           LAYER 2 · "Zion"          — intelligence core in agnostic markdown
bin/ + hooks/    LAYER 1                    — orchestration, state, portable enforcement
```

The golden rule: **Layer 2 never names a CLI.** Agents speak in capabilities (`read`, `edit`, `search`, `code-nav`, `run-subagent`, `ask-user`, `run-command`); each adapter binds those to a host CLI's real tools.

## The roster

One master, five core specialists, one opt-in sixth. Names map to function.

- **Neo** — *master*. The single voice. Routes, holds context, carries the sacred foundation, bridges every CLI.
- **The Oracle** — *researcher*. Gathers, compares, cites, foresees. "What is true / what exists."
- **Morpheus** — *planner*. Turns ambiguity into ordered scope. "What / when."
- **The Architect** — *architect*. Designs structure, names trade-offs, reviews plans before build. "How it fits."
- **Trinity** — *builder*. Implements and ships real, working code.
- **Agent Smith** — *evaluator*. Tests, critiques, finds the flaw, blocks weak work.
- **The Keymaker** — *git/ops, opt-in*. Branches, paths, access, version control.

**Routing seam:** Morpheus answers *what/when*; the Architect answers *how it fits* and reviews the plan before Trinity builds; Smith gates the result before "done".

## Supporting cast (infrastructure)

- **Seraph** — portable enforcement hooks (`pre_activation_check`, `validate_phase_close`, `post_run_audit`, bypass detection).
- **Link** — the append-only ledger (`brain/state/activity.log`) every agent and ship reads/writes.
- **The Construct** — cost & context optimization (semantic code-nav, model selection, artifact delegation, resume checkpoints).
- **The Trainman** — the CLI adapter layer + `bin/matrix build`.
- **Commander Lock** — the unattended/cockpit guardrail (validates the autonomous prompt, hard FS rules, fail-loud).
- **The Hardline** — opt-in multi-channel/AFK daemon (reacts to external events, zero tokens on idle).
- **The Source** — `docs/SYSTEM_TRUTH.md`, a generated-and-validated single source of truth.
- **The fleet** — federated subsystems are ships (`brain/subsystems/<ship>/`) with their own master and contract. Core vessel: **Nebuchadnezzar**; example research ship: **Logos** (captain Niobe).

## File structure

```text
matrix/
├── AGENTS.md                  # canonical contract (Layer 2)
├── README.md                  # this file
├── DEVIN.md                   # Devin adapter notes
├── .context.yaml              # primary active project
├── .registry.json             # all known projects
├── bin/matrix                 # CLI orchestrator (Layer 1)
├── hooks/                     # Seraph — portable enforcement (python)
│   ├── pre_activation_check.py
│   ├── validate_phase_close.py
│   └── post_run_audit.py
├── adapters/                  # Trainman — Layer 3 (devin/, claude/, ...)
├── brain/                     # Layer 2 — the intelligence core
│   ├── config.yaml
│   ├── agents/                # neo, oracle, morpheus, architect, trinity, smith, keymaker
│   ├── workflows/             # spec → develop → test → eval
│   ├── data/                  # lessons.md, code-quality-review-lens.md, capability-map.md
│   ├── subsystems/            # the fleet (federated ships)
│   └── state/                 # workspace.yaml, activity.log, checkpoints.jsonl, ...
├── docs/SYSTEM_TRUTH.md       # The Source (generated/validated)
└── clients/                   # GITIGNORED: pulled project repos
```

## CLI commands

```text
list                      List registered projects
add <name> [path]         Register a project
select <name>             Set primary project + create _brain symlink
deselect                  Clear primary project
work <name>               Warm a project into the active set (multi-project)
unwork <name>             Remove a project from the active set
workspace                 Show the warm set
status                    Show system status
checkpoint "<note>"       Write a checkpoint (+ Link entry)
activity [n]              Show last n Link events
hooks <name> [json]       Run a Seraph hook
build --target=<cli>      Trainman: generate native CLI artifacts
help                      Usage
```

## Quick start

```bash
# Register and bind a project
./bin/matrix add myproject /path/to/project
./bin/matrix select myproject

# Or warm several projects at once
./bin/matrix work myproject
./bin/matrix work otherproject
./bin/matrix workspace

# Generate native artifacts for your CLI and invoke the master
./bin/matrix build --target=claude
# (then invoke Neo via the host CLI; the user always talks to Neo first)
```

## Principles

1. **Root intelligence + pulled projects.** The root repo is the brain; project repos are pulled on demand.
2. **One master, capability specialists.** Neo is the face; specialists are capabilities, not topics. Roster discipline: add one → retire one.
3. **CLI-agnostic core.** The brain speaks capabilities; adapters speak CLIs.
4. **File-based state.** No database. Managed by the CLI; agents never mutate state by hand.
5. **Reality decides.** Nothing is done without an E2E happy-path check. (Sacred foundation.)
6. **Sacred foundation (Zion).** Non-negotiable values baked into Neo's identity.

See [`AGENTS.md`](AGENTS.md) for the full contract and [`DEVIN.md`](DEVIN.md) for Devin-specific notes.
