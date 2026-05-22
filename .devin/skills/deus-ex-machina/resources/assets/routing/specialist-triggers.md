# Specialist Trigger Keywords

Specialists are invoked using **ONLY** the `run_subagent` command with the appropriate agent name. Each specialist below has their trigger keywords that Deus Ex Machina uses to determine routing.

## Smith

- **Domain**: Bug detection, debugging, troubleshooting
- **Trigger keywords**: "bug", "error", "problema técnico", "no funciona", "falla", "debug", "arreglar"

## Morpheus

- **Domain**: Planning, strategy, roadmap creation
- **Trigger keywords**: "plan", "estrategia", "roadmap", "cómo organizamos", "pasos a seguir", "organizar", "proceso"

## Oracle

- **Domain**: Research, information gathering, analysis
- **Trigger keywords**: "investiga", "busca", "encuentra información", "¿cómo funciona", "research"

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

## Neo

- **Domain**: Content creation, writing, communication (final confirmations and success)
- **Trigger keywords**: "escribe", "redacta", "comunica", "explica para otros", "contenido", "texto"

## Cypher

- **Domain**: Problem communication, error reporting, when things are going wrong
- **Trigger keywords**: "error", "fallo", "problema", "algo salió mal", "no funcionó", "falló", "issue", "bug report", "error message", "something went wrong", "problema grave", "crítico", "blocker"

## Seraph

- **Domain**: Request clarification, interpretation, and reformulation
- **Trigger keywords**: "clarifica", "entiende mejor", "reformula", "no entiendo", "confuso", "ambiguo", "estructura"

## Wachowski

- **Domain**: Matrix system specialist - handles all Matrix workspace and system update tasks with full specialist capabilities
- **Trigger keywords**: "matrix", "actualizar matrix", "update matrix", "mejorar matrix", "matrix workspace", "sistema matrix"
- **Special trigger condition**: When request originates from Matrix workspace (/home/emiliano/www/emisrepos/matrix)
- **Note**: Wachowski is a self-sufficient specialist with all specialist capabilities (code, debugging, planning, research, security, documentation, architecture, quality assurance) - no coordination with other specialists needed
