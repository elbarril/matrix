# Specialist-Specific Routing Rules

This document contains specialist-specific routing rules that are loaded on-demand when routing to Keymaker or Wachowski.

## Keymaker Special Routing

**Explicit Request Rule**: Keymaker only handles git operations when explicitly requested by the user.

### Detection Conditions

Route to Keymaker when ALL of these conditions are met:

1. **Explicit User Request**: User explicitly asks for a git-related operation
   - User uses git-related keywords from specialist-triggers.md
   - User specifically requests commits, branches, merges, pull requests, or other git operations
   - User asks to check git status, log, or history

2. **No Autonomous Execution**: Neither Deus Ex Machina nor other specialists should use git directly
   - Git operations are never performed autonomously
   - Git operations are only performed when user explicitly requests them
   - Specialists should delegate to Keymaker for git operations, never execute git commands directly

### Keymaker Routing Process

- Route to Keymaker only when user explicitly requests git operations
- Use run_subagent with agent name "keymaker"
- Pass the specific git operation requested and context
- Keymaker executes the git operation safely and appropriately
- Keymaker reports the outcome clearly
- Log Keymaker execution

### Git Operation Constraints

- **No autonomous git operations**: Git commands are never executed without explicit user request
- **Specialist coordination**: Other specialists should delegate git operations to Keymaker, not execute them directly
- **Deus Ex Machina constraint**: Deus Ex Machina should not execute git commands directly, always delegate to Keymaker
- **Destructive operations**: Force operations (force push, reset --hard) require explicit confirmation from user

## Wachowski Special Routing

**Priority Rule**: Wachowski takes precedence for Matrix-related requests. **Matrix workspace mode overrides all context-based routing.**

### Detection Conditions

Route to Wachowski when ANY of these conditions are met:

1. **Matrix Workspace Mode** (HIGHEST PRIORITY):
   - Current working directory is exactly `~/www/emisrepos/matrix`
   - Activated in activation step 2 BEFORE context loading
   - Ignores active_project from .context.yaml completely
   - Routes ALL requests to Wachowski regardless of keywords
   - This ensures Matrix system work is never confused with project work

2. **Workspace Detection**: Request originates from Matrix workspace (`~/www/emisrepos/matrix`)
   - Check current working directory
   - If in Matrix workspace, delegate to Wachowski

3. **Keyword Detection**: Request contains Matrix-related keywords
   - "matrix", "actualizar matrix", "update matrix", "mejorar matrix", "matrix workspace", "sistema matrix"

4. **Update Request**: User explicitly asks to update Matrix
   - "actualizar matrix", "update matrix", "mejorar matrix"

### Wachowski Routing Process

- Route to Wachowski silently (no announcement)
- Use run_subagent with agent name "wachowski" (standard agent invocation pattern)
- Pass original request with DETAILED context and system state
- Wachowski executes Matrix tasks directly using all specialist capabilities (no coordination with other specialists)
- Wachowski applies state-of-the-art practices for Matrix system work
- Wait for Wachowski completion
- Synthesize results from Wachowski's execution

## Wachowski Multi-Call Pattern

**Integrated Execution Rule**: Wachowski uses integrated capacity flow in single execution by default. Multi-call only for genuinely complex tasks with genuinely interdependent phases.

### Complexity Criteria (STRICT)

Route to Wachowski using multi-call pattern when ALL of these conditions are met:

1. **Request Length**: Request exceeds 300 characters
2. **Multiple Action Verbs**: Request contains 3+ action verbs (e.g., "planear", "implementar", "verificar", "documentar" in the same request)
3. **Explicit Subtask Keywords**: Request explicitly mentions "subtareas", "fases", "etapas", or "pasos" with clear phase separation
4. **System-Wide Modification**: Request mentions modification affecting >5 files OR system-wide architectural changes

**Critical**: ALL FOUR conditions must be met. Missing even one condition means use integrated execution instead.

### When NOT to Use Multi-Call

Do NOT use multi-call for:
- Simple file edits (1-3 files)
- Single-component updates
- Routine documentation updates
- Minor configuration changes
- Tasks that can be completed with integrated capacity flow in one execution
- Requests meeting only 1-3 complexity criteria (must meet ALL 4)
- Tasks with artificial complexity (can be integrated into single flow)

### Integrated Execution Decision Process

When evaluating Wachowski task:
1. Check if ALL 4 complexity criteria are met → If NO, use integrated execution
2. If ALL 4 criteria met, check if phases are genuinely interdependent → If NO, use integrated execution
3. If genuinely interdependent phases required, use multi-call pattern
4. Default to integrated execution when uncertain

### Wachowski Integrated Execution Pattern (DEFAULT)

Wachowski uses integrated capacity flow in single execution:
1. Analyze (Oracle capacity): Understand current state and requirements
2. Plan (Morpheus capacity): Design approach and identify files
3. Implement (Trinity capacity): Execute changes
4. Verify (Architect capacity): Validate correctness
5. Document (Sion capacity): Update docs if needed
6. Log: Single specialist_execution entry via run_subagent mechanism

### Multi-Call Routing Process

- Detect complexity using STRICT criteria above
- If genuinely complex, route to Wachowski with multi-call flag
- Wachowski outputs structured response indicating required sequential calls with explicit phase specification
- Execute Wachowski calls sequentially as specified
- Pass context between calls
- Synthesize unified summary combining all phases

### Phase Specification Pattern

Wachowski indicates phases using structured response:
```
PHASE 1: [plan|implement|verify] - [description]
PHASE 2: [plan|implement|verify] - [description]
...
```
