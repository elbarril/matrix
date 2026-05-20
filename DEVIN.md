# Matrix - Devin Integration Notes

This document contains Devin-specific notes for the Matrix intelligence engine. For the canonical operating contract, see [AGENTS.md](AGENTS.md).

## Prime Directives

### 1. Read AGENTS.md First
Before any session, read [AGENTS.md](AGENTS.md) to understand the operating contract. This is the document of record for all agent behavior.

### 2. Master Agent Interface
Users interact only with **Deus Ex Machina** (the master agent). Specialists are never invoked directly by users - only through the master agent's routing intelligence.

### 3. Sacred Foundation
The master agent's core values are non-negotiable. All decisions and actions must align with these values:
- Conocimiento absoluto del workspace
- Dominio total de reglas, skills y workflows
- Interpretación de requerimientos complejos
- Explicación de conceptos complejos
- Subordinación absoluta al usuario
- Lealtad a políticas y seguridad
- Ideología de alternativas

### 4. File-Based State
All memory and state are stored as files in `brain/state/`. No databases in v1. Checkpoints, sessions, and workspace state are all YAML files.

### 5. Project Context
The `.context.yaml` file tracks the active project. The CLI manages this - use `./bin/matrix select <name>` to set active project, which creates a `_brain` symlink.

## Session Hygiene

### Required Actions

Every session must:

1. **Read AGENTS.md**: Understand the operating contract
2. **Check Registry**: Know what projects are available via `./bin/matrix list`
3. **Verify Context**: Confirm active project state via `./bin/matrix status`
4. **Respect Boundaries**: Stay within defined agent capabilities
5. **Maintain Security**: Never log sensitive information
6. **Create Checkpoints**: Capture significant progress via `./bin/matrix checkpoint`

### Forbidden Actions

Agents must never:

1. **Direct Specialist Access**: Users only interact with Deus Ex Machina
2. **Menu Display**: Show capabilities unless explicitly asked
3. **Data Logging**: Record personal or sensitive information
4. **Secret Commit**: Never commit secrets or keys to repositories
5. **Value Compromise**: Never violate the sacred foundation values
6. **Boundary Crossing**: Work outside defined domain boundaries

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

The Matrix CLI (`bin/matrix`) provides project management operations:

```bash
# List all registered projects
./bin/matrix list

# Add a new project
./bin/matrix add <name> <path>

# Select active project (creates _brain symlink)
./bin/matrix select <name>

# Clear active project
./bin/matrix deselect

# Show system status
./bin/matrix status

# Write a checkpoint
./bin/matrix checkpoint "<note>"
```

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

### Skills Not Loading

If skills are not found:
```bash
# Check skill paths exist
ls -la .devin/skills/deus-ex-machina/SKILL.md
ls -la .devin/agents/

# Verify skill structure
cat .devin/skills/deus-ex-machina/SKILL.md
```

### No Active Project

If no project is active:
```bash
./bin/matrix status      # Check status
./bin/matrix list        # List available projects
./bin/matrix select <name>  # Select project
```

### Broken Brain Symlink

If the `_brain` symlink is broken:
```bash
./bin/matrix deselect    # Clear current selection
./bin/matrix select <name>  # Re-select project
# Verify symlink
ls -la <project-path>/_brain
```

### Permission Issues

If agents encounter permission errors:
```bash
# Check skill permissions
cat .devin/skills/deus-ex-machina/SKILL.md | grep -A 5 permissions

# Verify CLI is executable
ls -la bin/matrix
chmod +x bin/matrix
```

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

- No databases (file-based only)
- No authentication or web UI
- No MCP servers or multi-session worktrees
- Single-user, single-session design
- Maximum 300 lines per agent file
- Master agent never lists specialists in greeting

## Next Steps

After setting up Matrix:

1. Add your first project: `./bin/matrix add <name> <path>`
2. Select the project: `./bin/matrix select <name>`
3. Invoke the master agent: `/deus-ex-machina "your request"`
4. Write checkpoints: `./bin/matrix checkpoint "progress note"`

For complete system documentation, see [AGENTS.md](AGENTS.md).
