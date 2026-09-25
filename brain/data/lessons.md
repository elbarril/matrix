# lessons.md — the Zion Archive

Battle-tested lessons from real mistakes. These bind like the sacred foundation, but unlike it they are **amendable**: append a new lesson when reality teaches one. Read this at session start.

Routing: a lesson that binds across all projects lives here (the core pool). A lesson specific to one project lives in `brain/data/lessons/<project>.md` and loads only when the session binds to that project.

Una lección que afirma qué puede o no puede hacer otra plataforma/CLI tiene que citar la línea o doc exacto verificado — nunca "según el análisis previo" ni una inferencia sin medir. Si nadie lo verificó todavía, escribila como pregunta abierta, no como hallazgo.

La numeración de las lecciones es un identificador estable, no un índice secuencial: un hueco documentado (ver 31/33 más abajo) no implica contenido perdido, y un número nunca se reutiliza ni se reordena.

---

## Core lessons

4. **El brain nunca nombra un CLI.** — enforced by `hooks/validate_layer2.py`.

5. **State goes through the CLI.** Nothing under `brain/state/**` is hand-edited; state mutates via `bin/matrix`. Hand edits desync the ledger and the dashboard. An explicit, ledger-logged exception is admitted for emergencies.

6. **Roster discipline.** Five core specialists. Adding one requires retiring or merging another. Proliferation (the old 9–12 roster) created overlap and maintenance cost with no gain.

8. **Never log secrets.** Not in checkpoints, agent output, commits, or the ledger. Scrub emails and tokens from anything that leaves the machine.

11. **No asumas gates de aprobación sin medirlos.** Detalle: `brain/output/research/adapter-lessons-detail.md`.

13. **Tool-allowlist declarativa no restringe; denylist de lectura del CLI sí, pero no bloquea `grep`/`exec`.** Detalle: `brain/output/research/adapter-lessons-detail.md`. (Semántica re-verificada 2026-09-07 en Devin CLI 3000.6.14: `Read(...)` SÍ bloquea `grep`/`glob`/`read` y `exec` `cat`/`ls` con path literal — el claim anterior era obsoleto; ver lección 65.) <!-- adapter-note: semantica del matcher Read() re-verificada contra Devin CLI 3000.6.14 el 2026-09-07 (hecho adapter-specific, ver leccion 65) -->

14. **Medí la capacidad antes de diseñar alrededor de su ausencia.** Detalle: `brain/output/research/adapter-lessons-detail.md`.

15. **Una afirmación documental que no tiene código que la genere o gate que la valide se vuelve falsa con un refactor.** Generala desde el estado vivo o agregá una validación de drift.

17. **Re-verificá claims de subagentes/fixtures vos mismo antes de confiar.** Detalle: `brain/output/research/lesson-17-self-report-not-evidence.md`.

18. **Una regla escrita en abstracto no se queda abstracta si el ejemplo que la ilustra es de una sola plataforma — y corregí la lección cuando la evidencia nueva la contradice, no la dejes como quedó escrita.** Regla operable: cuando una doctrina de coordinación depende de una capacidad de plataforma no verificada, marcarla "requiere verificación por adapter" al escribirla — y cuando la doctrina cambia, enmendar la lección citando el cambio real (archivo + fecha), nunca dejarla afirmando el estado viejo (lección 20). Aplicado en `brain/agents/smith.md` y `brain/agents/neo.md`; diseño completo en `brain/output/architecture/matrix-smith-evaluator-with-remediation-adr.md`.

19. **Gatear una defensa fail-loud con permisos restringidos da un falso PASS.** Detalle: `brain/output/research/adapter-lessons-detail.md`.

21. **Un claim de arquitectura es una afirmación falsificable, auditala como tal.** Auditoría real (Architect, 2026-07-27) encontró 29 puntos de acoplamiento fuera del adapter, 3 con falso-verde. Mecanizado parcialmente por `hooks/validate_layer2.py` — ver lección 23.

22. **El checkpoint es un puntero al artefacto, nunca un sustituto.** Regla general ya en `brain/agents/neo.md` ('Persist artifacts from read-only specialists'). Caso: la auditoría de la lección 21 se perdió por no persistirse a tiempo.

23. **Si una violación se repite tras documentarla en prosa dos veces, el siguiente paso es un chequeo mecánico.** Detalle: `brain/output/research/adapter-lessons-detail.md`.

28. **Re-corré una prueba de seguridad en el contexto real de uso antes de apoyar un diseño en ella.** Detalle: `brain/output/research/adapter-lessons-detail.md`.

29. **Un dashboard debe separar 'eventos abiertos' de 'proyectos conectados'.** Detalle: `brain/output/research/lesson-29-open-vs-connected-events.md`.

30. **Un nuevo camino de escritura en log/cola debe pasar por el mismo filtro de secretos que el camino existente.** Detalle: `brain/output/research/lesson-30-new-write-path-security-filter.md`.

32. **Correr una precondición de diseño antes del gate; no basta documentarla como pendiente.** Detalle: `brain/output/architecture/hardline-session-end-notify.md`.

34. **Un evento de hook que puede forzar un loop del agente necesita re-verificación independiente del gate.** Detalle: `brain/output/research/adapter-lessons-detail.md`.

35. **Antes de construir un mecanismo nuevo de coordinación, buscá si `adapters/<target>/` ya tiene un lever para eso.** Detalle: `brain/output/research/adapter-lessons-detail.md`.

37. **Cuando agregás una entrada a `gitignore_entries`, auditá los proyectos ya bindeados.** Detalle: `brain/output/research/adapter-lessons-detail.md`. — **MECANISMO RETIRADO 2026-09-11** (rework no-binding): ya no se escriben `_brain`/`AGENTS.local.md`/exclude dentro de los proyectos; la lección queda como registro histórico del incidente original.

38. **Al reparar SQLite con `.dump`, inspeccioná la última línea: puede cerrar en `ROLLBACK`.** Detalle: `brain/output/research/devin-sessions-db-corruption-incidents.md`. <!-- adapter-note: filename contains adapter name, pointer to existing research artifact -->

39. **Re-verificar la cita de un subagente no es solo confirmar que el archivo/línea existe — hay que leer también si el código citado está marcado deprecado, y "existe en código" no es lo mismo que "es una feature de cliente soportada/documentada".** Caso completo (citas, módulos, IDs, verificación contra help-api): `brain/output/research/lesson-39-citation-verification-case.md`. Regla operable: (a) grepear/leer anotaciones de deprecación en el mismo archivo antes de aceptar una cita como evidencia del camino vigente; (b) cuando la respuesta viene de código de plataforma, verificar también la doc de cliente final para confirmar que el usuario final puede asumirla disponible.

40. **La proporcionalidad del ruteo no exime checkpoint/Link ni verificación E2E.** Detalle: `brain/output/research/lesson-40-proportionality-not-exempt.md`.

41. **Persistí el cierre formal/eval de una fase antes de encadenar la siguiente.** Detalle: `brain/output/research/lesson-41-persist-phase-close.md`.

42. **Session close y routing de trabajo mutante tienen gates mecánicos warn-only.** — enforced by `hooks/detect_orphan_session.py` y `hooks/validate_routing_signal.py`. La ventana de análisis de una sesión cierra en su ÚLTIMO evento, no en el último `session_end`: una sesión reanudada dejaba el trabajo del día nuevo fuera de la ventana y producía un falso positivo de escalada (fix 2026-09-22, cubierto por 2 casos de regresión en `bin/lib/tests/routing-signal-delegation.py`). El ledger lleva `session_id=` (atribución exacta, no match por proyecto) y la escalada cuenta RACHA consecutiva, no acumulado: un contador de patrón que nunca decae degenera en warn siempre-on (113 unresolved acumulados → warn en cada close; fix 2026-09-22, cubierto por `bin/lib/tests/link-session-id.py` y los casos de racha).

43. **Re-medí una cifra de un audit viejo antes de heredarla.** Detalle: `brain/output/architecture/matrix-system-health-audit.md`.

44. **"Compila/pasa local" no es evidencia de que un pipeline de CI/CD desatendido funcione — solo una corrida real disparada en ese entorno lo prueba.** Caso completo (`artista-ia`, `gh workflow run`, `package-lock.json`, versión de Node): `brain/output/eval/lesson-44-cicd-unattended-case.md`. Regla operable: cuando el criterio de "listo" exige ejecución desatendida en un entorno gestionado, dispará un `workflow_dispatch` real con las credenciales reales y mirá el run real antes de aceptar el criterio como PASS.

45. **Supabase Auth + Resend: tres gotchas operables encontrados debuggeando un flujo de invite/reset roto, reusables en cualquier proyecto con esta misma pila:** (a) el sender por default de Supabase (sin custom SMTP) tiene un límite duro de 2 mails/hora **compartido por todo el proyecto**; (b) el sender sandbox de Resend (`onboarding@resend.dev`) solo puede mandar mail **a la cuenta dueña de la API key**, nunca a un tercero; (c) el botón "Invite user" del dashboard de Supabase no expone `redirectTo` — para aterrizar en una ruta puntual post-invite se debe usar la Admin API. Ninguno es específico del proyecto; son comportamientos de la plataforma.

46. **Un gate de aceptación debe chequear el sentinel de workspace antes de rechazar por falta de bind.** Detalle: `brain/output/architecture/hardline-matrix-workspace-dispatch.md`.

49. **Nunca leas un `.env*` completo; preferí `grep` por clave o chequeos de longitud.** Detalle: `brain/output/research/lesson-49-no-full-env-read.md`.

51. **Retirar un especialista del roster no limpia por sí solo lo instalado — el instalador del adapter vigente copia/actualiza pero no poda huérfanos, y conviene buscar también instalaciones legacy fuera del path activo.** Reglas operables: (a) después de retirar un especialista, borrar a mano su carpeta instalada; (b) candidato a mecanizar: que el instalador compare instalado vs. generado y poda carpetas de specialists ya no en el roster; (c) ante limpieza, buscar también árboles legacy en otras convenciones de wiring. Detalle completo (Keymaker, `.agents/` viejo, paths exactos): `brain/output/research/adapter-lessons-detail.md` §51.

53. **No asumas forma uniforme ni lista exhaustiva de call-sites sin `grep`.** Detalle: `brain/output/architecture/install-integrity-guard-and-hardline-secrets.md`.

55. **La ausencia de un tool MCP adapter-native en un subagente pese a estar declarado en sus permisos no fue un caso aislado: se repitió con dos bindings de browser distintos.** Correr en foreground no garantiza que un MCP declarado esté disponible para un subagente; cuando se necesite certeza, pedir al subagente que lo declare explícitamente al principio y, si falta, verificar desde la sesión raíz. Nombres exactos de tools/permisos/evidencia: `brain/output/research/adapter-lessons-detail.md` §55.

50. **`post_run_audit` debe atrapar gaps de eval-artifact en remediaciones de Smith.** — enforced by `hooks/post_run_audit.py`.

56. **Un `file_containment_violated` de `post_run_audit` sobre la remediación de Smith puede ser falso positivo del gap de atribución conocido (subagentes internos no llevan tag de perfil por evento de edición) — no lo aceptes ni lo rechaces sin cruzarlo contra el log de auditoría.** Regla operable: ante un `file_containment_violated` en una sesión con múltiples despachos intercalados de Trinity/Smith, cruzá rutas+timestamp de los eventos de edición contra los timestamps de cada despacho de subagente antes de tratar el hallazgo como violación real o ruido. Detalle completo (paths, timestamps, tool nativo): `brain/output/research/adapter-lessons-detail.md` §56.

58. **Para settings de instancias dev obdbqa, ir a `/_managerLogin` con cuenta avasso.** Detalle: `brain/output/research/lesson-58-obdbqa-manager-login.md`.

59. **En UI Avature, `input.value` no prueba persistencia; hacé `location.reload()`.** Detalle: `brain/output/research/lesson-59-avature-spa-input-persistence.md`.

60. **`PostCompaction` dispara hooks pero no entrega `additionalContext` al modelo.** Detalle: `brain/output/research/adapter-lessons-detail.md`.

61. **No corras dos editores con write en paralelo sobre el mismo worktree.** Detalle: `brain/output/research/lesson-61-parallel-writer-collision.md`.

62. **Un perfil "read-only" con `exec` en allowed-tools puede mutar archivos vía shell — el grant de tools no reemplaza la disciplina, y un brief de "solo lectura" no es un control.** Caso: en `cronicas`, la Oracle (grant: read, grep, glob, exec, mcp__context7 — sin `edit`/`write`) editó `informe/13-bibliografia.md` pese a un brief explícito de solo lectura, escribiendo vía shell (exec). El contenido pasó por gate de Smith (BLOCK → fix → PASS), así que el daño fue de proceso, no de contenido — pero el patrón es generalizable: cualquier subagente con `exec` puede mutar el filesystem. Regla operable: (a) cuando un rol requiere read-only real, quitar `exec` del grant o auditar post-hoc; (b) el brief no es control — si el dato crítico es "que no escriba", el control tiene que ser mecánico. Candidato a chequeo mecánico: hook que detecte mutaciones de archivos de proyecto por subagentes read-only, o quitar `exec` de los grants de Oracle. Incidente: `incident:writer-collision` 2026-09-05. <!-- adapter-note: contiene mcp__context7 (grant del perfil Oracle del adapter Devin); caso cronicas 2026-09-05 -->

64. **Cuando el caller conoce el `session_id`, pasalo explícito a `post_run_audit` — el marker global (`.current-hook-session`) es racy con sesiones concurrentes y atribuye el report al último `session_start`, no al cierre.** Detalle: `brain/output/eval/session-close-attribution-gate.md`.

65. **El matcher de deny `Read(...)` de Devin CLI es verb-aware y ruta-resoluble: bloquea tools read/grep/glob y exec que LEEN contenido con path literal (`cat`, `ls`), pero NO bloquea predicados (`test -f`), `source` ni indirección `$HOME` (3000.6.14, verificado 2026-09-07).** Reglas operables: (a) para chequear existencia de credenciales usá `test -f` (nunca `ls`/`cat`); (b) para cargar un token usá `source "$HOME/.avature/credentials/<host>.env"` (el matcher no resuelve $HOME); (c) nunca vuelques credenciales a la conversación ni a artefactos (lección 8/49); (d) si un comando lee una ruta denyada con path literal, el hook pre_tool_use_guard bloquea con guía de workaround. Incidente: incident-secret-deny-overblock-tl0090. **Decisión del usuario 2026-09-07: la deny list quedó DESHABILITADA** (`harden --revert` + `secret_deny.enabled: false` en config.yaml) — la semántica de este matcher queda documentada por si se re-habilita una versión angosta. <!-- adapter-note: semantica del matcher Read(...) verificada contra Devin CLI 3000.6.14 el 2026-09-07 (hecho adapter-specific del binding Devin) -->

66. **El tamaño en líneas es mal predictor de la ruta de ruteo: usá superficie (never-small), propagación (artefactos generados/archivos paralelos) y verificabilidad mecánica.** Evidencia: 42 casos 09-04→09-08 en `brain/output/research/routing-path-signals-2026-09.md`. Reglas operables: (a) la mayoría de los errores de ruteo ocurren al DECLARAR, no al ejecutar — la declaración del camino chico debe chequear propagación (S12), no solo el archivo nombrado; (b) doctrina vigente: escalera G0–G3 en `brain/agents/neo.md` `<routing>` + cláusula `sin-prop=si` en AGENTS.md §6.5; (c) desde 2026-09-08 el enforcement cambió: `session_close` exige `smith_gate` para trabajo G2 mutante y la delegación sin check verificado queda expuesta como `unverified_delegation` (warn `routing_signal_escalation`, no bloqueante) — enmendado por `brain/output/architecture/routing-remediation-cronicas-2026-09-08.md` (caso: 4 sesiones cronicas inline sin gate, audit `brain/output/research/routing-audit-cronicas-2026-09-08.md`).

67. **Un pendiente registrado en el ledger no es un pendiente comunicado.** `decision-tl2176` ("decisión del usuario sobre remediación de doctrina") quedó 5 horas sin resolución: se logueó el pendiente pero la pregunta nunca llegó al usuario — recién se resolvió cuando él pidió la auditoría. Regla operable: si un `pendiente=` requiere decisión del usuario, la pregunta tiene que llegar explícita (ask-user o mención en la respuesta), no archivarse en el ledger. Candidato a chequeo mecánico: surface de pendientes sin resolución al session start.

68. **Un presupuesto de tamaño medido en la unidad equivocada es un guard ciego: se vigila en la unidad del corte real.** Caso: `DEVIN.md` se leía con un tool que corta a 20.000 **caracteres**, mientras `hooks/surface_budget.py` medía **bytes** con un `fail` (24 KiB) *por encima* de ese corte — el archivo truncaba (se perdían las últimas 9 líneas) y el guard reportaba `ok`/`warn`. — enforced by `hooks/surface_budget.py` (unidad por superficie: bytes para lo que se inyecta, chars para lo que se lee). Reglas operables: (a) si un read vuelve truncado, **no es un read completo**: continuar con `offset` hasta EOF (`brain/data/activation-preamble.tmpl` item 4; el parámetro concreto lo nombra el adapter doc); (b) antes de comprimir un doc que un guard exige que nombre claves literales, correr `bin/matrix hooks the_source --check` — el recorte puede romper `config_flags_missing` sin que nada más lo note. Detalle: `brain/output/plans/harness-truncation-hardening-2026-09-18.md`, `brain/output/architecture/harness-truncation-hardening-review-2026-09-18.md`, `brain/output/eval/harness-truncation-hardening-2026-09-18.md`. <!-- adapter-note: el límite de 20.000 caracteres es del tool de lectura del adapter Devin; el caso se midió contra él el 2026-09-18 -->

69. **La identidad de sesión no puede depender de un marker compartido: con sesiones concurrentes, adivinar la sesión es peor que bloquear.** Caso: `bin/state/.current-hook-session` era un único archivo global; el último `session_start` en escribirlo ganaba, así que un `phase close` de una sesión corrió el chequeo de ruteo **contra otra sesión** y `post_run_audit` escribió su veredicto atribuido a la sesión ajena. — enforced by `hooks/_common.py#current_session_id` (resolución fail-closed: id explícito/payload/env → gana siempre; 0 bindings → marker legacy; exactamente 1 binding **y fresco** → ese id; cualquier otro caso → `None` → BLOCK "pasá session_id explícito"). Regla operable: (a) ante ambigüedad de identidad, BLOCK con mensaje accionable, nunca resolver al candidato más probable — un falso BLOCK se revierte pasando el id, una atribución errónea no; (b) "activo" se deriva de `last_seen_at` **al leer**, nunca de "el archivo existe", para que un residuo stale no deje el harness inutilizable; (c) el TTL/schema/path del binding tienen **un solo dueño** en Layer 1 y el adapter los importa (el path del marker estaba duplicado en dos archivos). Detalle: `brain/output/plans/harness-session-identity-2026-09-18.md` + `brain/output/architecture/harness-session-identity-review-2026-09-18.md`. <!-- adapter-note: el caso se midio sobre el binding Devin (marker `.current-hook-session` y session_id del payload del adapter Devin), 2026-09-18 -->

70. **Declarar que algo "no existe" exige una búsqueda explícita — el alcance por defecto de la herramienta oculta hechos y la conclusión falsa sale con confianza de fuente.** Dos casos verificados el mismo día, de dos agentes distintos: (a) un `read` plano sobre `brain/state/hook-audit.jsonl` (16 MB / 48.376 líneas) devuelve las entradas de **julio**, y de ahí salió "las sesiones de hoy no están en el log" (sí estaban: 374 y 272 líneas); (b) un `find`/`grep` que no descendió al directorio oculto `.devin/` produjo "ese archivo no existe" sobre un archivo de 21.552 B que sí existía — y esa afirmación falsa llegó a un artefacto de diseño. Regla operable: antes de afirmar una ausencia, (i) buscá también en paths ocultos (`.devin/`, dotdirs) y (ii) sobre archivos grandes usá `grep`/`python` en vez del tool de lectura con corte; si no podés cerrar la búsqueda, escribí "no lo encontré con este alcance", no "no existe". Misma familia que la 68 (el tool te oculta el hecho por unidad o por alcance). <!-- adapter-note: el caso (a) se midio con el limite de lectura del adapter Devin (20.000 chars); 2026-09-18 -->

71. **Un camino de lectura que traga excepciones convierte una falla transitoria en un resultado vacío indistinguible de "no hay nada".** Caso: `adapters/_adapter_meta.py::load_yaml` devolvía `{}` ante cualquier excepción (incluido un `import yaml` intermitente) y `adapter_binding` descartaba stderr → el smoke flakeaba ~1/5 como "no adapter binding" sin causa visible. Fix 2026-09-22: falla tipada (`_AdapterMetaUnreadable`), diagnóstico real a stderr (tipo de excepción + `sys.executable` + `sys.path`) y código de salida propio (2 = ilegible vs 1 = ausente) — enforced by `bin/lib/tests/adapter-meta-loud-failure.py`. Familia con el mismo patrón, pendiente: `adapters/_harden.py::_load_yaml`, `hooks/_common.py::_load_yaml`, `hooks/_flags.py`. Regla operable: distinguí "ausente" de "ilegible" con código propio y dejá el diagnóstico real en stderr; nunca un `{}` mudo.

72. **Con 2+ sesiones concurrentes, el signal de ruteo puede atribuir evidencia cross-sesión (falso `delegated`).** Con 2+ bindings frescos, `current_session_id()` falla-closed a None (lección 69) y `link_append` no anota `session_id=`; sin atribución, `hooks/validate_routing_signal.py::_activity_in_scope` cae al fallback por proyecto y un `handoff` de OTRA sesión del mismo proyecto cuenta como delegación propia (caso real 2026-09-23: `session_close` de `rainbow-hammer` resolvió `delegated` con un handoff de `gelatinous-dugout`). Regla operable: con concurrencia, cruzá `delegation_evidence` contra el sid real antes de aceptar el veredicto. Fix candidato: sid explícito en `link_append` + no caer a proyecto si la línea nombra otra sesión.

73. **El kernel de hooks tiene un ratchet de frontera de imports: ninguna arista nueva no declarada entra en `hooks/` ni cruza hacia `adapters/*/hooks/`.** — enforced by `hooks/import_boundaries.py`. El set sancionado es una lista nombrada y chica (`_common`, `_flags`, `_writer_lane`, `_tokenizer`); toda arista que no entre en él — un símbolo privado importado desde otro módulo local, un módulo con guión bajo fuera del set, o una arista que cruza la frontera `hooks/` ↔ `adapters/*/hooks/` hacia un destino no sancionado — falla la activación salvo que se declare como deuda intencional en `hooks/import_debt.json` con `intentional:true` y una nota. El hook **nunca auto-agrega**; una arista declarada que ya no existe en el grafo se reporta como `stale_debt` (info) y se borra en el mismo commit que la eliminó. Un `try/except` no exime: una arista es una arista, porque el try/except es el vector de evasión (el ciclo pre_activation_check↔install_integrity_check vivía en imports perezosos/try; S2 lo rompió moviendo ROSTER/SUPPORTING_AGENTS a `_common`). El ratchet es FAIL, no WARN, y se cablea como import duro en `pre_activation_check` (no en boot_warn): un guard que solo avisa es la misma trampa que un no-op. Regla y enforcement en el mismo commit (lección 15).

## Números retirados 2026-09-07

Registro: 10. (→ brain/output/research/retired-lessons-2026-09.md §10) 16. (→ brain/output/research/retired-lessons-2026-09.md §16) 48. (→ brain/output/eval/lesson-48-responseschema-conditional.md) 52. (→ brain/output/research/lesson-52-github-actions-platform-facts.md) 54. (→ brain/output/research/lesson-54-noninteractive-shell-and-clone-tool-gaps.md) 57. (→ brain/output/research/lesson-57-git-state-drift.md) 63. (→ lección 15 + brain/output/plans/link-bare-events.md)

Compactados: 1. (→ Foundation 3, AGENTS.md §4) 2. (→ Foundation 4, AGENTS.md §4) 3. (→ The Construct, AGENTS.md §9) 7. (→ The Construct, AGENTS.md §9) 9. (→ neo.md scope growth) 12. (→ neo.md promotion rule) 20. (→ preámbulo de lessons.md) 24. (→ lección 19) 25. (→ lección 17) 26. (→ lección 17) 27. (→ lección 17) 31. (retirado — forense Fase 0: matrix-lessons-remediation-plan.md) 33. (idem 31) 36. (→ lección 17) 47. (retirado — retiro no documentado al audit 2026-09-04)
