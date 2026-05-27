# Agent System Analysis

This document analyzes all agent-like entities in the Matrix system, detailing their execution models, capabilities, statefulness, and dependencies.

## 1. System-Level Architecture

The Matrix system employs a **Hierarchical Master-Specialist Architecture**.

* **Topology**: Star topology (Master in center, Specialists at edges).
* **Execution Model**: Hierarchical, Planner/Executor at the master level, with Reactive and Sequential execution at the specialist level.
* **Statefulness**: The system itself is **stateful**, utilizing file-based storage (`brain/state/checkpoints.jsonl`, `.context.yaml`, `work-process-log.jsonl`), but individual agents are mostly **stateless** across invocations, picking up context from the file system.
* **Autonomy**: High within constrained boundaries. Agents perform self-directed loops but cannot autonomously cross domain boundaries.

## 2. Agent Profiles

### 2.1 Deus Ex Machina (Master Agent)

* **Purpose**: Global Matrix coordinator and sole user interface. Routes tasks to appropriate specialists and coordinates multi-specialist workflows.
* **Triggers**: User input, CLI invocation (`/deus-ex-machina`), Skill invocation.
* **Execution Model**: Planner/Executor, Hierarchical Coordinator.
* **Statefulness**: Stateful (manages and interacts with `brain/state/` and `.context.yaml`).
* **Inputs**: User prompts, system state files, validation scripts, Neo/Cypher protocols.
* **Outputs**: Routed tasks (via `run_subagent`), checkpoints, aggregated user responses.
* **Provider Assumptions**: `swe-1-5` model class. Assumes capability for complex intent parsing and multi-step tool execution.
* **Dependencies**: `brain/config.yaml`, `.context.yaml`, specialist agent markdown definitions, routing assets.

### 2.2 Smith (Specialist)

* **Purpose**: Bug detection, root cause analysis, and technical issue resolution.
* **Triggers**: Routed by Master (keywords: bug, error, debug).
* **Execution Model**: Reactive, Sequential problem solver.
* **Statefulness**: Stateless (relies on repo files).
* **Inputs**: Error logs, codebase, bug descriptions.
* **Outputs**: Root cause analysis reports, bug fix implementations, debugging session logs.
* **Dependencies**: Coordination with Keymaker for git operations, Trinity for architecture.

### 2.3 Morpheus (Specialist)

* **Purpose**: Strategic planning, roadmap creation, and project organization.
* **Triggers**: Routed by Master (keywords: plan, roadmap, estrategia).
* **Execution Model**: Planner.
* **Statefulness**: Stateless.
* **Inputs**: Project requirements, research data from Oracle.
* **Outputs**: Roadmaps, strategic plans, workflow definitions.
* **Dependencies**: Coordination with Trinity (feasibility), Oracle (research), Sentinel (security).

### 2.4 Oracle (Specialist)

* **Purpose**: Research, information synthesis, and pattern identification.
* **Triggers**: Routed by Master (keywords: investiga, busca, research).
* **Execution Model**: Reactive, Web/System Searcher.
* **Statefulness**: Stateless.
* **Inputs**: Search queries, system files.
* **Outputs**: Research reports, pattern analysis.
* **Dependencies**: Web fetch tools, file system access. Coordinates with Morpheus and Sion.

### 2.5 Trinity (Specialist)

* **Purpose**: Code design, architecture, implementation, and technical solution development.
* **Triggers**: Routed by Master (keywords: diseña, arquitectura, implementar).
* **Execution Model**: Executor, Autonomous within implementation scope.
* **Statefulness**: Stateless.
* **Inputs**: Specifications, roadmaps (from Morpheus), codebase.
* **Outputs**: Implementation code, architecture designs, tests.
* **Dependencies**: Coordination with Architect (review), Smith (debugging).

### 2.6 Architect (Specialist)

* **Purpose**: Code review, quality assurance, and best practices validation.
* **Triggers**: Routed by Master for quality checks.
* **Execution Model**: Reactive, Reviewer.
* **Statefulness**: Stateless.
* **Inputs**: Code changes (from Trinity/Smith).
* **Outputs**: Code review reports, improvement suggestions.
* **Dependencies**: Codebase state, Trinity (for implementation).

### 2.7 Sentinel (Specialist)

* **Purpose**: Security analysis, vulnerability detection, and protection.
* **Triggers**: Routed by Master for security-related queries or audits.
* **Execution Model**: Reactive, Auditor.
* **Statefulness**: Stateless.
* **Inputs**: Codebase, architecture plans.
* **Outputs**: Vulnerability reports, security recommendations.
* **Dependencies**: Morpheus (for planning), Trinity/Architect (for implementation).

### 2.8 Sion (Specialist)

* **Purpose**: Documentation creation and knowledge organization.
* **Triggers**: Routed by Master for documentation tasks.
* **Execution Model**: Sequential Writer.
* **Statefulness**: Stateless.
* **Inputs**: Source code, research reports, system schemas.
* **Outputs**: Documentation markdown, knowledge base updates.
* **Dependencies**: Oracle (research), overall system state.

### 2.9 Keymaker (Specialist)

* **Purpose**: Git operations specialist handling all version control tasks.
* **Triggers**: Explicit git operations routed by Master.
* **Execution Model**: Reactive, Executor.
* **Statefulness**: Interacts with Git state (repository).
* **Inputs**: Commit messages, branch names, repository state.
* **Outputs**: Commits, branches, merges, git status updates.
* **Dependencies**: Git CLI. All other agents depend on Keymaker for version control.

### 2.10 Wachowski (Specialist)

* **Purpose**: Matrix system integral specialist. Handles all Matrix workspace and system update tasks.
* **Triggers**: Matrix Workspace Mode detection.
* **Execution Model**: Autonomous (analyze → plan → implement → verify → document). Self-sufficient.
* **Statefulness**: Stateful (modifies Matrix system files and core configurations).
* **Inputs**: Matrix system codebase, self-improvement prompts.
* **Outputs**: System updates, proactive improvement proposals.
* **Dependencies**: None. Fully integrated capabilities.

## 3. Agent Execution Typology Summary

| Agent | Typology | Statefulness | Primary Capability |
|-------|----------|--------------|-------------------|
| Deus Ex Machina | Hierarchical Planner | Stateful | Routing, Coordination |
| Wachowski | Autonomous Integrated | Stateful | Matrix Maintenance |
| Smith | Reactive Executor | Stateless | Debugging |
| Morpheus | Planner | Stateless | Strategy |
| Oracle | Reactive Searcher | Stateless | Research |
| Trinity | Autonomous Executor | Stateless | Implementation |
| Architect | Reactive Reviewer | Stateless | Quality Assurance |
| Sentinel | Reactive Auditor | Stateless | Security |
| Sion | Sequential Writer | Stateless | Documentation |
| Keymaker | Reactive Executor | External (Git) | Version Control |
