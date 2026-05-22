# Routing Rules

## Wachowski Special Routing

**Priority Rule**: Wachowski takes precedence for Matrix-related requests.

### Detection Conditions

Route to Wachowski when ANY of these conditions are met:

1. **Workspace Detection**: Request originates from Matrix workspace (`/home/emiliano/www/emisrepos/matrix`)
   - Check current working directory
   - If in Matrix workspace, delegate to Wachowski

2. **Keyword Detection**: Request contains Matrix-related keywords
   - "matrix", "actualizar matrix", "update matrix", "mejorar matrix", "matrix workspace", "sistema matrix"

3. **Update Request**: User explicitly asks to update Matrix
   - "actualizar matrix", "update matrix", "mejorar matrix"

### Wachowski Routing Process

- Route to Wachowski silently (no announcement)
- Use run_subagent with agent name "wachowski"
- Pass original request with DETAILED context and system state
- Wachowski executes Matrix tasks directly using all specialist capabilities (no coordination with other specialists)
- Wachowski applies state-of-the-art practices for Matrix system work
- Wachowski delegates to Neo ONLY for final confirmations
- Wachowski delegates to Cypher ONLY for problems and errors
- Wait for Wachowski completion
- Synthesize results from Wachowski's execution

## 1 Specialist

- Route to specialist silently (no announcement)
- Use run_subagent with agent name
- Pass original request and context
- Wait for specialist completion
- Synthesize results

## More Than 1 Specialist

- Detect multi-specialist request
- Identify coordination pattern from coordination-patterns.md
- Execute specialists sequentially in defined order (silently, no upfront announcement)
- Pass context between specialists
- Synthesize unified summary combining all contributions
- Handle conflicts by presenting both perspectives
- Never use skill invoke for specialists
- Always use run_subagent with local agents in .devin/agents/
