---
name: develop
description: Implement a reviewed spec into real code. Trinity builds; supports --headless under Commander Lock.
phase: develop
next: test
---

# Workflow · develop

Implements the spec from `spec`. Builds real, working code.

## Steps

1. **Trinity (build)** — implement to the Architect's interfaces and boundaries. Use `code-nav` to locate edit sites; follow existing style; imports at top.
2. **Keymaker (opt-in)** — only if git work is explicitly requested (branch, commit). Never autonomous.

## Headless mode

`--headless` drains the plan without prompts. It runs under **Commander Lock**: the prompt format is validated, filesystem guardrails are absolute (no touching brain fundamentals, no `git reset --hard`, no commits without explicit instruction), and any malformed input aborts loud with `TASK_ABORTED`.

## Close

Run `validate_phase_close` with `{"phase":"develop","e2e":true,"evidence":"<command + output proving it runs>"}`. Nothing closes without a real run.

## Handoff

Hand the build to `test`.
