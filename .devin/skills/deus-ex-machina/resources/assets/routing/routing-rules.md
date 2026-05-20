# Routing Rules

## 1 Specialist

- Announce routing to user
- Use run_subagent with agent name
- Pass original request and context
- Wait for specialist completion
- Synthesize results

## More Than 1 Specialist

- Detect multi-specialist request
- Identify coordination pattern from coordination-patterns.md
- Announce full sequence upfront
- Execute specialists sequentially in defined order
- Pass context between specialists
- Synthesize unified summary combining all contributions
- Handle conflicts by presenting both perspectives
- Never use skill invoke for specialists
- Always use run_subagent with local agents in .devin/agents/
