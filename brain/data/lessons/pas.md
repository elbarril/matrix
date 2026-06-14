# lessons/pas.md — scoped lessons for PAS (Portal-Templates-Group)

These load only when a session binds to a PAS project. Append-only.

---

## Lessons

1. **Always use Templates Features over custom implementations.** Before writing custom JS/CSS, check if a Templates Feature already solves it. Custom code that duplicates a TF is tech debt.

2. **Never edit anything under templatesTools/.** That directory is read-only for agents. Source scripts with `source <script>.sh && <function>`, never execute bash scripts directly.

3. **Code review is mandatory before merge.** Run `templates-review.sh` on every portal before declaring done. Apply filter-exceptions by default.

4. **Trans text counter must pass.** Run `transTextCounter` after any copy change to verify translation coverage.
