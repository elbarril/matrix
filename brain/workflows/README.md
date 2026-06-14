# Workflows — composable programs

Thin-pointer pattern: the body of each workflow lives here (agnostic markdown); each adapter (the Trainman) exposes it as the host CLI's native command.

The loop composes:

```text
spec  →  develop  →  test  →  eval
```

- **`spec`** — Oracle (research) → Morpheus (plan) → Architect (review). Produces a reviewed plan.
- **`develop`** — Trinity builds to the plan. Supports `--headless` under Commander Lock.
- **`test`** — Smith runs the E2E reality gate and the code-quality sweep.
- **`eval`** — judge against the goal, capture lessons (Zion Archive), checkpoint.

Each workflow closes by calling the `validate_phase_close` hook (Seraph). Nothing in a runtime phase closes without real, end-to-end evidence. (Foundation 3.)

`--headless` drains a plan without prompts, guarded by Commander Lock (`brain/agents/` cockpit guardrail — see Phase 3 modules).
