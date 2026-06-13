# Repository Glossary

This glossary preserves repository-native terminology and prevents conceptual drift during analysis.

---

## Terminology Rules

* Preserve original repository terminology whenever possible.

* Distinguish between:

  * explicit terminology,
  * inferred terminology,
  * mapped abstractions.

* Do not rename concepts prematurely.

---

## Terms

### Deus Ex Machina

Status: EXPLICIT
Confidence: HIGH

Observed References:

* `.agents/skills/deus-ex-machina/SKILL.md` (master agent skill definition)
* `AGENTS.md` (master agent role and responsibilities)
* `README.md` (system architecture description)
* `DEVIN.md` (master agent interface)

Possible Meaning:

* Master coordinator agent - sole user interface for the Matrix system
* Global intelligence with cross-session awareness and control
* Routing intelligence to specialist agents

Mapped Abstractions:

* Master agent / coordinator
* Skill (Devin native)
* Orchestrator

---

### Agent

Status: EXPLICIT
Confidence: HIGH

Observed References:

* `.agents/agents/*/AGENT.md` (specialist agent definitions)
* `AGENTS.md` (agent architecture and contract)
* `README.md` (specialist agents list)

Possible Meaning:

* Devin subagent with specific domain expertise
* Specialist with defined boundaries and capabilities
* Invoked only by Deus Ex Machina (never directly by users)

Mapped Abstractions:

* Subagent (Devin native)
* Specialist
* Domain expert

---

### Skill

Status: EXPLICIT
Confidence: HIGH

Observed References:

* `.agents/skills/deus-ex-machina/SKILL.md` (master agent as skill)
* `DEVIN.md` (skill structure)
* `brain/config/global-skills.yaml` (global skills integration)

Possible Meaning:

* Devin native skill definition with YAML frontmatter
* Master agent implemented as skill
* External skills integration capability

Mapped Abstractions:

* Devin skill
* Master agent implementation
* External integration point

---

### Specialist

Status: EXPLICIT
Confidence: HIGH

Observed References:

* `AGENTS.md` (specialist agents section)
* `README.md` (specialist agents list)
* Routing resources (specialist triggers, coordination patterns)

Possible Meaning:

* Domain-specific expert agent
* One of 9 defined specialists (Smith, Morpheus, Oracle, Trinity, Architect, Sentinel, Sion, Wachowski, Keymaker)
* Invoked via routing by Deus Ex Machina

Mapped Abstractions:

* Domain expert
* Subagent
* Specialist agent

---

### Matrix Workspace Mode

Status: EXPLICIT
Confidence: HIGH

Observed References:

* `AGENTS.md` (Matrix Workspace Mode section)
* `.agents/skills/deus-ex-machina/resources/assets/routing/routing-rules.md` (Matrix Workspace Mode rule)
* `.agents/skills/deus-ex-machina/resources/assets/routing/rules/specialist-specific-rules.md` (Wachowski special routing)

Possible Meaning:

* Special mode when working in Matrix root directory
* Skips context loading, routes all requests to Wachowski
* Ensures Matrix system work doesn't interfere with project work

Mapped Abstractions:

* System maintenance mode
* Root directory mode
* Wachowski-only routing mode

---

### _brain Symlink

Status: EXPLICIT
Confidence: HIGH

Observed References:

* `AGENTS.md` (_brain-Aware Path Resolution Pattern)
* `README.md` (Symlink Bridge section)
* `DEVIN.md` (Active Project Context section)

Possible Meaning:

* Symlink from active project to Matrix brain directory
* Provides portable access to intelligence layer
* Enables agents to work from active projects

Mapped Abstractions:

* Brain bridge
* Intelligence layer symlink
* Portable state access

---

### Checkpoint

Status: EXPLICIT
Confidence: HIGH

Observed References:

* `AGENTS.md` (Checkpoint format section)
* `bin/matrix` (checkpoint command)
* `brain/state/checkpoints/` (checkpoint files)

Possible Meaning:

* Timestamped progress marker
* Captures project state and progress
* Written via CLI or auto-checkpoint by agents

Mapped Abstractions:

* Progress marker
* State snapshot
- Milestone record

---

### Work Process Log

Status: EXPLICIT
Confidence: HIGH

Observed References:

* `AGENTS.md` (Work Process Logging section)
* `brain/state/work-process-log.jsonl` (log file)
* `.agents/skills/deus-ex-machina/scripts/matrix-log-entry.sh` (logging script)

Possible Meaning:

* Comprehensive logging of all work processes
* Tracks activation, routing, specialist execution, checkpoints
* Rotates after 1000 entries

Mapped Abstractions:

* Activity log
* Execution trace
* Work audit trail

---

### Context

Status: EXPLICIT
Confidence: HIGH

Observed References:

* `.context.yaml` (active project context)
* `brain/config/projects/*.yaml` (project-specific context)
* `.agents/skills/deus-ex-machina/resources/assets/routing/routing-rules.md` (context preparation)

Possible Meaning:

* Active project state and configuration
* Project-specific settings and preferences
- Used for context-aware routing

Mapped Abstractions:

* Project context
* Active project state
* Configuration context

---

### Routing Resources

Status: EXPLICIT
Confidence: HIGH

Observed References:

* `.agents/skills/deus-ex-machina/SKILL.md` (routing-resources section)
* `.agents/skills/deus-ex-machina/resources/assets/routing/` (routing files)
* `.agents/skills/deus-ex-machina/resources/assets/routing/routing-rules.md` (routing protocol)

Possible Meaning:

* Externalized routing intelligence
* Specialist triggers, coordination patterns, routing rules
* Loaded during activation for routing decisions

Mapped Abstractions:

* Routing intelligence
* Decision logic
* Specialist mapping

---

### Activation Protocol

Status: EXPLICIT
Confidence: HIGH

Observed References:

* `.agents/skills/deus-ex-machina/SKILL.md` (activation section)
* `AGENTS.md` (Activation Pattern section)
* `.agents/skills/deus-ex-machina/scripts/matrix-validate-activation.sh` (validation script)

Possible Meaning:

* Defined sequence of steps for agent activation
* Enforced via validation scripts
* Includes pre-activation checks and post-activation validation

Mapped Abstractions:

* Startup sequence
* Initialization protocol
* Activation flow

---

### Sacred Foundation

Status: EXPLICIT
Confidence: HIGH

Observed References:

* `AGENTS.md` (Sacred Foundation section)
* `README.md` (Core Values section)

Possible Meaning:

* Non-negotiable core values baked into master agent persona
* 7 sacred foundation values
* Never compromised

Mapped Abstractions:

* Core values
* Immutable principles
* Foundation values

---

### Global Skills

Status: EXPLICIT
Confidence: HIGH

Observed References:

* `brain/config/global-skills.yaml` (configuration)
* `.agents/skills/deus-ex-machina/resources/assets/routing/routing-rules.md` (global skills integration)
* `/opt/aiad-common/skills/` (skills path)

Possible Meaning:

* External Devin skills integrated with Matrix
* Context-aware usage patterns
* Priority: local skills > global skills > Matrix specialists

Mapped Abstractions:

* External skills
* Shared skills
* Community skills

---

### Coordination Pattern

Status: EXPLICIT
Confidence: HIGH

Observed References:

* `.agents/skills/deus-ex-machina/resources/assets/routing/coordination-patterns.md` (pattern definitions)
* `.agents/skills/deus-ex-machina/resources/assets/routing/routing-rules.md` (multi-specialist routing)

Possible Meaning:

* Predefined patterns for multi-specialist coordination
* 7 defined patterns for different specialist combinations
* Used when request triggers multiple specialist domains

Mapped Abstractions:

* Multi-specialist pattern
* Collaboration pattern
* Specialist workflow

---

### Wachowski

Status: EXPLICIT
Confidence: HIGH

Observed References:

* `.agents/agents/wachowski/AGENT.md` (agent definition)
* `.agents/skills/deus-ex-machina/resources/assets/routing/specialist-triggers.md` (trigger keywords)
* `.agents/skills/deus-ex-machina/resources/assets/routing/rules/specialist-specific-rules.md` (special routing rules)

Possible Meaning:

* Matrix system integral specialist
* Self-sufficient with all specialist capabilities built-in
* Handles all Matrix workspace tasks without coordination

Mapped Abstractions:

* Matrix system specialist
* Integral specialist
* Self-sufficient agent

---

### Keymaker

Status: EXPLICIT
Confidence: HIGH

Observed References:

* `.agents/agents/keymaker/AGENT.md` (agent definition)
* `AGENTS.md` (Git Operations Policy)
* `.agents/skills/deus-ex-machina/resources/assets/routing/rules/specialist-specific-rules.md` (explicit request rule)

Possible Meaning:

* Git operations specialist
* Only invoked when user explicitly requests git operations
* Handles all git-related tasks safely

Mapped Abstractions:

* Git specialist
* Version control specialist
* Git operations handler

---

### Neo

Status: EXPLICIT
Confidence: HIGH

Observed References:

* `.agents/skills/deus-ex-machina/SKILL.md` (neo-communication-protocol)

Possible Meaning:

* Communication protocol for final confirmations and success messages
* Handles task completion, production deploy announcements, error fix verification
* Output passed to user exactly as generated

Mapped Abstractions:

* Success communicator
* Confirmation handler
* Positive outcome messenger

---

### Cypher

Status: EXPLICIT
Confidence: HIGH

Observed References:

* `.agents/skills/deus-ex-machina/SKILL.md` (cypher-communication-protocol)

Possible Meaning:

* Communication protocol for problem communication and error reporting
* Handles errors, failures, issues, blockers
* Output passed to user exactly as generated

Mapped Abstractions:

* Error communicator
* Problem reporter
* Negative outcome messenger

---

### Phase (Removed)

Status: REMOVED - No longer relevant after analysis completion

The "Phase" terminology was used during the reverse engineering process but is no longer applicable now that the analysis artifacts are complete. The analysis directory now contains independent artifacts without phase-based organization.

---

### Pre-Activation Validation

Status: EXPLICIT
Confidence: HIGH

Observed References:

* `.agents/skills/deus-ex-machina/SKILL.md` (pre-activation-checks section)
* `.agents/skills/deus-ex-machina/scripts/matrix-validate-config.sh` (config validation)
* `.agents/skills/deus-ex-machina/scripts/matrix-validate-context.sh` (context validation)
* `.agents/skills/deus-ex-machina/scripts/matrix-validate-routing-resources.sh` (routing validation)
* `.agents/skills/deus-ex-machina/scripts/matrix-init-brain-state.sh` (state initialization)

Possible Meaning:

* Multi-stage validation before agent activation
* Sequential validation scripts that must all pass
* Configuration, context, routing resources, and brain state validation

Mapped Abstractions:

* Startup validation
* Pre-flight checks
* Activation validation

---

### Consolidated Logging

Status: EXPLICIT
Confidence: HIGH

Observed References:

* `.agents/skills/deus-ex-machina/SKILL.md` (work-process-logging section)
* `.agents/skills/deus-ex-machina/scripts/matrix-log-entry.sh` (logging script)
* Activation logging (consolidated format)
* Specialist execution logging (consolidated format)

Possible Meaning:

* Single log event instead of multiple events
* Reduces log verbosity while maintaining traceability
* Activation: single event instead of 5 activation_step events
* Specialist execution: single event instead of invocation + completion

Mapped Abstractions:

* Unified logging
* Reduced verbosity logging
* Consolidated event logging

---

### Context-Aware Skill Priority Routing

Status: EXPLICIT
Confidence: HIGH

Observed References:

* `.agents/skills/deus-ex-machina/resources/assets/routing/routing-rules.md` (Context-Aware Skill Priority Routing section)
* `brain/config/projects/*.yaml` (skill_priority setting)
* `brain/config/global-skills.yaml` (global skills integration)

Possible Meaning:

* Routing logic based on context configuration
* Priority modes: local_first, matrix_first, hybrid
* Priority hierarchy: local skills > global skills > Matrix specialists

Mapped Abstractions:

* Context-based routing
* Priority routing
* Skill hierarchy routing

---

### Integrated Execution Pattern

Status: EXPLICIT
Confidence: HIGH

Observed References:

* `.agents/agents/wachowski/AGENT.md` (activation section, rule 11, rule 17)
* `.agents/skills/deus-ex-machina/resources/assets/routing/specialist-triggers.md` (Wachowski Execution Pattern)
* Wachowski capacity integration (Oracle → Morpheus → Trinity → Architect → Sion)

Possible Meaning:

* Wachowski's default execution pattern
* Integrates all specialist capacities in single cohesive flow
* Avoids artificial separation unless genuinely interdependent phases required

Mapped Abstractions:

* Unified capacity flow
* Single-execution pattern
* Integrated specialist flow

---

### Multi-Call Pattern

Status: EXPLICIT
Confidence: HIGH

Observed References:

* `.agents/agents/wachowski/AGENT.md` (multi-call-protocol section)
* `.agents/skills/deus-ex-machina/resources/assets/routing/rules/specialist-specific-rules.md` (Wachowski Multi-Call Pattern)
* Complexity criteria (>300 chars, 3+ verbs, explicit phases keyword, >5 files)

Possible Meaning:

* Wachowski execution pattern for genuinely complex tasks
* Structured phase specification with sequential calls
* Strict complexity criteria (ALL 4 conditions must be met)

Mapped Abstractions:

* Sequential execution
* Phase-based execution
* Complex task splitting

---

### Context Passing

Status: EXPLICIT
Confidence: HIGH

Observed References:

* `.agents/skills/deus-ex-machina/SKILL.md` (rule 6: Context passing)
* `.agents/skills/deus-ex-machina/resources/assets/routing/coordination-patterns.md` (context passing between specialists)
* Multi-specialist coordination patterns

Possible Meaning:

* Passing findings and context between specialists in coordination patterns
* Sequential context propagation in multi-specialist workflows
* Enables specialists to build on previous specialist's work

Mapped Abstractions:

* State propagation
* Findings passing
* Specialist chaining

---

### Validation Report

Status: EXPLICIT
Confidence: HIGH

Observed References:

* `.agents/skills/deus-ex-machina/scripts/matrix-validate-activation.sh` (validation script)
* `brain/state/validation-report.json` (report output)
* `.agents/skills/deus-ex-machina/SKILL.md` (post-activation-validation section)

Possible Meaning:

* Post-activation compliance report
* Contains activation status, missing steps, activation log, user request
* Written by .agents/skills/deus-ex-machina/scripts/matrix-validate-activation.sh after activation completes

Mapped Abstractions:

* Compliance report
* Activation validation output
* Post-activation check

---

### Log Rotation

Status: EXPLICIT
Confidence: HIGH

Observed References:

* `AGENTS.md` (Work Process Logging section)
* `.agents/skills/deus-ex-machina/scripts/matrix-log-entry.sh` (log rotation logic)
* `brain/state/work-process-log-archive/` (archive directory)

Possible Meaning:

* Automatic rotation of work-process-log.jsonl after 1000 entries
* Archives old entries to work-process-log-archive/
* Maintains recent entries in active log

Mapped Abstractions:

* Log archival
* Automatic log cleanup
* Log size management

---

### Silent Operation

Status: EXPLICIT
Confidence: HIGH

Observed References:

* `.agents/skills/deus-ex-machina/SKILL.md` (persona section: "Silencio operativo")
* `.agents/agents/wachowski/AGENT.md` (persona section: "Opera en silencio")
* Silent routing rule (no announcements)

Possible Meaning:

* Operating without announcing work steps
* All logging goes to work-process-log.jsonl
* User-facing output only for final results

Mapped Abstractions:

* Quiet operation
* Non-verbose execution
* Background operation

---

### Stopping Condition

Status: EXPLICIT
Confidence: HIGH

Observed References:

* `.agents/skills/deus-ex-machina/SKILL.md` (pre-activation-checks: "If any check fails, halt activation")
* `.agents/skills/deus-ex-machina/resources/assets/routing/coordination-patterns.md` (coordination failure handling)
* Specialist execution failures

Possible Meaning:

* Conditions that halt execution
* Pre-activation validation failures
* Specialist execution failures
* User intervention

Mapped Abstractions:

* Halt condition
* Execution termination
* Stop condition

---

### Orchestration Boundary

Status: EXPLICIT
Confidence: HIGH

Observed References:

* `.agents/skills/deus-ex-machina/SKILL.md` (rules section: routing boundaries)
* `AGENTS.md` (specialist boundaries)
* `.agents/skills/deus-ex-machina/resources/assets/routing/routing-rules.md` (Deus Ex Machina constraints)

Possible Meaning:

* Defined limits for each component's responsibilities
* Deus Ex Machina: routing and coordination only
* Specialists: domain-specific execution only
- Wachowski: self-sufficient for Matrix tasks

Mapped Abstractions:

* Responsibility boundary
* Domain boundary
* Scope limit

---

### _brain-Aware Pattern

Status: EXPLICIT
Confidence: HIGH

Observed References:

* `AGENTS.md` (_brain-Aware Path Resolution Pattern)
* All specialist activation sequences
* All scripts (path resolution)

Possible Meaning:

* Path resolution pattern that tries _brain symlink first
* Falls back to Matrix root path if _brain doesn't exist
* Enables portable access from active projects

Mapped Abstractions:

* Symlink-aware resolution
* Portable path pattern
* Brain bridge pattern

### Routing Priority

Status: INFERRED
Confidence: HIGH

Observed References:
* `brain/config/global-skills.yaml`
* `.agents/skills/deus-ex-machina/resources/assets/routing/routing-rules.md`

Possible Meaning:
* The order of precedence Deus Ex Machina uses when resolving a request: Local Skills > Global Skills > Matrix Specialists.

Mapped Abstractions:
* Tool selection priority
* Agent resolution order

### run_subagent

Status: EXPLICIT
Confidence: HIGH

Observed References:
* `.agents/agents/wachowski/AGENT.md`
* `.agents/skills/deus-ex-machina/resources/assets/routing/rules/specialist-specific-rules.md`
* `.agents/skills/deus-ex-machina/resources/assets/routing/specialist-triggers.md`

Possible Meaning:
* Proprietary Devin tool used to spawn specialist agents as stateless sub-tasks.
* The sole mechanism Deus Ex Machina uses to invoke specialists.

Mapped Abstractions:
* Provider-specific subagent router
* Thread spawner
* Task delegator

### todo_write

Status: EXPLICIT
Confidence: HIGH

Observed References:
* `.agents/agents/trinity/AGENT.md`
* `.agents/agents/smith/AGENT.md`
* `.agents/skills/deus-ex-machina/SKILL.md` (Deus Ex Machina)

Possible Meaning:
* Proprietary Devin tool for creating and managing a structured task list in the agent's UI.

Mapped Abstractions:
* Provider-specific task manager
* UI state integration

### validation-report.json

Status: EXPLICIT
Confidence: HIGH

Observed References:
* `brain/state/validation-report.json`
* `AGENTS.md` (Protocol Violation Troubleshooting)

Possible Meaning:
* An ephemeral file generated post-activation to confirm the agent followed the `<activation>` protocol correctly. Records the user request and missing steps.

Mapped Abstractions:
* Ephemeral run state
* Activation audit artifact

### Prompt-Driven Orchestration

Status: INFERRED
Confidence: HIGH

Observed References:
* `.agents/skills/deus-ex-machina/resources/assets/routing/routing-rules.md`
* `.agents/skills/deus-ex-machina/SKILL.md` (<activation> block)

Possible Meaning:
* Control flow and routing logic that exists as natural language instructions parsed by the LLM context, rather than hardcoded in bash/python scripts. The LLM determines execution sequence by reading markdown files.

Mapped Abstractions:
* LLM-driven state machine
* Natural language orchestration

### LLM-Evaluated State Machine

Status: INFERRED
Confidence: HIGH

Observed References:
* `<activation>` block in `.agents/skills/deus-ex-machina/SKILL.md`
* `.agents/skills/deus-ex-machina/resources/assets/routing/routing-rules.md`

Possible Meaning:
* A system architecture where state transitions (e.g., executing validation scripts, picking an agent, logging) are not hardcoded in Python/Bash loops, but are instead sequentially evaluated and executed by an LLM strictly following a prompt.

Mapped Abstractions:
* Prompt-driven orchestration
* LLM CPU

### File-System as Database (FSaDB)

Status: INFERRED
Confidence: HIGH

Observed References:
* `brain/state/`
* `workspace.yaml`
* `.registry.json`

Possible Meaning:
* The deliberate architectural choice to avoid RDBMS or SQLite in favor of storing all system state, logs, and contexts as raw YAML/JSON files, allowing easy inspection and symlink portability.

Mapped Abstractions:
* File-based State
* Flat-file memory
