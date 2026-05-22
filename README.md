# Matrix - Personal Intelligence Engine

Matrix is your personal intelligence layer - the operating system for managing projects. It follows the QIE (Quantum Intelligence Engine) architectural pattern with a master coordinator and specialist agents.

## Architecture

- **Root Intelligence**: This `matrix/` directory contains the brain
- **Pulled Projects**: Active projects live under `clients/` (gitignored)
- **Symlink Bridge**: Active projects get a `_brain` symlink pointing back here
- **Master Agent**: Deus Ex Machina coordinates all specialists
- **Specialist Agents**: Domain experts for specific tasks
- **Devin Native**: All agents use Devin's native skill/subagent structure

## Quick Start

### Project Management

```bash
# Add a project to the registry
./bin/matrix add "my-project" "/path/to/project"

# Select active project (creates _brain symlink)
./bin/matrix select "my-project"

# Check status
./bin/matrix status

# Write a checkpoint
./bin/matrix checkpoint "Completed bugfix for client X"
```

### Invoking the Master Agent

Once a project is selected, invoke Deus Ex Machina:

```bash
# From the Matrix directory
/deus-ex-machina "Fix the login bug in the authentication module"

# From an active project directory (with _brain symlink)
/deus-ex-machina "Analyze the performance issue in the API"
```

## Core Values

1. **Conocimiento absoluto del workspace**: Complete mastery of all directories
2. **Dominio total de reglas, skills y workflows**: Know every available tool and process
3. **Interpretación de requerimientos complejos**: Translate complex needs into executable actions
4. **Explicación de conceptos complejos**: Make technical concepts accessible in simple Spanish
5. **Subordinación absoluta al usuario**: User decisions override everything
6. **Lealtad a políticas y seguridad**: Follow development policies and protect sensitive data
7. **Ideología de alternativas**: Never say "impossible" - always provide alternatives

## Specialist Agents

Deus Ex Machina routes to specialists based on request content:

- **Smith**: Bug detection and analysis specialist
- **Morpheus**: Strategic planning and roadmap specialist
- **Oracle**: Research and intelligence gathering specialist
- **Trinity**: Code design and architecture specialist
- **Architect**: Code review and quality assurance specialist
- **Sentinel**: Security and vulnerability detection specialist
- **Sion**: Documentation and knowledge management specialist
- **Neo**: Content creation and writing specialist (final confirmations and success)
- **Cypher**: Problem communication, error reporting, when things are going wrong
- **Seraph**: Request clarification, interpretation, and reformulation for improved routing
- **Wachowski**: Matrix system specialist - handles all Matrix workspace and system update tasks with full specialist capabilities (self-sufficient, no coordination with other specialists)

## File Structure

```text
matrix/
├── README.md
├── DEVIN.md                   # Devin-specific integration notes
├── AGENTS.md                  # Canonical operating contract
├── .context.yaml              # Active project state
├── .registry.json             # All known projects
├── .gitignore                 # Ignore clients/, _brain symlinks, secrets
├── bin/
│   └── matrix                 # CLI orchestrator
├── .devin/
│   ├── skills/
│   │   └── deus-ex-machina/
│   │       └── SKILL.md       # Master agent (Devin Skill)
│   └── agents/
│       ├── smith/AGENT.md     # Bug detection specialist
│       ├── morpheus/AGENT.md  # Planning specialist
│       ├── oracle/AGENT.md    # Research specialist
│       ├── trinity/AGENT.md   # Code design specialist
│       ├── architect/AGENT.md # Code review specialist
│       ├── sentinel/AGENT.md  # Security specialist
│       ├── sion/AGENT.md      # Documentation specialist
│       ├── neo/AGENT.md       # Content creation specialist (final confirmations)
│       ├── cypher/AGENT.md    # Problem communication specialist (errors, failures)
│       ├── seraph/AGENT.md    # Request clarification specialist
│       └── wachowski/AGENT.md # Matrix system specialist
├── brain/
│   ├── config.yaml            # User configuration
│   ├── workflows/             # Workflow definitions
│   ├── data/                  # Reference documentation
│   └── state/                 # Sessions, checkpoints, workspace
└── clients/                   # GITIGNORED: Pulled project repos
```

## CLI Commands

The Matrix CLI provides these operations:

- `list`: Show all registered projects
- `add <name> <path>`: Register new project
- `select <name>`: Set active project and create brain symlink
- `deselect`: Clear active project and remove symlink
- `status`: Show current system status
- `checkpoint "<note>"`: Write timestamped checkpoint

## Documentation

- **[AGENTS.md](AGENTS.md)**: Canonical operating contract for all agents
- **[DEVIN.md](DEVIN.md)**: Devin-specific integration notes and session hygiene

## System Safeguards

Matrix includes built-in safeguards to ensure the activation protocol is followed correctly and to detect bypass attempts.

### Pre-Invocation Checks

Before the master agent activates, it verifies all prerequisites:

- **Configuration Check**: Verifies `brain/config.yaml` exists and is valid YAML
- **Context Check**: Verifies `.context.yaml` exists and has active project
- **Routing Resources Check**: Verifies routing resources exist (specialist-triggers.md, coordination-patterns.md, routing-rules.md)
- **Brain State Check**: Verifies `brain/state/` directory structure exists
- **CLI Executability Check**: Verifies Matrix CLI is executable (warning if fails)

If any check fails, the skill halts with a clear error message about what's missing.

### Activation Protocol Enforcement

Each activation step is marked as `[ENFORCED]` in the skill and must be executed:

- Load configuration (must log "Loaded configuration")
- Read context (must log "Loaded context")
- Review recent state (must log state review)
- Load routing resources (must log "Loaded routing resources")
- Greet user in Spanish
- Await user request
- Analyze request for routing
- Execute or route to specialists
- Write checkpoint if significant progress

If any enforced step fails, the skill halts with an error.

### Post-Activation Validation

After activation completes, the skill validates compliance:

- Checks log contains required markers for each enforced step
- Writes validation report to `brain/state/validation-report.yaml`
- Flags non-compliant activations
- Continues in degraded mode if non-compliant (allows work but flags as non-compliant)

### Work Process Logging

All work processes are logged to `brain/state/work-process-log.yaml`:

- Activation steps with timestamps and status
- Routing decisions with detected specialists and patterns
- Specialist invocations with context passed
- Specialist completions with outcomes
- Checkpoint writes

Logs are rotated after 100 entries, with older logs archived to `brain/state/work-process-log-archive/`.

### Troubleshooting Safeguard Issues

**Validation report shows non-compliant activation**:

- Check `brain/state/validation-report.yaml` for missing steps
- Verify all routing resources exist in `.devin/skills/deus-ex-machina/resources/assets/routing/`
- Review `brain/state/work-process-log.yaml` for incomplete logs
- Ensure skill is invoked via `/deus-ex-machina` or skill trigger
- Re-invoke skill with proper Devin mechanism

**Pre-invocation check fails**:

- Check the error message for what's missing
- Verify configuration files exist and are valid YAML
- Verify `.context.yaml` has active project set
- Use `./bin/matrix status` to check system state
- Use `./bin/matrix select <name>` to set active project if needed

**Missing routing resources**:

- Verify `.devin/skills/deus-ex-machina/resources/assets/routing/` directory exists
- Check that `specialist-triggers.md`, `coordination-patterns.md`, and `routing-rules.md` exist
- If missing, restore from repository or create based on AGENTS.md specifications

## Version 1 Constraints

- No databases (file-based only)
- No authentication or web UI
- Single-user, single-session design
- Maximum 300 lines per agent file
- Master agent never lists specialists in greeting

## Usage Example

```bash
# 1. Add your project
./bin/matrix add "my-project" "/path/to/my-project"

# 2. Select it (creates _brain symlink)
./bin/matrix select "my-project"

# 3. Navigate to your project
cd /path/to/my-project

# 4. Invoke the master agent
/deus-ex-machina "I need to fix a bug in the authentication flow"

# 5. Write a checkpoint when done
./bin/matrix checkpoint "Fixed authentication bug - user can now login"
```

## Architecture Principles

1. **Root Intelligence + Pulled Projects**: The root repo is the brain. Project repos are pulled on demand.
2. **Registry First, Pull on Demand**: A registry knows about all projects. Only active ones are cloned locally.
3. **Active Project Context**: A `.context.yaml` file tracks which project is active.
4. **Master + Specialists Pattern**: ONE master agent is the face. Specialists are domain experts the master routes to.
5. **Devin Native Agents**: Each agent uses Devin's native structure (Skills for master, Subagents for specialists).
6. **Sacred Foundation**: Core values are baked into the master agent's persona.
7. **File-Based State**: Memory and state are files, not databases.

## License

Personal intelligence engine for Emiliano's project management.
