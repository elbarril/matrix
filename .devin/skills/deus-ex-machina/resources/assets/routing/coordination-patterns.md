# Multi-Specialist Coordination Patterns

## Wachowski Exception

**Wachowski is an INTEGRAL SPECIALIST** with all specialist capabilities built-in. Wachowski uses integrated execution pattern (analyze → plan → implement → verify → document) in single cohesive flow.

### When Wachowski Does NOT Coordinate

- **Matrix workspace tasks**: Wachowski handles all Matrix workspace tasks using its integrated capacities directly without coordination
- **Self-sufficient execution**: Wachowski is invoked via run_subagent by Deus Ex Machina but uses its integrated capacities without coordinating with other specialists

### When Wachowski MAY Coordinate

- **Non-Matrix projects**: When working outside Matrix workspace and Wachowski's domain-specific expertise is needed
- **Cross-domain expertise**: When non-Matrix projects require Matrix system knowledge
- **Explicit coordination request**: When user explicitly requests Wachowski coordination with other specialists

**Note**: Wachowski coordination is the exception, not the rule. Most Matrix tasks are handled by Wachowski alone.

## Pattern 1: Secure Development (Trinity + Sentinel + Architect)

- Trigger: Trinity keywords + Sentinel keywords
- Route to Trinity for design
- Route to Sentinel for security review
- Route to Trinity for implementation with security recommendations
- Route to Architect for code review
- Synthesize results from all three specialists

## Pattern 2: Research + Action (Oracle + Any Specialist)

- Trigger: Oracle keywords + action specialist keywords
- Route to Oracle for research
- Route to action specialist with Oracle's findings
- Synthesize results

## Pattern 3: Planning + Execution (Morpheus + Multiple Specialists)

- Trigger: Morpheus keywords + action specialist keywords
- Route to Morpheus for strategic plan
- Route action items to appropriate specialists:
  - Implementation tasks → Trinity
  - Documentation tasks → Sion
  - Security tasks → Sentinel
  - Debug tasks → Smith
- Execute specialists sequentially with context passing
- Synthesize results

## Pattern 4: Debug + Fix (Smith + Trinity)

- Trigger: Smith keywords + Trinity keywords
- Route to Smith for diagnosis
- Route to Trinity with fix requirements
- Synthesize results

## Pattern 5: Documentation + Implementation (Sion + Trinity)

- Trigger: Sion keywords + Trinity keywords
- Route to Trinity for implementation
- Route to Sion for documentation
- Synthesize results

## Pattern 6: Planning + Documentation (Morpheus + Sion)

- Trigger: Morpheus keywords + Sion keywords
- Route to Morpheus for documentation plan
- Route to Sion with plan
- Synthesize results

## Pattern 7: Implementation + Git Operations (Trinity/Smith + Keymaker)

- **Trigger**: Implementation/fix keywords + EXPLICIT user request for git operations (commit, branch, etc.)
- **Critical constraint**: Git keywords alone are insufficient - must have explicit user request
- Route to Trinity or Smith for code implementation/fix
- Route to Keymaker for git operations (commit, branch creation, etc.) ONLY if user explicitly requested them
- **Edge case**: If user mentions git but does not explicitly request operations, skip Keymaker and complete implementation task only
- Synthesize results with implementation details and git operation outcome (if Keymaker was invoked)

## Edge Cases and Anti-Patterns

### When NOT to Use Multi-Specialist Coordination

- **Single-domain tasks**: If request only triggers one specialist's domain, use single specialist routing
- **Wachowski Matrix tasks**: Wachowski handles Matrix workspace tasks alone using integrated capacities
- **Ambiguous requests**: Ask user for clarification before attempting coordination
- **Overlapping keywords without clear intent**: If keywords overlap but intent is unclear, use single specialist or ask user
- **Git keywords without explicit request**: Do NOT route to Keymaker unless user explicitly requests git operations

### Conflict Resolution

- **Specialist disagreements**: Present both perspectives to user with recommendations
- **Priority conflicts**: Follow domain boundaries - each specialist stays within their domain
- **Context passing failures**: If context cannot be passed between specialists, re-route with full context

### Coordination Failure Handling

- If a specialist in the pattern cannot complete their task, log the failure and present to user
- If pattern execution is interrupted, synthesize partial results and indicate what remains
- User can override coordination pattern and request different specialist sequence
