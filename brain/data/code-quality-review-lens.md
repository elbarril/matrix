# code-quality-review-lens.md

The lens Smith sweeps every diff against before declaring PASS. Runs alongside the E2E reality gate, never instead of it. Prolijidad is a first-class deliverable.

## Sweep checklist

1. **Best practices.** Idiomatic for the language/framework. No deprecated patterns. Follows the project's existing conventions.
2. **Self-documenting.** Names say what they do. No comments needed to understand intent. (Do not add comments unless asked.)
3. **Clean & clear.** Smallest change that solves the problem. No dead code, no leftover debug output, no commented-out blocks.
4. **DRY.** No copy-paste duplication that should be a shared function. But do not over-abstract — earn the abstraction.
5. **Design fit.** Matches the Architect's design and the existing structure. No surprise new patterns smuggled in.
6. **Smells.** Long functions, deep nesting, god objects, primitive obsession, leaky boundaries, hidden side effects.
7. **Bugs.** Off-by-one, null/undefined handling, error paths, resource leaks, race conditions, unhandled rejections.
8. **Security.** No secrets in code or logs. Input validated. No injection surface. Least privilege.
9. **Imports & structure.** Imports at the top of the file. No mid-file imports. Files within reasonable size.
10. **Reality.** The E2E happy path was actually run, with evidence. (This gate is separate and mandatory.)

## Verdict format

```text
VERDICT: PASS | BLOCK
Reason: <one line>
Evidence: <command/output/url that proves it real>
Findings: <numbered list of issues, each with file:line and a minimal fix>
```
