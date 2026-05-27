# Agent Dependency Graph

This graph illustrates the hierarchical routing and coordination dependencies between agents in the Matrix system.

```mermaid
graph TD
    %% Core Master Agent
    User((User)) --> DEM[Deus Ex Machina]
    
    %% Workspace Mode
    DEM -- "Matrix Workspace Mode" --> Wachowski[Wachowski<br>Self-Sufficient]
    
    %% Routing to Specialists
    DEM -- "Bug/Error" --> Smith[Smith]
    DEM -- "Plan/Strategy" --> Morpheus[Morpheus]
    DEM -- "Research" --> Oracle[Oracle]
    DEM -- "Code/Design" --> Trinity[Trinity]
    DEM -- "Review/Quality" --> Architect[Architect]
    DEM -- "Security" --> Sentinel[Sentinel]
    DEM -- "Documentation" --> Sion[Sion]
    DEM -- "Git Operations" --> Keymaker[Keymaker]
    
    %% Specialist Coordination (Dotted lines)
    Smith -. "Architecture fixes" .-> Trinity
    Smith -. "Git ops" .-> Keymaker
    
    Morpheus -. "Feasibility" .-> Trinity
    Morpheus -. "Research" .-> Oracle
    Morpheus -. "Security" .-> Sentinel
    
    Oracle -. "Strategic context" .-> Morpheus
    Oracle -. "Docs data" .-> Sion
    
    Trinity -. "Code review" .-> Architect
    Trinity -. "Debugging" .-> Smith
    Trinity -. "Security" .-> Sentinel
    Trinity -. "Git ops" .-> Keymaker
    
    Architect -. "Recommendations" .-> Trinity
    
    Sion -. "Git ops" .-> Keymaker

    %% State dependencies
    DEM -. "Reads/Writes" .-> State[(File State<br>.context.yaml<br>checkpoints/)]
    Wachowski -. "Modifies" .-> MatrixState[(Matrix Core State)]
    
    classDef master fill:#f9f,stroke:#333,stroke-width:2px;
    classDef specialist fill:#bbf,stroke:#333,stroke-width:1px;
    classDef autonomous fill:#bfb,stroke:#333,stroke-width:2px;
    classDef state fill:#ddd,stroke:#333,stroke-width:1px,stroke-dasharray: 5 5;
    
    class DEM master;
    class Smith,Morpheus,Oracle,Trinity,Architect,Sentinel,Sion,Keymaker specialist;
    class Wachowski autonomous;
    class State,MatrixState state;
```

## Dependency Rules

1. **Master Isolation**: Users only interact with `Deus Ex Machina`. No direct user-to-specialist interaction.
2. **Keymaker Bottleneck**: Git operations are centralized in `Keymaker` (except for `Wachowski`, which has integrated git capabilities).
3. **Workspace Override**: When in the `~/www/emisrepos/matrix` directory, routing overrides to `Wachowski`.
4. **Coordination via Master**: Specialists technically coordinate by returning control or instructions that the Master then routes, rather than direct peer-to-peer invocation.
