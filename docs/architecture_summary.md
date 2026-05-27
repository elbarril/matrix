# Architecture Summary

This document summarizes the dependency risk analysis and portability assessment for the Matrix system.

## 1. Dependency Risk Analysis

### 1.1 High-Risk Dependencies
* **`run_subagent` Tool**: The entire multi-agent topology depends on this single proprietary API call provided by the Devin environment. If this API changes, is deprecated, or is unavailable in another runtime, the Star Topology breaks immediately.
* **LLM Prompt Comprehension**: The orchestration is written in English (`routing-rules.md`, `<activation>` logic). Moving to a smaller or less capable model (e.g., from GPT-4 class / SWE class down to a smaller local model) risks severe orchestration failures, hallucinated routing, and ignored coordination rules.

### 1.2 Medium-Risk Dependencies
* **Filesystem Symlinking (`_brain`)**: Works flawlessly on POSIX/Linux. Will fail entirely on Windows without Admin privileges, or inside strictly isolated container environments that do not permit symlinks across bound volumes.
* **CLI Utility Tooling**: Reliance on `jq`, `flock`, and `sed`. If executed in an Alpine container without these installed, `bin/matrix` validation and state scripts will crash.

### 1.3 Low-Risk Dependencies
* **Markdown Configuration**: Storing agent configurations as Markdown files with YAML frontmatter is highly resilient and universally parseable.
* **File-Based State (FSaDB)**: Storing state in JSONL/JSON files rather than SQLite makes the system incredibly portable and easy to version control.

## 2. Portability Assessment

**Target**: Porting Matrix to OpenHands, Claude Code, or an agnostic Agentic framework.
**Effort Estimate**: Moderate to High.

### 2.1 What works out-of-the-box (Highly Portable)
* **The CLI Orchestrator**: `bin/matrix` and its context handling.
* **The Prompts**: The personas, boundaries, and XML tagging structures.
* **The State Engine**: `.context.yaml` and checkpoints.

### 2.2 What must be refactored (Portability Requirements)
To replace the Devin runtime, an **Abstraction Layer** must be built:
1. **Agent Spawner Shim**: A script or framework-level translation that intercepts the LLM's desire to route to a specialist (currently `run_subagent`) and translates it into the target framework's multi-agent API (e.g., spawning a new thread in Claude Code, or a new agent instance in OpenHands).
2. **YAML Frontmatter Parser**: Devin natively understands `allowed-tools` and `permissions` in the Markdown headers. A custom script is needed to parse these headers and instantiate the sandbox permissions in the new runtime.
3. **Tool Mapping**: Proprietary tools (`todo_write`, `skill invoke`) must be mapped to native equivalents (e.g., a standard file write to `todo.md`, or a standard shell execution).

### 2.3 Conclusion
The architecture is elegantly simple on the data/storage side, but dangerously coupled to the provider on the execution/orchestration side. Because orchestration relies on the LLM "reading the manual" (prompt-driven routing), the portability of this system depends entirely on creating a compatible `run_subagent` shim in the target runtime.
