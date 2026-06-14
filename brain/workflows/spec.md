---
name: spec
description: Turn a goal into a reviewed, ordered spec. Composes Oracle → Morpheus → Architect.
phase: spec
next: develop
---

# Workflow · spec

Produces a reviewed plan before any code is written. Agnostic body — each adapter exposes this as its native command.

## Steps

1. **Oracle (research)** — gather what exists and what is true about the goal. Output: `_brain/output/research/<goal>.md` with sources and confidence labels.
2. **Morpheus (plan)** — turn the goal into an ordered, minimal scope: steps, owners, done-criteria. Output: `_brain/output/plans/<goal>.md`.
3. **Architect (review)** — review Morpheus's plan against existing systems; name trade-offs; define interfaces and boundaries Trinity will build to. Output: `_brain/output/architecture/<goal>.md`.

## Close

Run `validate_phase_close` with `{"phase":"spec","evidence":"<plan + architecture artifact paths>"}`. The spec closes on a concrete artifact, not a runtime check.

## Handoff

Hand the reviewed plan to `develop`.
