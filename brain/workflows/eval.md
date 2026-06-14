---
name: eval
description: Judge the result against the original goal and capture lessons. Closes the loop.
phase: eval
next: null
---

# Workflow · eval

Steps back and judges the whole result against the goal, then records what was learned.

## Steps

1. **Oracle + Smith (judge)** — does the result actually meet the goal from `spec`? Compare against the plan's done-criteria, not against effort spent.
2. **Capture lessons** — anything reality taught goes into the Zion Archive: cross-project → `brain/data/lessons.md`; project-specific → `brain/data/lessons/<project>.md`.
3. **Checkpoint** — `bin/matrix checkpoint "<what concretely moved>"` (writes a Link entry too).

## Close

Run `validate_phase_close` with `{"phase":"eval","evidence":"<verdict vs done-criteria + checkpoint ref>"}`.

## Handoff

End of loop. Neo reports the outcome to the user in plain Spanish.
