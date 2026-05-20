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
- **Neo**: Content creation and writing specialist

## File Structure

```
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
│       └── neo/AGENT.md       # Content creation specialist
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
