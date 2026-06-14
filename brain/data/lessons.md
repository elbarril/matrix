# lessons.md — the Zion Archive

Battle-tested lessons from real mistakes. These bind like the sacred foundation, but unlike it they are **amendable**: append a new lesson when reality teaches one. Read this at session start.

Routing: a lesson that binds across all projects lives here (the core pool). A lesson specific to one project lives in `brain/data/lessons/<project>.md` and loads only when the session binds to that project.

---

## Core lessons

1. **If it's not real, it doesn't matter.** No "done" without an end-to-end happy-path check. A passing unit test is not the same as the feature working. Smith + `validate_phase_close` gate the close. (Foundation 3.)

2. **Start simple, earn complexity.** The smallest thing that works ships first. Every added moving part must justify itself under a real constraint. The Architect's bias is fewer parts. (Foundation 4.)

3. **Load only what you need (The Construct).** Use `code-nav` for symbol-level reads/edits before opening whole files; delegate large artifacts (>~10 KB) to a sub-agent with a word cap; cheap model for mechanical work, reasoning model for hard problems. Context is the scarce resource.

4. **The brain never names a CLI.** Anything CLI-specific belongs in an adapter (the Trainman), never in `brain/`. If a lesson or workflow only works under one CLI, it's an adapter concern.

5. **State goes through the CLI.** Never hand-edit `.registry.json`, `brain/state/workspace.yaml`, `activity.log`, or `checkpoints.jsonl`. Use `bin/matrix`. Hand edits desync the ledger and the dashboard.

6. **Roster discipline.** Five core specialists. Adding one requires retiring or merging another. Proliferation (the old 9–12 roster) created overlap and maintenance cost with no gain.

7. **Checkpoint before truncating context.** On a long task or a mode change (build → eval → fix), write a checkpoint and a Link entry first. Resume is cheap; lost context is not.

8. **Never log secrets.** Not in checkpoints, agent output, commits, or the ledger. Scrub emails and tokens from anything that leaves the machine.

9. **Surface scope growth before doing it.** If a request quietly grows, stop and name it. Silent scope creep is a foundation violation, not helpfulness.

10. **Generated docs over hand-maintained docs.** The Source (`docs/SYSTEM_TRUTH.md`) is generated from the live brain and validated for drift. The old 22 hand-written docs drifted from reality; one generated doc cannot.
