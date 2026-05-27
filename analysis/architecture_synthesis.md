# Architecture Synthesis

This document synthesizes the findings from the analysis artifacts into a cohesive conceptual model of the Matrix Intelligence Engine.

## 1. The True Orchestration Model

**Verified Architecture:**
The Matrix system is an **LLM-Evaluated State Machine** driven by a **Hierarchical Master-Specialist** topology. 

Unlike traditional software orchestration where a central process (like a Python loop or temporal workflow) dictates execution, Matrix delegates the orchestration entirely to the LLM's context window. The `Deus Ex Machina` agent acts as the CPU. It "boots" by executing bash validation scripts, reads external markdown files (`routing-rules.md`, `coordination-patterns.md`) into its context, and then evaluates the user's prompt against these textual rules to determine its next action (typically invoking `run_subagent`).

**Inferred Architecture:**
Because the orchestration lives inside the LLM prompt rather than code, it is highly dependent on the model's reasoning capabilities (`swe-1-5`). The system assumes the LLM will rigidly follow the sequence defined in `<activation>`.

## 2. Architectural Patterns

1. **Star Topology (Hierarchical Dispatch):** `Deus Ex Machina` is the sole entry point. It fans out tasks to Specialists (`Smith`, `Trinity`, etc.) and aggregates their responses.
2. **File-System as Database (FSaDB):** There is no RDBMS. State (`.context.yaml`, checkpoints, logs) is stored in YAML/JSON. Concurrency is handled poorly or using basic bash `flock`.
3. **Workspace Override Pattern:** Specialized routing overrides standard context. The `Wachowski` agent takes over entirely if the user is operating in the `~/www/emisrepos/matrix` directory.
4. **Symlink Bridging (`_brain`):** Provides a portable execution context. Agents running in remote directories can access global Matrix state by following the `_brain` symlink back to the root repository.

## 3. System Boundaries and Execution Model

### 3.1 Boundaries
* **User Boundary:** Users interface exclusively with `Deus Ex Machina`. Direct invocation of specialists is forbidden.
* **Provider Boundary:** The system relies on Devin/Windsurf capabilities (e.g., `run_subagent`, sandboxed bash access, `skill invoke`).
* **State Boundary:** File mutations happen inside `brain/` or the active project dir.

### 3.2 Execution Model
1. **Pre-Flight (Code-Driven):** `bin/matrix` selects the context. `matrix-validate-config.sh` and related scripts validate the environment.
2. **Context Assembly (Prompt-Driven):** `Deus Ex Machina` reads the validated state and the routing assets into its prompt.
3. **Evaluation (LLM-Driven):** The Master LLM decides which Specialist is needed.
4. **Delegation (Provider-Driven):** Master invokes `run_subagent`.
5. **Specialist Loop (Agent-Driven):** The Specialist reads its `<activation>`, uses tools (`grep`, `edit`, `todo_write`), and returns.
6. **Finalization (Code/Prompt-Driven):** Master writes to `work-process-log.yaml` and reports back via Neo/Cypher protocols.

## 4. Responsibility Separation & Mixed Concerns

**Verified Separation:**
* **Git Operations:** Strictly isolated to `Keymaker`.
* **Matrix Maintenance:** Strictly isolated to `Wachowski`.
* **State vs. Orchestration:** State is neatly separated into YAML files (`brain/state/`), while orchestration rules are in Markdown (`resources/assets/routing/`).

**Mixed Concerns (Hidden Complexity):**
* **Prompt/Code Coupling:** `<activation>` blocks mix natural language commands (e.g., "Understand the problem") with hardcoded bash script execution commands. 
* **State Manipulation:** The Master LLM is trusted to manually append logs to `work-process-log.yaml` using `matrix-log-entry.sh`. If the LLM hallucinates the bash command parameters, the log corrupts.

## 5. Summary of Certainty

* **HIGH Confidence (Verified):** The File-based state model, the Star Topology of agents, the use of `run_subagent` for delegation, the `_brain` symlink mechanism.
* **MEDIUM Confidence (Inferred):** The rigidity of the prompt-driven routing. While the rules are explicitly written, whether the LLM reliably executes complex multi-specialist coordination without faltering depends on the underlying model's compliance.
* **LOW Confidence (Speculative):** How the system behaves under high concurrency or context-window overflow. The current file-locking and logging mechanisms seem designed for single-user sequential interaction.
