# lessons.md — the Zion Archive

Battle-tested lessons from real mistakes. These bind like the sacred foundation, but unlike it they are **amendable**: append a new lesson when reality teaches one. Read this at session start.

Routing: a lesson that binds across all projects lives here (the core pool). A lesson specific to one project lives in `brain/data/lessons/<project>.md` and loads only when the session binds to that project.

Una lección que afirma qué puede o no puede hacer otra plataforma/CLI tiene que citar la línea o doc exacto verificado — nunca "según el análisis previo" ni una inferencia sin medir. Si nadie lo verificó todavía, escribila como pregunta abierta, no como hallazgo.

La numeración de las lecciones es un identificador estable, no un índice secuencial: un hueco documentado (ver 31/33 más abajo) no implica contenido perdido, y un número nunca se reutiliza ni se reordena.

---

## Core lessons

1. (regla ya cubierta por Foundation 3 en `AGENTS.md` §4 y por el gate `hooks/validate_phase_close.py` — ver ahí. Número no reutilizable.)

2. (regla ya cubierta por Foundation 4 en `AGENTS.md` §4 — ver ahí. Número no reutilizable.)

3. (regla ya cubierta por The Construct en `AGENTS.md` §9 — ver ahí. Número no reutilizable.)

4. **El brain nunca nombra un CLI.** — enforced by `hooks/validate_layer2.py`.

5. **State goes through the CLI.** Nothing under `brain/state/**` is hand-edited; state mutates via `bin/matrix`. Hand edits desync the ledger and the dashboard. An explicit, ledger-logged exception is admitted for emergencies.

6. **Roster discipline.** Five core specialists. Adding one requires retiring or merging another. Proliferation (the old 9–12 roster) created overlap and maintenance cost with no gain.

7. (regla ya cubierta por The Construct en `AGENTS.md` §9 — ver ahí. Número no reutilizable.)

8. **Never log secrets.** Not in checkpoints, agent output, commits, or the ledger. Scrub emails and tokens from anything that leaves the machine.

9. (regla ya cubierta por `brain/agents/neo.md` (regla de scope growth) — ver ahí. Número no reutilizable.)

10. **Generated docs over hand-maintained docs.** The Source (`docs/SYSTEM_TRUTH.md`) is generated from the live brain and validated for drift. The old 22 hand-written docs drifted from reality; one generated doc cannot.

11. **No asumas gates de aprobación sin medirlos.** Detalle: `brain/output/research/adapter-lessons-detail.md`.

12. (regla ya cubierta por `brain/agents/neo.md:101` (promover lessons proactivamente) — ver ahí. Número no reutilizable.)

13. **Tool-allowlist declarativa no restringe; denylist de lectura del CLI sí, pero no bloquea `grep`/`exec`.** Detalle: `brain/output/research/adapter-lessons-detail.md`.

14. **Medí la capacidad antes de diseñar alrededor de su ausencia.** Detalle: `brain/output/research/adapter-lessons-detail.md`.

15. **Una afirmación documental que no tiene código que la genere o gate que la valide se vuelve falsa con un refactor.** Generala desde el estado vivo o agregá una validación de drift.

16. **Con `set -euo pipefail`, capturar un comando que puede fallar requiere `|| rc=$?`.** Sin esa captura, el shell sale antes del camino de error; para gates de fase, eso convierte un BLOCK en evidencia no persistida.

17. **Re-verificá claims de subagentes/fixtures vos mismo antes de confiar.** Detalle: `brain/output/research/lesson-17-self-report-not-evidence.md`.

18. **Una regla escrita en abstracto no se queda abstracta si el ejemplo que la ilustra es de una sola plataforma — y corregí la lección cuando la evidencia nueva la contradice, no la dejes como quedó escrita.** Regla operable: cuando una doctrina de coordinación depende de una capacidad de plataforma no verificada, marcarla "requiere verificación por adapter" al escribirla — y cuando la doctrina cambia, enmendar la lección citando el cambio real (archivo + fecha), nunca dejarla afirmando el estado viejo (lección 20). Aplicado en `brain/agents/smith.md` y `brain/agents/neo.md`; diseño completo en `brain/output/architecture/matrix-smith-evaluator-with-remediation-adr.md`.

19. **Gatear una defensa fail-loud con permisos restringidos da un falso PASS.** Detalle: `brain/output/research/adapter-lessons-detail.md`.

20. (contenido movido al preámbulo del archivo — ver encabezado. Número no reutilizable.)

21. **Un claim de arquitectura es una afirmación falsificable, auditala como tal.** Auditoría real (Architect, 2026-07-27) encontró 29 puntos de acoplamiento fuera del adapter, 3 con falso-verde. Mecanizado parcialmente por `hooks/validate_layer2.py` — ver lección 23.

22. **El checkpoint es un puntero al artefacto, nunca un sustituto.** Regla general ya en `brain/agents/neo.md` ('Persist artifacts from read-only specialists'). Caso: la auditoría de la lección 21 se perdió por no persistirse a tiempo.

23. **Si una violación se repite tras documentarla en prosa dos veces, el siguiente paso es un chequeo mecánico.** Detalle: `brain/output/research/adapter-lessons-detail.md`.

24. (texto casi idéntico a la lección 19 — ver ahí, mismo hallazgo. Número no reutilizable.)

25. (consolidada en la lección 17 — ver ahí. Número no reutilizable.)

26. (consolidada en la lección 17 — ver ahí. Número no reutilizable.)

27. (consolidada en la lección 17 — ver ahí. Número no reutilizable.)

28. **Re-corré una prueba de seguridad en el contexto real de uso antes de apoyar un diseño en ella.** Detalle: `brain/output/research/adapter-lessons-detail.md`.

29. **Un dashboard debe separar 'eventos abiertos' de 'proyectos conectados'.** Detalle: `brain/output/research/lesson-29-open-vs-connected-events.md`.

30. **Un nuevo camino de escritura en log/cola debe pasar por el mismo filtro de secretos que el camino existente.** Detalle: `brain/output/research/lesson-30-new-write-path-security-filter.md`.

31. (número retirado — sin registro de por qué en este archivo; confirmado por `git log -p` sobre los 6 commits que tocaron `lessons.md` que esta línea nunca existió, no hay contenido perdido. Ver Fase 0 del plan de remediación en `brain/output/plans/matrix-lessons-remediation-plan.md`.)

32. **Correr una precondición de diseño antes del gate; no basta documentarla como pendiente.** Detalle: `brain/output/architecture/hardline-session-end-notify.md`.

33. (número retirado — mismo caso que la línea 31, confirmado por el mismo forense de Fase 0.)

34. **Un evento de hook que puede forzar un loop del agente necesita re-verificación independiente del gate.** Detalle: `brain/output/research/adapter-lessons-detail.md`.

35. **Antes de construir un mecanismo nuevo de coordinación, buscá si `adapters/<target>/` ya tiene un lever para eso.** Detalle: `brain/output/research/adapter-lessons-detail.md`.

36. (consolidada en la lección 17 — ver ahí. Número no reutilizable.)

37. **Cuando agregás una entrada a `gitignore_entries`, auditá los proyectos ya bindeados.** Detalle: `brain/output/research/adapter-lessons-detail.md`.

38. **Al reparar SQLite con `.dump`, inspeccioná la última línea: puede cerrar en `ROLLBACK`.** Detalle: `brain/output/research/devin-sessions-db-corruption-incidents.md`.

39. **Re-verificar la cita de un subagente no es solo confirmar que el archivo/línea existe — hay que leer también si el código citado está marcado deprecado, y "existe en código" no es lo mismo que "es una feature de cliente soportada/documentada".** Caso completo (citas, módulos, IDs, verificación contra help-api): `brain/output/research/lesson-39-citation-verification-case.md`. Regla operable: (a) grepear/leer anotaciones de deprecación en el mismo archivo antes de aceptar una cita como evidencia del camino vigente; (b) cuando la respuesta viene de código de plataforma, verificar también la doc de cliente final para confirmar que el usuario final puede asumirla disponible.

40. **La proporcionalidad del ruteo no exime checkpoint/Link ni verificación E2E.** Detalle: `brain/output/research/lesson-40-proportionality-not-exempt.md`.

41. **Persistí el cierre formal/eval de una fase antes de encadenar la siguiente.** Detalle: `brain/output/research/lesson-41-persist-phase-close.md`.

42. **Session close y routing de trabajo mutante tienen gates mecánicos warn-only.** — enforced by `hooks/detect_orphan_session.py` y `hooks/validate_routing_signal.py`.

43. **Re-medí una cifra de un audit viejo antes de heredarla.** Detalle: `brain/output/architecture/matrix-system-health-audit.md`.

44. **"Compila/pasa local" no es evidencia de que un pipeline de CI/CD desatendido funcione — solo una corrida real disparada en ese entorno lo prueba.** Caso completo (`artista-ia`, `gh workflow run`, `package-lock.json`, versión de Node): `brain/output/eval/lesson-44-cicd-unattended-case.md`. Regla operable: cuando el criterio de "listo" exige ejecución desatendida en un entorno gestionado, dispará un `workflow_dispatch` real con las credenciales reales y mirá el run real antes de aceptar el criterio como PASS.

45. **Supabase Auth + Resend: tres gotchas operables encontrados debuggeando un flujo de invite/reset roto, reusables en cualquier proyecto con esta misma pila:** (a) el sender por default de Supabase (sin custom SMTP) tiene un límite duro de 2 mails/hora **compartido por todo el proyecto**; (b) el sender sandbox de Resend (`onboarding@resend.dev`) solo puede mandar mail **a la cuenta dueña de la API key**, nunca a un tercero; (c) el botón "Invite user" del dashboard de Supabase no expone `redirectTo` — para aterrizar en una ruta puntual post-invite se debe usar la Admin API. Ninguno es específico del proyecto; son comportamientos de la plataforma.

46. **Un gate de aceptación debe chequear el sentinel de workspace antes de rechazar por falta de bind.** Detalle: `brain/output/architecture/hardline-matrix-workspace-dispatch.md`.

47. (número retirado; su retiro no quedó documentado al momento del audit 2026-09-04. Número no reutilizable.)

48. **El `responseSchema` de un LLM no puede forzar reglas condicionales; validalas en código.** Detalle: `brain/output/eval/lesson-48-responseschema-conditional.md`.

49. **Nunca leas un `.env*` completo; preferí `grep` por clave o chequeos de longitud.** Detalle: `brain/output/research/lesson-49-no-full-env-read.md`.

51. **Retirar un especialista del roster no limpia por sí solo lo instalado — el instalador del adapter vigente copia/actualiza pero no poda huérfanos, y conviene buscar también instalaciones legacy fuera del path activo.** Reglas operables: (a) después de retirar un especialista, borrar a mano su carpeta instalada; (b) candidato a mecanizar: que el instalador compare instalado vs. generado y poda carpetas de specialists ya no en el roster; (c) ante limpieza, buscar también árboles legacy en otras convenciones de wiring. Detalle completo (Keymaker, `.agents/` viejo, paths exactos): `brain/output/research/adapter-lessons-detail.md` §51.

52. **Verificá `schedule:` y branch protection de GitHub contra el tier real de la cuenta.** Detalle: `brain/output/research/lesson-52-github-actions-platform-facts.md`.

53. **No asumas forma uniforme ni lista exhaustiva de call-sites sin `grep`.** Detalle: `brain/output/architecture/install-integrity-guard-and-hardline-secrets.md`.

54. **Un comando `exec` de un solo tiro corre no-interactivo y no fuente `~/.bashrc`/`~/.bash_aliases`, así que una función/env var del usuario puede parecer inexistente sin que el dotfile esté mal.** Reglas operables: (a) antes de concluir que una herramienta/función/variable "no existe" en un shell no-interactivo, re-intentar con `bash -ic '<comando>'` (o el equivalente interactivo del usuario); (b) cuando existe una herramienta sancionada por el equipo para una tarea, usarla y reportar el bug real en vez de reimplementar a mano. Caso completo (`sandisk`, `PATHTOREPOS`, `basePortalCloner`, bug modo `-d`): `brain/output/research/lesson-54-noninteractive-shell-and-clone-tool-gaps.md`.

55. **La ausencia de un tool MCP adapter-native en un subagente pese a estar declarado en sus permisos no fue un caso aislado: se repitió con dos bindings de browser distintos.** Correr en foreground no garantiza que un MCP declarado esté disponible para un subagente; cuando se necesite certeza, pedir al subagente que lo declare explícitamente al principio y, si falta, verificar desde la sesión raíz. Nombres exactos de tools/permisos/evidencia: `brain/output/research/adapter-lessons-detail.md` §55.

50. **`post_run_audit` debe atrapar gaps de eval-artifact en remediaciones de Smith.** — enforced by `hooks/post_run_audit.py`.

56. **Un `file_containment_violated` de `post_run_audit` sobre la remediación de Smith puede ser falso positivo del gap de atribución conocido (subagentes internos no llevan tag de perfil por evento de edición) — no lo aceptes ni lo rechaces sin cruzarlo contra el log de auditoría.** Regla operable: ante un `file_containment_violated` en una sesión con múltiples despachos intercalados de Trinity/Smith, cruzá rutas+timestamp de los eventos de edición contra los timestamps de cada despacho de subagente antes de tratar el hallazgo como violación real o ruido. Detalle completo (paths, timestamps, tool nativo): `brain/output/research/adapter-lessons-detail.md` §56.

57. **Auditá el drift de estado de git (`tracked_leak`) en proyectos bindeados.** Detalle: `brain/output/research/lesson-57-git-state-drift.md`.

58. **Para settings de instancias dev obdbqa, ir a `/_managerLogin` con cuenta avasso.** Detalle: `brain/output/research/lesson-58-obdbqa-manager-login.md`.

59. **En UI Avature, `input.value` no prueba persistencia; hacé `location.reload()`.** Detalle: `brain/output/research/lesson-59-avature-spa-input-persistence.md`.

60. **`PostCompaction` dispara hooks pero no entrega `additionalContext` al modelo.** Detalle: `brain/output/research/adapter-lessons-detail.md`.

61. **No corras dos editores con write en paralelo sobre el mismo worktree.** Detalle: `brain/output/research/lesson-61-parallel-writer-collision.md`.

62. **Un perfil "read-only" con `exec` en allowed-tools puede mutar archivos vía shell — el grant de tools no reemplaza la disciplina, y un brief de "solo lectura" no es un control.** Caso: en `cronicas`, la Oracle (grant: read, grep, glob, exec, mcp__context7 — sin `edit`/`write`) editó `informe/13-bibliografia.md` pese a un brief explícito de solo lectura, escribiendo vía shell (exec). El contenido pasó por gate de Smith (BLOCK → fix → PASS), así que el daño fue de proceso, no de contenido — pero el patrón es generalizable: cualquier subagente con `exec` puede mutar el filesystem. Regla operable: (a) cuando un rol requiere read-only real, quitar `exec` del grant o auditar post-hoc; (b) el brief no es control — si el dato crítico es "que no escriba", el control tiene que ser mecánico. Candidato a chequeo mecánico: hook que detecte mutaciones de archivos de proyecto por subagentes read-only, o quitar `exec` de los grants de Oracle. Incidente: `incident:writer-collision` 2026-09-05.
