---
name: test
description: Verify the build is real. Smith runs the E2E happy path and the code-quality sweep.
phase: test
next: eval
---

# Workflow · test

The reality gate. Proves the build works end-to-end before it can be called done.

## Steps

1. **Smith (verify)** — define and run the happy-path E2E check. Reproduce any reported bug before diagnosing. Root cause over symptom.
2. **Smith (sweep)** — review the diff against `brain/data/code-quality-review-lens.md`.
3. **Trinity (fix)** — if Smith blocks, Trinity applies the minimal fix; back to step 1.

## Close

Run `validate_phase_close` with `{"phase":"test","e2e":true,"evidence":"<E2E command + passing output>","tests":"<n/n>"}`. BLOCK if no E2E was run.

## Handoff

Hand a PASS to `eval`.
