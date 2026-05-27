# Runtime Interaction Graphs

This document contains visual representations of the synthesized Matrix architecture.

## 1. High-Level Architecture Diagram

```mermaid
graph TD
    subgraph "External Boundary"
        User((User))
    end

    subgraph "Matrix Core (Code-Driven)"
        CLI[bin/matrix]
        Validation[Validation Scripts]
        Logger[Logging Scripts]
    end

    subgraph "State Layer (FSaDB)"
        Registry[.registry.json]
        Context[.context.yaml]
        State[brain/state/]
    end

    subgraph "Intelligence Layer (Prompt-Driven)"
        DEM[Deus Ex Machina]
        Routing[Routing Rules Markdown]
        Specialists[Specialist Agents]
    end

    subgraph "Provider Layer"
        Windsurf[Devin / Windsurf Runtime]
    end

    %% Flow
    User -->|CLI Commands| CLI
    User -->|Prompts| DEM
    
    CLI -->|Mutates| Context
    CLI -->|Mutates| Registry
    
    DEM -->|Reads| Routing
    DEM -->|Reads| Context
    DEM -->|Executes| Validation
    DEM -->|Executes| Logger
    
    Logger -->|Appends| State
    
    DEM -->|Invokes via run_subagent| Windsurf
    Windsurf -->|Spawns| Specialists
    
    Specialists -->|Mutates FS| State
```

## 2. Runtime Execution Interaction

```mermaid
sequenceDiagram
    participant User
    participant CLI as bin/matrix
    participant DEM as Deus Ex Machina
    participant OS as Bash / OS
    participant LLM as Provider Runtime
    participant Spec as Specialist (e.g., Trinity)

    User->>CLI: matrix select <project>
    CLI->>OS: Write .context.yaml & _brain symlink
    
    User->>DEM: <Prompt>
    DEM->>OS: Execute matrix-validate-config.sh
    OS-->>DEM: Validation OK
    
    DEM->>OS: Read routing-rules.md
    OS-->>DEM: <Routing Text>
    
    Note over DEM,LLM: Prompt-Driven Evaluation
    DEM->>LLM: Evaluate routing rules against User Prompt
    LLM-->>DEM: Decision: Invoke Trinity
    
    DEM->>LLM: tool: run_subagent(Trinity, Context)
    LLM->>Spec: Spawn stateless agent
    
    Spec->>OS: Read _brain/config.yaml
    Spec->>OS: Execute tasks (edit, grep, write)
    Spec-->>LLM: Return output
    LLM-->>DEM: Specialist completed
    
    DEM->>OS: Execute matrix-log-entry.sh
    DEM->>User: <Neo Protocol Response>
```

## 3. Agent Interaction Graph

```mermaid
graph TD
    DEM{Deus Ex Machina}
    
    DEM -- "run_subagent" --> Trinity[Trinity<br>Code/Design]
    DEM -- "run_subagent" --> Smith[Smith<br>Bugs/Debug]
    DEM -- "run_subagent" --> Oracle[Oracle<br>Research]
    DEM -- "run_subagent" --> Morpheus[Morpheus<br>Planning]
    DEM -- "run_subagent" --> Architect[Architect<br>Review]
    DEM -- "run_subagent" --> Sentinel[Sentinel<br>Security]
    DEM -- "run_subagent" --> Sion[Sion<br>Docs]
    DEM -- "run_subagent" --> Keymaker[Keymaker<br>Git Ops]
    
    DEM -- "Workspace Override" --> Wachowski[Wachowski<br>Self-Sufficient System Maintainer]
    
    %% Coordination
    Trinity -. "Delegates Git" .-> Keymaker
    Smith -. "Delegates Git" .-> Keymaker
    Morpheus -. "Requires Research" .-> Oracle
    Trinity -. "Requires QA" .-> Architect
    
    classDef master fill:#f9f,stroke:#333,stroke-width:2px;
    classDef agent fill:#bbf,stroke:#333,stroke-width:1px;
    classDef special fill:#bfb,stroke:#333,stroke-width:2px;
    
    class DEM master;
    class Trinity,Smith,Oracle,Morpheus,Architect,Sentinel,Sion,Keymaker agent;
    class Wachowski special;
```
