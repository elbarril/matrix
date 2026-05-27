# Matrix - Devin Integration Notes

This document contains Devin-specific notes for the Matrix intelligence engine. For the canonical operating contract, see [AGENTS.md](AGENTS.md).

## Prime Directives

### 1. Read AGENTS.md First

Before any session, read [AGENTS.md](AGENTS.md) to understand the operating contract. This is the document of record for all agent behavior.

### 2. Master Agent Interface

Users interact only with **Deus Ex Machina** (the master agent). Specialists are never invoked directly by users - only through the master agent's routing intelligence.

### 3. Sacred Foundation

The master agent's core values are non-negotiable. See [AGENTS.md](AGENTS.md#sacred-foundation-non-negotiable-values) for the complete list of sacred foundation values.

### 4. File-Based State

All memory and state are stored as files. See [AGENTS.md](AGENTS.md#state-management) for complete state management details.

### 5. Project Context

The `.context.yaml` file tracks the active project. The CLI manages this - use `./bin/matrix select <name>` to set active project, which creates a `_brain` symlink.

## Session Hygiene

See [AGENTS.md](AGENTS.md#session-hygiene) for complete session hygiene requirements, including required and forbidden actions.

## Skill Structure

### Master Agent (Skill)

- **Location**: `.devin/skills/deus-ex-machina/SKILL.md`
- **Type**: Devin Skill
- **Access**: Invoked via `/deus-ex-machina` or skill trigger
- **Permissions**: Full read access, Matrix write access, Matrix CLI execution

### Specialist Agents (Subagents)

- **Location**: `.devin/agents/<name>/AGENT.md`
- **Type**: Devin Subagent
- **Access**: Invoked only by Deus Ex Machina routing
- **Permissions**: Varies by specialist domain

## CLI Integration

The Matrix CLI (`bin/matrix`) provides project management operations. See [AGENTS.md](AGENTS.md#cli-commands) for the complete command reference.

## Project Workflow

### Adding a Project

1. Register the project: `./bin/matrix add <name> <path>`
2. Select the project: `./bin/matrix select <name>`
3. Verify symlink: `ls -la <project-path>/_brain`
4. Invoke master agent: `/deus-ex-machina "your request"`

### Active Project Context

When a project is selected:

- `.context.yaml` is updated with active project info
- A `_brain` symlink is created in the project directory
- The symlink points to the Matrix `brain/` directory
- Agents can access brain state and configuration from the project

## Troubleshooting

For common troubleshooting issues (skills not found, no active project, broken brain symlink, permission issues), see [AGENTS.md](AGENTS.md#troubleshooting).

## Skill-Level Enforcement Mechanisms

The Deus Ex Machina skill includes built-in enforcement mechanisms to ensure the activation protocol is followed correctly. These mechanisms are implemented within the skill itself (SKILL.md), not in the Matrix CLI.

**Important**: Enforcement happens at the skill level, not the CLI level.

### Validation Scripts

The system includes several validation scripts in `.devin/skills/deus-ex-machina/scripts/`:

- **matrix-pre-activation-checks.sh**: Consolidated pre-activation validation (config, context, routing resources, brain state)
- **matrix-validate-config.sh**: Validates brain/config.yaml exists and is valid YAML
- **matrix-validate-context.sh**: Validates .context.yaml exists and has active project
- **matrix-validate-routing-resources.sh**: Validates routing resources exist (specialist-triggers.md, coordination-patterns.md, routing-rules.md)
- **matrix-validate-activation.sh**: Post-activation validation compliance check
- **matrix-init-brain-state.sh**: Initializes brain state directory structure
- **matrix-log-entry.sh**: Work process logging with consolidated event structure
- **matrix-log-metrics.sh**: Log quality metrics calculation
- **matrix-execute-with-error-logging.sh**: Command execution wrapper with error logging and retry support

All scripts are _brain-aware and auto-detect _brain symlink when running from active projects.

- The Matrix CLI (`bin/matrix`) does NOT invoke agents
- Agents (skills) are invoked through Devin (e.g., `/deus-ex-machina` or skill trigger)
- See [SKILL.md](.devin/skills/deus-ex-machina/SKILL.md) for complete enforcement implementation details

### CLI vs Skill Responsibilities

**Matrix CLI (`bin/matrix`)**:

- Project management operations (add, select, list, status, deselect)
- Checkpoint writing via `./bin/matrix checkpoint`
- State management (brain directory structure)
- DOES NOT invoke agents or enforce activation protocol

**Deus Ex Machina Skill**:

- Pre-invocation checks, activation protocol, post-activation validation
- Work process logging and routing to specialist agents
- Uses CLI for checkpoints, not for invocation

See [SKILL.md](.devin/skills/deus-ex-machina/SKILL.md) for complete skill implementation including:

- `<pre-invocation-checks>`: Validation scripts before activation
- `<activation-protocol>`: Step-by-step activation sequence
- `<post-activation-validation>`: Compliance validation after activation
- `<work-process-logging>`: Logging structure and scripts
- `<routing-resources>`: External routing intelligence files

### Proper Skill Invocation

**Correct invocation**:

```bash
# From Matrix directory
/deus-ex-machina "your request here"

# From active project directory (with _brain symlink)
/deus-ex-machina "your request here"

# Using skill trigger
skill invoke deus-ex-machina "your request here"
```

**Incorrect invocation**:

```bash
# DO NOT invoke specialists directly
/smith "debug this issue"  # WRONG - users only interact with Deus Ex Machina

# DO NOT manually read SKILL.md and skip activation protocol
cat .devin/skills/deus-ex-machina/SKILL.md  # WRONG - bypasses enforcement
```

### Why Skill-Level Enforcement?

Enforcement at the skill level ensures:

- **Bypass Detection**: Manual bypass attempts are detectable through validation reports
- **Audit Trail**: Complete logging of all activation steps and work processes
- **Debugging Capability**: Clear data about what happened for troubleshooting
- **Self-Contained**: Enforcement logic travels with the skill, not the CLI
- **Devin-Native**: Works within Devin's skill invocation model

The Matrix CLI remains focused on project management operations, while the skill handles its own activation protocol enforcement.

## Architecture Notes

### Root Intelligence + Pulled Projects

The Matrix directory is the intelligence layer. Project repos live under `clients/` (gitignored). Only actively used projects are pulled locally.

### Registry First, Pull on Demand

The `.registry.json` knows about all projects. Only projects being actively worked on are cloned to `clients/`.

### Devin Native Agents

Each agent uses Devin's native structure:

- Master agent is a Skill (`.devin/skills/<name>/SKILL.md`)
- Specialists are Subagents (`.devin/agents/<name>/AGENT.md`)
- All have YAML frontmatter and structured Markdown/XML bodies

### Sacred Foundation

Even small agent sets need named values. Core values are baked into the master agent's persona to maintain system coherence.

## Version 1 Constraints

See [AGENTS.md](AGENTS.md#evolution-path) for complete V1 constraints and evolution path.

## Next Steps

After setting up Matrix:

1. Add your first project: `./bin/matrix add <name> <path>`
2. Select the project: `./bin/matrix select <name>`
3. Invoke the master agent: `/deus-ex-machina "your request"`
4. Write checkpoints: `./bin/matrix checkpoint "progress note"`

For complete system documentation, see [AGENTS.md](AGENTS.md).
