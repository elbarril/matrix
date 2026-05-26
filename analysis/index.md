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

## Phase Status

| Phase                            | Status    | Artifact                         |
| -------------------------------- | --------- | -------------------------------- |
| Phase 1 — Repository Mapping     | Complete  | phase1_repository_mapping.md     |
| Phase 2 — Execution Flow         | Complete  | phase2_execution_flow.md         |
| Phase 3 — Agent Analysis         | Complete  | phase3_agents.md                 |
| Phase 4 — Provider Coupling      | Complete  | phase4_provider_coupling.md      |
| Phase 5 — State | Phase 5 — State & Memory         | Pending   | phase5_state_memory.md           | Memory         | Complete  | phase5_state_memory.md           |
| Phase 6 — Prompt Architecture    | Pending   | phase6_prompt_architecture.md    |
| Phase 7 — Architecture Synthesis | Pending   | phase7_architecture_synthesis.md |
| Phase 8 — Refactor Preparation   | Pending   | phase8_refactor_strategy.md      |

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

(To be populated incrementally)

### Phase 3 Artifacts
* [Phase 3 Agents Analysis](phase3_agents.md)
* [Agent Dependency Graph](agent_dependency_graph.md)
* [Agent Capabilities JSON](agent_capabilities.json)

### Phase 4 Artifacts
* [Phase 4 Provider Coupling](phase4_provider_coupling.md)
* [Provider Coupling JSON](provider_coupling.json)

### Phase 5 Artifacts
* [Phase 5 State & Memory Analysis](phase5_state_memory.md)
* [State Flow JSON](state_flow.json)
