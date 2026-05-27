# Analysis Index

## Repository

matrix

## Objective

Reverse engineer the orchestration architecture, execution model, provider coupling, and agent system in order to:

* deeply understand the system,
* identify architectural boundaries,
* enable safe refactoring,
* and support portability across runtimes/providers such as:

  * Devin
  * Claude Code
  * Gemini CLI
  * Codex CLI
  * OpenHands

---

## Analysis Artifacts

| Artifact                        | Status    |
| ------------------------------- | --------- |
| Repository Mapping              | Complete  |
| Execution Flow Reconstruction   | Complete  |
| Agent System Analysis           | Complete  |
| Provider Coupling Analysis      | Complete  |
| State and Memory Analysis       | Complete  |
| Prompt Architecture Analysis     | Complete  |
| Architecture Synthesis          | Complete  |

---

## Shared Artifacts

| Artifact                  | Purpose                |
| ------------------------- | ---------------------- |
| glossary.md               | Repository terminology |
| dependency_inventory.json | Dependency map         |
| execution_nodes.json      | Execution graph nodes  |
| provider_coupling.json    | Provider dependencies  |
| agent_inventory.json      | Agent definitions      |
| runtime_inventory.json    | Runtime assumptions    |

---

## Canonical Findings

### Agent System Analysis
* [Agent System Analysis](agents.md)
* [Agent Dependency Graph](agent_dependency_graph.md)
* [Agent Capabilities JSON](agent_capabilities.json)

### Provider Coupling Analysis
* [Provider Coupling Analysis](provider_coupling.md)
* [Provider Coupling JSON](provider_coupling.json)

### State and Memory Analysis
* [State and Memory Analysis](state_memory.md)
* [State Flow JSON](state_flow.json)

### Prompt Architecture Analysis
* [Prompt Architecture Analysis](prompt_architecture.md)
* [Prompt Inventory JSON](prompt_inventory.json)

### Architecture Synthesis
* [Architecture Synthesis](architecture_synthesis.md)
* [Runtime Interaction Graph](runtime_interaction_graph.md)
* [Architecture Summary](architecture_summary.md)
