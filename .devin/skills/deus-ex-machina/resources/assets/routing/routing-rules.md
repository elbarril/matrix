# Routing Rules

**For specialist-specific rules (Keymaker, Wachowski), see: rules/specialist-specific-rules.md**

## Routing Decision Flow

Deus Ex Machina follows this decision flow when routing requests:

1. **Check for Wachowski priority**
   - Is request from Matrix workspace? → Route to Wachowski
   - Does request contain Matrix keywords? → Route to Wachowski
   - Did user explicitly request Matrix update? → Route to Wachowski
   - If none apply, continue to step 2

2. **Check for Matrix workspace mode**
   - Is current working directory ~/www/emisrepos/matrix? → Enter Matrix workspace mode
   - If in Matrix workspace mode: SKIP context loading, route all requests to Wachowski
   - If NOT in Matrix workspace mode: continue to step 3

3. **Load and prepare context** (only when NOT in Matrix workspace mode)
   - Detect context from working directory
   - Load context configuration if available
   - Apply skill_priority rules if configured
   - Check global-skills.yaml for pattern matches
   - Prepare request with context enhancement

4. **Check for Keymaker explicit request**
   - Did user explicitly request git operations? → Route to Keymaker
   - Git keywords alone are insufficient
   - If no explicit request, continue to step 5

5. **Determine specialist count**
   - Does request trigger single specialist domain? → Single specialist routing
   - Does request trigger multiple specialist domains? → Multi-specialist routing
   - Apply coordination pattern if applicable

6. **Execute routing**
   - Single specialist: Route directly with run_subagent
   - Multi-specialist: Apply coordination pattern from coordination-patterns.md
   - Wachowski (Matrix workspace): Use run_subagent with agent name "wachowski"
   - Wachowski (non-Matrix): Use run_subagent with agent name "wachowski"

**Note**: Wachowski and Keymaker have special routing rules in rules/specialist-specific-rules.md that override general flow.

## Matrix Workspace Mode

**Matrix Workspace Mode Rule**: When working in the Matrix system root, ignore project context and route all requests to Wachowski.

### Detection Conditions

Enter Matrix workspace mode when:
- Current working directory is exactly `~/www/emisrepos/matrix`
- This check happens in activation step 2 before context loading

### Matrix Workspace Mode Behavior

When in Matrix workspace mode:
- **SKIP context loading** from .context.yaml (ignore active_project)
- **SKIP context detection** against brain/config/projects/*.yaml
- **Route ALL requests** to Wachowski for Matrix system work
- **Bypass context preparation** and skill priority routing
- **Treat all requests** as Matrix system maintenance tasks

### Rationale

Matrix workspace mode ensures that when working on the Matrix system itself:
- No confusion between active project (e.g., sandisk) and Matrix system work
- All requests are handled by Wachowski with integrated specialist capabilities
- Project context does not interfere with Matrix system operations
- Clear separation between project work and Matrix system maintenance

### Edge Cases

- **Symlink detection**: Check uses actual path, not symlinks
- **Subdirectories**: Only Matrix root triggers mode, subdirectories do not
- **User override**: User can explicitly request non-Wachowski specialists if needed

## Context Preparation

**Context Preparation Rule**: Deus Ex Machina detects context and prepares requests for specialists.

### Context Detection Process

- Detect current context by matching working directory against brain/config/projects/*.yaml
- If context match found, load context configuration from brain/config/projects/{context}.yaml
- Extract context information: primary_skills, pas_tools, skill_priority, matrix_integration
- Load global-skills.yaml for usage patterns

### Request Preparation

Deus Ex Machina prepares the request for context by:

1. **Primary Skills Enhancement**: If context has primary_skills
   - Add relevant keywords for those skills to the request
   - Ensure request triggers appropriate skill routing

2. **Tools Matching**: If context has pas_tools.enabled=true and tools_index
   - Load tools index from context.pas_tools.tools_index
   - Match request triggers against context tools
   - Prepare tools information to pass to appropriate specialists
   - NEVER execute tools directly - only pass information

3. **Global Skills Integration**: If context matches global-skills.yaml patterns
   - Check if request matches any usage_pattern.pattern
   - If pattern matches and context is in pattern.contexts (or "all")
   - Include global skills from pattern.skills in routing options
   - Apply priority: local skills > global skills > Matrix specialists

### Context Preparation Constraints

- **Deus Ex Machina only**: Only Deus Ex Machina detects context and prepares requests
- **Information only**: Tools information is passed to specialists, never executed by Deus Ex Machina
- **Skill priority**: Skills have priority over direct script usage when available

## Context-Aware Skill Priority Routing

**Skill Priority Rule**: Respect context's skill_priority setting when routing between local skills and Matrix specialists.

### Priority Modes

When context is loaded and has skill_priority configured, apply the following routing logic:

1. **matrix_specialists_only** (default for all contexts):
   - Route ONLY to Matrix specialists
   - NO generic subagents allowed (subagent_explore, subagent_general, etc.)
   - Use specialist triggers from specialist-triggers.md
   - Allow user to override and request Matrix specialists explicitly

2. **local_first** (legacy mode - deprecated):
   - Check if local skills match the request
   - If local skill match found, use local skills
   - If no local skill match, fall back to Matrix specialists
   - Allow user to override and request Matrix specialists explicitly

3. **matrix_first**:
   - Route to Matrix specialists directly
   - Local skills only if user explicitly requests them
   - Use for contexts that prefer Matrix specialists for most tasks

4. **hybrid** (default for Chronicle):
   - Check context's primary_skills list
   - If request matches primary_skills, use local skills
   - Otherwise, route to Matrix specialists
   - Allow user to override in either direction

### Priority Routing Process

- Load context configuration during context detection
- Extract skill_priority setting from context.working_model.skill_priority
- Extract primary_skills list from context.working_model.primary_skills
- Apply routing logic based on skill_priority mode
- **CRITICAL**: If skill_priority is not set or is invalid, default to "matrix_specialists_only"
- **FORBIDDEN**: Never route to generic subagents (subagent_explore, subagent_general, etc.) when Matrix is active
- **VALIDATION**: Check that target agent exists in .devin/agents/ directory before routing
- Log routing decision with context and priority mode
- Allow user override for all modes

### Global Skills Integration

When routing, also check brain/config/global-skills.yaml for usage patterns:

1. Load global-skills.yaml during context detection
2. Check if request matches any usage_pattern.pattern
3. If pattern matches and context is in pattern.contexts (or "all"):
   - Include global skills from pattern.skills in routing options
   - Apply priority: Matrix specialists > global skills > local skills
4. If pattern.contexts is ["all"], apply to all contexts
5. If pattern.contexts lists specific contexts, apply only to those

### Global Skills Routing Process

- Check global-skills.yaml for matching patterns
- If pattern matches, include global skills in routing options
- Respect priority: Matrix specialists > global skills > local skills
- Log global skills usage when applicable
- Allow user to override global skills suggestion

**Note**: Wachowski Multi-Call Pattern details are in rules/specialist-specific-rules.md

## Single Specialist Routing

### Detection

Route to single specialist when:
- Request triggers keywords for exactly one specialist domain
- Request does not require coordination patterns
- Request is not ambiguous
- Wachowski is not the appropriate target (not Matrix workspace or Matrix keywords)

### Routing Process

- Route to specialist silently (no announcement)
- Use run_subagent with agent name from .devin/agents/
- **VALIDATION**: Verify agent exists in .devin/agents/ before routing
- **FORBIDDEN**: Never route to generic subagents (subagent_explore, subagent_general, etc.)
- Pass original request with full context (context.yaml, system state)
- Wait for specialist completion
- Synthesize results for user

### Edge Cases

- **Keyword overlap**: If keywords overlap between specialists, choose based on primary domain match
- **Weak trigger**: If trigger is weak but domain is clear, route anyway
- **Context override**: If context specifies skill_priority, respect that over keyword matching

## Multi-Specialist Routing

### Detection

Route to multiple specialists when:
- Request triggers keywords for multiple specialist domains
- Request requires coordination pattern from coordination-patterns.md
- Request explicitly mentions multiple domains
- Complex task requiring sequential specialist involvement

### Routing Process

- Detect multi-specialist request
- Identify coordination pattern from coordination-patterns.md
- Execute specialists sequentially in defined order (silently, no upfront announcement)
- Pass context and previous specialist outputs between specialists
- **VALIDATION**: Verify all agents exist in .devin/agents/ before routing
- **FORBIDDEN**: Never use generic subagents (subagent_explore, subagent_general, etc.)
- Synthesize unified summary combining all contributions
- Handle conflicts by presenting both perspectives with recommendations
- Never use skill invoke for specialists
- Always use run_subagent with local agents in .devin/agents/

### Coordination Pattern Selection

- Match request against pattern triggers in coordination-patterns.md
- If multiple patterns match, choose the most comprehensive pattern
- If no pattern matches exactly, compose custom sequence based on domains
- Always include conflict resolution in synthesis

### Edge Cases

- **Wachowski exception**: If Matrix workspace task, do NOT coordinate - route to Wachowski alone
- **Keymaker constraint**: Only include Keymaker if user explicitly requested git operations
- **Pattern failure**: If pattern execution fails, present partial results and alternatives
