Este archivo es **referencia, no contrato**. Contiene lore, mnemónicos, catálogos y plantillas mudados verbatim desde `AGENTS.md` para que el contrato entre bajo el límite de inyección de 16.384 B del CLI host. **Ninguna regla operable vive acá.** Si una regla aterriza en este archivo, está misfiled: va a `AGENTS.md`. El contrato es `AGENTS.md`.

## Lore note

> **Lore note.** Matrix is named and themed after the trilogy. Each component below carries the name of the character or place whose function it mirrors. The names are mnemonic, not decorative: they tell you what the thing *does*.

## The three layers

```text
┌─────────────────────────────────────────────────────────────┐
│  LAYER 3 — Adapters · "The Trainman"                         │
│  adapters/<cli>/   (one dir/CLI; none built for a 2nd yet)   │
│  Transit between worlds. Maps abstract capabilities to the   │
│  host CLI's native tools. Generates artifacts via            │
│  `bin/matrix build` and deploys them into the CLI's          │
│  discovery path via `bin/matrix install`. Thin, replaceable. │
└─────────────────────────────────────────────────────────────┘
                              ▲
┌─────────────────────────────────────────────────────────────┐
│  LAYER 2 — Intelligence core (agnostic markdown) · "Zion"    │
│  brain/agents/      → Neo (master) + specialists             │
│  brain/data/lessons.md → battle-tested lessons (Zion Archive)│
│  AGENTS.md          → this contract                          │
│  NEVER names a specific CLI. Speaks only in capabilities.    │
└─────────────────────────────────────────────────────────────┘
                              ▲
┌─────────────────────────────────────────────────────────────┐
│  LAYER 1 — Orchestration & infrastructure (bash/python)      │
│  bin/matrix → registry, projects, checkpoints, ledger (Link) │
│  hooks/     → portable enforcement (Seraph)                  │
│  brain/state/ → file-based state (workspace, logs, reports)  │
│  Knows nothing about agents. Manages state and fires hooks.  │
└─────────────────────────────────────────────────────────────┘
```

## Roster

| Agent | Trilogy role | Function (capability) |
|---|---|---|
| **Neo** | The One — the nexus between worlds | **Master.** The single voice. Routes, holds context, carries the sacred foundation. Bridges the user and the host CLI (see the adapter doc at the repo root for which one is current). |
| **The Oracle** | The seer who knows | **Researcher.** Gathers, compares, cites, foresees. Answers "what is true / what exists". |
| **Morpheus** | The mentor who shows the path | **Planner.** Turns ambiguity into ordered scope. Answers "what / when". "I can only show you the door." |
| **The Architect** | Designer of the system | **Architect.** Designs structure, names trade-offs, reviews plans before build. Answers "how it fits". |
| **Trinity** | The operator who executes | **Builder.** Implements and ships. Real, working code. |
| **Agent Smith** | The relentless detector of anomalies | **Evaluator (with scoped remediation).** Tests, critiques, finds the flaw, blocks weak work; fixes the low-blast-radius defects it reported itself, under pre-registered failing→passing evidence. |

## Supporting cast

### Supporting cast (infrastructure, Layers 1 & 3)

| Name | Trilogy role | Function |
|---|---|---|
| **Seraph** | The guardian who tests before passage | **Portable enforcement hooks**: `pre_activation_check`, `validate_phase_close`, `post_run_audit`, bypass detection. |
| **Link** | The operator who connects ship and Matrix | **Ledger**: `brain/state/activity.log`, the append-only index every agent and subsystem reads and writes. |
| **The Construct** | "Load exactly what you need, nothing more" | **Cost & context optimization**: semantic code-nav, model selection, large-artifact delegation, proactive resume checkpoints. |
| **The Trainman** | Controls transit between worlds | **CLI adapter layer**: capability→tool mapping and `bin/matrix build`. |
| **Commander Lock** | Gives direct orders, enforces protocol | **Unattended / cockpit guardrail**: validates the autonomous prompt, hard filesystem rules, fail-loud `TASK_ABORTED`. |
| **The Hardline** | The phone exit in/out of the Matrix | **Multi-channel / AFK**: reacts to external events (Telegram/webhook), zero tokens on idle. Opt-in module. |
| **The Source** | The origin of truth | **`docs/SYSTEM_TRUTH.md`**: a minimal, generated-and-validated single source of truth (no manual doc drift). |
| **Zion** | The home, the spine | **The brain root + sacred foundation.** The non-negotiable values. |
| **The fleet** | Hovercraft with their own captains | **Federation**: see `brain/subsystems/FEDERATION.md`. Core vessel: **Nebuchadnezzar**. Example research ship: **Logos** (captain Niobe). |

## Agent file structure (canonical)

### Agent file structure (canonical)

```markdown
---
name: <agent>
description: <one line: role + when to route here>
capabilities: [read, edit, search, code-nav, run-subagent, ask-user, run-command, browser]
model_policy: <cheap|reasoning|auto>   # The Construct uses this
---

<activation>
1. Load configuration (`brain/config.yaml`).
2. Determine the active project (or Matrix workspace mode).
3. Read the last checkpoints + relevant lessons.
4. ... agent-specific steps ...
</activation>

<persona>
<role>...</role>
<identity>...(Spanish)...</identity>
<communication-style>...</communication-style>
</persona>

<domain>One sentence: what this agent does.</domain>
<key-paths>What outputs it produces and where.</key-paths>
<boundaries>What it does and does not do.</boundaries>
<rules>Operating constraints.</rules>
```

## State & persistence — topology examples (from AGENTS.md §7)

Examples of `innermost-root-wins` topologies that the single scope-resolution rule handles without special cases:
- the Matrix repo living inside a registered project (`emi ⊃ matrix`);
- a registered project living inside the Matrix repo (`clients/<name>`, type `remote`);
- a registered project inside another registered project (`emi ⊃ deseo`).

- **Root resolution (robust).** Scripts resolve `MATRIX_ROOT` by walking up from the script location until `brain/` + `AGENTS.md` are found (the `_brain` symlink bootstrap is a vestigial legacy path, no longer needed). Works from any subdirectory or registered project.

