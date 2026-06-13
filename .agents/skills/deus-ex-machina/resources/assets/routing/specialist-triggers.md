# Specialist Trigger Keywords

Specialists are invoked using the `run_subagent` command with the appropriate agent name. Each specialist below has their trigger keywords that Deus Ex Machina uses to determine routing.

## Smith

- **Domain**: Bug detection, debugging, troubleshooting
- **Trigger keywords**: "bug", "error", "problema técnico", "no funciona", "falla", "debug", "arreglar"

## Morpheus

- **Domain**: Planning, strategy, roadmap creation
- **Trigger keywords**: "plan", "estrategia", "roadmap", "cómo organizamos", "pasos a seguir", "organizar", "proceso"

## Oracle

- **Domain**: Research, information gathering, analysis
- **Trigger keywords**: "investiga", "busca", "encuentra información", "¿cómo funciona", "research", "analiza", "explora", "examina", "revisa código", "mirá archivos", "qué cambió", "compara", "diferencias"

## Trinity

- **Domain**: Code design, architecture, implementation
- **Trigger keywords**: "diseña", "arquitectura", "estructura", "cómo debería ser", "mejor manera de", "implementar"

## Architect

- **Domain**: Code review, quality assurance, best practices
- **Trigger keywords**: "revisa", "mejora", "optimiza", "qué opinas de", "calidad", "best practices"

## Sentinel

- **Domain**: Security, vulnerability detection, data protection
- **Trigger keywords**: "seguridad", "vulnerabilidad", "hack", "protección", "datos sensibles", "security"

## Sion

- **Domain**: Documentation, knowledge management, organization
- **Trigger keywords**: "documenta", "explica", "crea docs", "guía", "manual", "archivo markdown", "markdown", "formato"

## Wachowski

- **Domain**: Matrix system integral specialist - handles all Matrix workspace and system update tasks with integrated specialist capabilities (code, debugging, planning, research, security, documentation, architecture, quality assurance)
- **Trigger keywords**: "matrix", "actualizar matrix", "update matrix", "mejorar matrix", "matrix workspace", "sistema matrix"
- **Special trigger condition**: When request originates from Matrix workspace (~/www/emisrepos/matrix)
- **Invocation method**: Use run_subagent with agent name "wachowski" (standard agent invocation pattern)
- **Note**: Wachowski is an INTEGRAL SPECIALIST with all specialist capabilities built-in. Uses integrated execution pattern (analyze → plan → implement → verify → document) in single cohesive flow. No coordination with other specialists needed for Matrix tasks.
- **Efficiency**: Wachowski integrates all specialist capacities in one execution unless task is genuinely complex (>300 chars, 3+ verbs, explicit phases keyword, or >5 files affected). Avoids artificial splitting of simple tasks.
- **Edge case**: Wachowski is invoked via run_subagent when Deus Ex Machina routes to it, whether from Matrix workspace or non-Matrix projects needing Matrix system expertise.

### Wachowski Execution Pattern

Wachowski uses integrated capacity flow:
1. Analyze (Oracle capacity): Understand current state
2. Plan (Morpheus capacity): Design approach
3. Implement (Trinity capacity): Execute changes
4. Verify (Architect capacity): Validate correctness
5. Document (Sion capacity): Update docs if needed
6. Log: Single specialist_execution entry via run_subagent mechanism

All in ONE execution unless genuinely interdependent phases required.

## Keymaker

- **Domain**: Git operations specialist - handles all git-related tasks and version control operations
- **Trigger keywords**: "git", "commit", "branch", "merge", "pull request", "push", "rebase", "cherry-pick", "stash", "checkout", "git status", "git log", "git history", "version control", "repositorio", "commitear", "hacer commit", "crear rama", "fusionar", "pull request"
- **Routing constraint**: Keymaker is ONLY routed to when the user explicitly requests git operations. Keywords alone are insufficient - must have explicit user request.
- **Important constraint**: Neither Deus Ex Machina nor other specialists should use git directly. Always delegate to Keymaker when git operations are explicitly requested.
- **Note**: Keymaker handles all git operations safely and appropriately, following git best practices
- **Edge case**: If git keywords appear in request but user does NOT explicitly request git operations, do NOT route to Keymaker (treat as regular task)
