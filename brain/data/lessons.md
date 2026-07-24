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

11. **No asumas gates de aprobación sin medirlos.** Se sospechó que subagents en background auto-deniegan tools MCP no aprobadas (basado en `subagents.mdx`). 4 tests controlados (MCP read-only y con side-effects, foreground vs background) no reprodujeron el bloqueo en este entorno. La causa real de un bloqueo pasado (figma-audit) fue más probablemente el grant de capabilities del *perfil* del subagente, no el flag `is_background`. No construyas mitigación cara para un gap no reproducido — si vuelve a pasar, reabrilo con perfil/tool/versión concretos, no con la sospecha genérica.

12. **Promové lessons vos mismo, no esperes a que te lo pidan dos veces.** Un hallazgo real y verificado (root cause confirmado, gap cerrado/reproducido, supuesto corregido) que solo queda en un checkpoint se pierde: el ledger scrollea fuera de la ventana que la activación repasa, `lessons.md` se lee completo siempre. Si la escritura es de bajo riesgo (append trivial a un lesson file, sin tocar state files a mano, sin costo de recursos relevante, sin downside serio si está mal — las lessons son amendable, no sacred foundation), promovela a `lessons.md` o al lesson de proyecto apenas la tengas, sin pedir aprobación. El usuario no debería tener que decir "che, guardá eso" — para eso está esta disciplina.

13. **`allowed-tools` en SKILL.md no restringe; `permissions.deny` con `Read()` sí, pero solo para el tool `read`, no `grep`/`exec`.** Evaluación real (Smith, 11 sesiones): Devin aplica `deny: ["Read(<ruta>/**)"]` sobre `read_file` inclusive en `--permission-mode dangerous`, y se propaga a subagentes. Ese mismo `deny` no bloquea `grep`/`glob` ni `exec` (`cat`, etc.), así que es una mitigación parcial contra lectura incidental, no un sandbox. Documentar siempre ese hueco en la salida del comando que toca `permissions.deny`.
