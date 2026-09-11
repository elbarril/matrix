# Matrix — Personal Intelligence Engine (built for Devin CLI)

Matrix is your personal intelligence layer: one root repo holds the brain, projects live outside and are pulled on demand, and Matrix resolves a project by its registered path — nothing is written inside the project. The brain is written to be **CLI-agnostic in design** — it speaks only in capabilities, never a specific CLI's tools — but **today it is built, installed, and maintained for Devin CLI only**. Adding another CLI later would cost one small adapter, not a brain rewrite.

> Themed after the Matrix trilogy. Every component is named after the character or place whose function it mirrors. See [`AGENTS.md`](AGENTS.md) for the canonical contract.

---

## Empezá acá si no sabés mucho de agentes IA

Esta sección explica todo el sistema en criollo, sin asumir que sabés cómo trabajan los agentes de IA. Si ya lo tenés claro, saltá a [El problema que resuelve Matrix](#el-problema-que-resuelve-matrix).

### ¿Qué es un "agente de IA" en este contexto?

Un agente es un asistente de IA (en este caso, Devin CLI) al que le das una tarea en lenguaje natural y que puede leer archivos, escribir código, correr comandos de terminal, y tomar decisiones sobre qué hacer paso a paso, sin que vos le digas cada click. No es un chatbot que solo contesta preguntas: puede efectivamente modificar tu proyecto.

El problema de un agente "pelado" (sin nada de esto) es que cada sesión nueva no sabe nada de las anteriores, no sabe cómo querés que trabaje, no sabe tus reglas, y hay que explicarle todo de cero cada vez. Matrix existe para que eso no pase.

### ¿Qué es Matrix, en una frase?

Matrix es un cerebro persistente y compartido que le da a Devin CLI memoria, reglas de comportamiento, y un equipo de "especialistas" con roles fijos — todo guardado en archivos de texto plano en este repositorio, para que cualquier sesión de Devin, en cualquiera de tus proyectos, tenga el mismo criterio y el mismo historial.

### ¿Cómo se activa esto en la práctica? (la skill global de Neo)

1. Este repo (`matrix/`) tiene el "cerebro": reglas, agentes, memoria.
2. Cada proyecto tuyo (otro repo, en otra carpeta) se **registra** (`bin/matrix add <nombre> <ruta>`) y se **activa** (`bin/matrix select <nombre>`). Matrix no escribe **nada** dentro del proyecto: sabe dónde vive por el registro (`.registry.json`) y lo encuentra caminando hacia arriba desde la carpeta donde estés parado.
3. Neo se activa en cualquier carpeta vía la **skill global** de Devin (instalada con `bin/matrix install`), que apunta al cerebro por ruta absoluta. Por eso la activación de Neo **no depende de que te acuerdes de invocarlo**: es automática, mecánica, no probabilística, y no necesita ningún archivo dentro del proyecto.
4. Una vez activo, siempre hablás con **Neo** (el agente maestro). Neo nunca te hace elegir un especialista de un menú: interpreta lo que pedís y, si hace falta, delega en el especialista correcto por su cuenta.
5. El proyecto en sí **nunca se ensucia** con la inteligencia: no se crea ningún archivo dentro. Si quedaron restos del sistema viejo (un symlink `_brain` o un `AGENTS.local.md` de cuando sí se escribían), el harness los ignora y `bin/matrix migrate-nobind` los limpia cuando quieras.

### ¿Quién hace qué? (el equipo, en criollo)

No hay un solo "modelo" haciendo todo. Matrix reparte el trabajo entre roles con un propósito claro, para que cada tarea la resuelva quien mejor la sabe hacer:

| Quién | Qué hace, en criollo |
|---|---|
| **Neo** | Es con quien vos hablás siempre. Entiende el pedido y decide si lo resuelve él mismo (algo chico) o si llama a un especialista (trabajo real). |
| **The Oracle** | El investigador. Lo llamás (indirectamente, vía Neo) cuando hace falta averiguar algo, comparar opciones, o confirmar hechos antes de actuar. |
| **Morpheus** | El planificador. Convierte un pedido ambiguo ("quiero que el sistema soporte X") en una lista ordenada de pasos concretos. |
| **The Architect** | El diseñador. Revisa el plan de Morpheus y decide cómo encaja técnicamente antes de que se escriba una sola línea de código. |
| **Trinity** | El que construye. Implementa el código real, el que efectivamente cambia archivos. |
| **Agent Smith** | El evaluador. Prueba lo que construyó Trinity, busca fallas reales (no en la teoría, corriendo comandos de verdad), y bloquea el cierre si algo no anda. Además arregla él mismo las fallas de bajo riesgo que encontró — prosa/docs, o un cambio acotado a un archivo — pero solo después de congelar el comando que falla y su salida cruda, y volviendo a correr ese mismo comando para probarlo. Lo estructural (estado del sistema, lógica de un gate, el contrato) sigue volviendo a Trinity. |

No hay un especialista aparte para git/operaciones: si el pedido es explícitamente sobre ramas, merges, o control de versiones, lo maneja **Neo** directamente, con las mismas reglas de siempre (nunca autónomo, confirma la rama antes, pide confirmación explícita para operaciones destructivas).

Un pedido de "arreglame un bug" pasa por Smith (encuentra la causa) y ahí se bifurca: si el arreglo es chico y ya existe un comando que lo prueba, Smith mismo lo arregla y lo re-verifica con ese mismo comando (si el cambio toca comportamiento aunque sea acotado, el Architect revisa el diff antes de cerrar); si el arreglo toca algo estructural, vuelve a la cadena Smith (diagnostica) → Trinity (arregla) → Smith (verifica). Un pedido de "quiero una funcionalidad nueva" típicamente pasa por Morpheus (plan) → Architect (revisión) → Trinity (construye) → Smith (gate final). **Vos nunca hablás con ellos directamente** — es Neo quien los invoca como sub-agentes y te cuenta el resultado.

### Dos gates que se llaman parecido pero preguntan cosas distintas

Es fácil confundirlos porque los dos son hooks de Seraph y los dos aparecen al "cerrar" algo, pero responden preguntas distintas:

- **`validate_phase_close`** — el gate de **realidad del contenido**: "¿esto que decís que funciona, funciona de verdad?". No escribe nada en disco por sí mismo; recibe `{"phase","e2e","evidence","lesson"}` y devuelve PASS/BLOCK por stdout. Es manual: solo corre si el agente decide invocarlo al cerrar una fase (`spec`/`develop`/`test`/`eval`). Nada de Devin lo dispara solo.
- **`post_run_audit`** — el gate de **proceso**: "¿el agente siguió los pasos obligatorios de activación?" (no si el trabajo es real, sino si se hizo el ritual: `pre_activation_check`, etc.). Este sí persiste: escribe `brain/state/validation-report.json`. Se alimenta de eventos reales del ciclo de vida de Devin (`SessionStart`, `PostToolUse`, `SessionEnd`) vía `adapters/devin/hooks/session_audit.py` → `hooks/audit_event.py`; además, `SessionEnd` dispara `bin/matrix session close`, que corre `hooks/session_close.py` y escribe `session:close` en el ledger Link. Desde el cambio de rol de Smith, este hook además audita la remediación: si la sesión auditada es de Smith y hubo ediciones, exige el bloque de pre-registro (comando que falla → mismo comando pasando) en su artefacto de eval, y marca la sesión como no conforme si falta, si el comando cambió entre el antes y el después, o si se editó un archivo que el artefacto no declaró.

En criollo: uno audita el **qué** (¿el trabajo es real?), el otro audita el **cómo** (¿se siguió el protocolo?). Podés pasar uno y fallar el otro.

### ¿Por qué tantas capas / nombres raros?

Porque así el sistema no queda atado a Devin CLI para siempre. Las reglas y los agentes (`brain/`) están escritos en un lenguaje neutral — nunca dicen "usá la herramienta X de tal CLI", dicen "necesito la capacidad de leer archivos". Un traductor delgado (**el adaptador de Devin**, en `adapters/devin/`) es lo único que sabe que hoy el CLI es Devin. Si el día de mañana usás otro CLI, se cambia ese traductor (chico) y el cerebro entero se reutiliza tal cual.

### ¿Qué es "el estado" y por qué no se sube a git?

Matrix necesita recordar cosas entre sesiones: qué proyecto es tu foco actual, qué proyectos tenés "calientes", un historial de checkpoints, un log de eventos. Todo eso son **archivos de texto** en `brain/state/` — nunca una base de datos. Cambian todo el tiempo y son específicos de tu máquina, así que están en `.gitignore`: no se commitean, no ensucian el historial del repo.

### ¿Qué es un "checkpoint"? ¿Y en qué se diferencia de una "lesson"?

Un **checkpoint** es una nota con fecha que Neo (o vos) guarda cuando algo importante pasó ("implementé X, quedó pendiente Y"). Es memoria de **corto plazo**: sirve para retomar un hilo cortado (una sesión que se compactó, un cambio de foco), no para acordarse de algo para siempre. Se escribe con `bin/matrix checkpoint "nota"`, nunca a mano.

Por default, `matrix status` y `matrix activity` muestran los checkpoints/eventos del **proyecto activo** (resuelto igual que Neo: caminando hacia arriba desde la carpeta donde estás parado y comparando contra los proyectos registrados — el más cercano gana, y si hay proyectos anidados se muestra la cadena — o el foco de sesión con `matrix focus`). Esto es a propósito: `checkpoints.jsonl` es un archivo único y compartido entre *todos* tus proyectos, así que una vista global mezclaría el historial de sandisk con el de calian y el que te importa quedaría enterrado apenas trabajes en otro proyecto. Usá `matrix status --all` o `matrix activity --all` cuando de verdad quieras la vista cruzada, o `matrix activity --project=<nombre>` para mirar otro proyecto sin moverte de carpeta.

Una **lesson** (`brain/data/lessons.md` o `brain/data/lessons/<proyecto>.md`) es memoria de **largo plazo**: cosas que la realidad enseñó y que valen para siempre (una decisión del cliente, un link de acceso a una instancia, un bug real y su causa). A diferencia del checkpoint, no se cae de ninguna ventana — se lee siempre, íntegro, cuando la sesión trabaja en ese proyecto (y, si hay proyectos anidados, la cadena completa, más cercano primero). La fase `eval` del ciclo de trabajo (ver `hooks/validate_phase_close.py`) es la que la exige, y el hook `validate_phase_close` **bloquea** cerrar la fase `eval` si no se declaró explícitamente qué se aprendió (o un "N/A" razonado) — antes era solo una convención que se podía saltear en silencio.

---

## El problema que resuelve Matrix

Sin Matrix, cada sesión de Devin CLI en cada proyecto arranca en cero: sin memoria, sin reglas de comportamiento consistentes, sin división de roles. Matrix centraliza esa inteligencia en un solo lugar y la conecta a cualquier proyecto sin copiar nada dentro de él.

## The three layers

```text
adapters/        LAYER 3 · "The Trainman"  — Devin binding today (thin, replaceable if another CLI is added)
brain/           LAYER 2 · "Zion"          — intelligence core in agnostic markdown
bin/ + hooks/    LAYER 1                    — orchestration, state, portable enforcement
```

The golden rule: **Layer 2 never names a CLI.** Agents speak in capabilities (`read`, `edit`, `search`, `code-nav`, `run-subagent`, `ask-user`, `run-command`); each adapter binds those to a host CLI's real tools.

## The roster

One master, five core specialists. Names map to function.

- **Neo** — *master*. The single voice. Routes, holds context, carries the sacred foundation, bridges every CLI.
- **The Oracle** — *researcher*. Gathers, compares, cites, foresees. "What is true / what exists."
- **Morpheus** — *planner*. Turns ambiguity into ordered scope. "What / when."
- **The Architect** — *architect*. Designs structure, names trade-offs, reviews plans before build. "How it fits."
- **Trinity** — *builder*. Implements and ships real, working code.
- **Agent Smith** — *evaluator, with scoped remediation*. Tests, critiques, finds the flaw, blocks weak work; fixes the inert/localized defects it reported itself, under pre-registered failing→passing evidence.

There is no dedicated git/ops specialist: Neo handles explicitly-requested branches, paths, access, and version control directly.

**Routing seam:** Morpheus answers *what/when*; the Architect answers *how it fits* and reviews the plan before Trinity builds; Smith gates the result before "done", and fixes the Tier-1/Tier-2 defects it reported itself (Tier 2 needs an Architect diff review before close). Trinity is still the only agent that builds to a brief.

## Supporting cast (infrastructure)

- **Seraph** — portable enforcement hooks (`pre_activation_check`, `validate_phase_close`, `post_run_audit`, bypass detection).
- **Link** — the append-only ledger (`brain/state/activity.log`) every agent and ship reads/writes.
- **The Construct** — cost & context optimization (semantic code-nav, model selection, artifact delegation, resume checkpoints).
- **The Trainman** — the CLI adapter layer + `bin/matrix build`.
- **Commander Lock** — the unattended/cockpit guardrail (validates the autonomous prompt, hard FS rules, fail-loud).
- **The Hardline** — opt-in multi-channel/AFK daemon (reacts to external events, zero tokens on idle).
- **The Source** — `docs/SYSTEM_TRUTH.md`, a generated-and-validated single source of truth.
- **The fleet** — federated subsystems are ships (`brain/subsystems/<ship>/`) with their own master and contract. Core vessel: **Nebuchadnezzar**; example research ship: **Logos** (captain Niobe).

## File structure

```text
matrix/
├── AGENTS.md                  # canonical contract (Layer 2)
├── README.md                  # this file
├── DEVIN.md                   # Devin adapter notes
├── .registry.json             # all known projects
├── bin/matrix                 # CLI orchestrator (Layer 1)
├── hooks/                     # Seraph — portable enforcement (python)
│   ├── pre_activation_check.py
│   ├── validate_phase_close.py
│   └── post_run_audit.py
├── adapters/                  # Trainman — Layer 3 (devin/ only, for now)
├── brain/                     # Layer 2 — the intelligence core
│   ├── config.yaml            # GITIGNORED: per-machine (user, language, timezone)
│   ├── agents/                # neo, oracle, morpheus, architect, trinity, smith
│   ├── data/                  # lessons.md, code-quality-review-lens.md, capability-map.md
│   ├── subsystems/            # the fleet (federated ships)
│   ├── state/                 # GITIGNORED: workspace.yaml, activity.log, checkpoints.jsonl, ...
│   └── output/                # GITIGNORED: per-project artifact subtrees + Matrix-workspace-mode scratch (see AGENTS.md §1)
├── docs/SYSTEM_TRUTH.md       # The Source (generated/validated)
└── clients/                   # GITIGNORED: pulled project repos
```

Work artifacts for a **registered project** are written to `brain/output/<project>/{architecture,plans,research,eval}/` **in this repo** — never inside the project's own repo. See `AGENTS.md` §1. `matrix select` creates that per-project subtree (if missing). Nothing project-specific is written inside the project's own repo, so its `.gitignore` needs no entry for Matrix.

## CLI commands

```text
list                      List registered projects
add <name> [path]         Register a project
select <name>             Activate a project: warm it + set the adapter target +
                           create the output dirs (+ clone if remote). Writes
                           NOTHING inside the project.
deselect <name>           Clean legacy artifacts (migrate-nobind) + unwork
work <name>               Warm a project into the active set (bookmark)
unwork <name>             Remove a project from the warm set
bindings [--warm-only]    List registered projects with warm status (and any
                           legacy artifacts still present)
migrate-nobind [<name>|--all] [--dry-run]  Remove legacy _brain/AGENTS.local.md/
                           exclude blocks left by the old binding system
flags [--json|--validate] Show the feature flags (state, source, risk);
                           --validate exits 1 if any flag is inert/dangerous
scope [--tree [--json]]   Show current mode/project, or the project memory chain
status [--all]            Show known/warm counts, registered count, recent
                           checkpoints and Link events — scoped to the resolved
                           project chain by default; --all for the cross-project view
checkpoint "<note>"       Write a checkpoint (+ Link entry)
activity [n] [--all] [--project=<name>]   Show last n Link events, scoped to the
                           resolved project chain by default (default n=20)
hooks <name> [json]       Run a Seraph hook
build --target=<cli>      Trainman: generate native CLI artifacts
install --target=<cli>    Trainman: deploy generated artifacts into the CLI's discovery path
help                      Usage
```

## Multi-project: varios proyectos "vivos" a la vez

Podés tener **muchos proyectos registrados** y **varios "calientes" (warm)** al mismo tiempo, sin que se molesten entre sí. Esto es útil si trabajás en paralelo (por ejemplo, dos terminales, dos proyectos distintos, cada uno con su sesión de Devin CLI).

Hay dos conceptos, y es importante no confundirlos:

- **`known` (registrado)** — el proyecto figura en `.registry.json` con su ruta. Es la lista de proyectos que Matrix conoce.
- **`warm` (caliente)** — un proyecto "de interés" guardado en `brain/state/workspace.yaml`. Es una lista de bookmarks: solo se puede calentar un proyecto registrado (`warm ⊆ known`).

Ya no existe el concepto de "bindeado" (`bound`): el sistema viejo escribía un symlink `_brain` y un `AGENTS.local.md` dentro de cada proyecto para marcarlo; ahora no se escribe nada, y un proyecto está **en scope** cuando su ruta registrada es el ancestro más cercano de la carpeta donde estás parado.

**¿Cómo resuelve Neo qué proyecto es "el suyo" en una sesión dada?** Con esta prioridad: variable de entorno `$MATRIX_PROJECT` > foco de sesión (`matrix focus <nombre>`) > caminar hacia arriba desde la carpeta actual y comparar contra los proyectos registrados (el más cercano gana). Si nada resuelve, la sesión **no tiene proyecto** (neutral). En la práctica: **si abrís una terminal dentro de un proyecto registrado, esa sesión ya sabe cuál es su proyecto sin importar qué otros proyectos estén activos en otro lado.**

**Proyectos anidados:** si un proyecto vive dentro de otro (por ejemplo, `outer/inner`), la sesión toma memoria de **ambos** como una cadena: el subject es el más cercano (`inner`) y las lecciones y vistas de proyecto cargan la cadena completa (inner primero, después sus ancestros). `matrix scope --tree` te muestra esa cadena. Si la raíz de Matrix gana el walk-up, se entra en **Matrix workspace mode** (trabajo sobre el sistema mismo, sin proyecto).

Ejemplo de uso real con dos proyectos a la vez:

```bash
./bin/matrix add sitio-web /home/vos/proyectos/sitio-web
./bin/matrix add api-backend /home/vos/proyectos/api-backend

./bin/matrix select sitio-web      # lo activa (warm + outputs); no escribe nada en el proyecto
./bin/matrix select api-backend    # activa api-backend SIN tocar a sitio-web

./bin/matrix bindings
#  ✓ sitio-web -> /home/vos/proyectos/sitio-web [warm]
#  ✓ api-backend -> /home/vos/proyectos/api-backend [warm]

./bin/matrix status
# Known: 2 project(s) / Warm: 2 project(s)

./bin/matrix deselect sitio-web    # limpia legados + lo saca del warm set; api-backend sigue intacto
```

Ahora podés abrir Devin CLI dentro de `sitio-web/` y dentro de `api-backend/` (en dos terminales distintas, o en momentos distintos) y ambas sesiones activan a Neo automáticamente, cada una con el contexto de su propio proyecto — sin que una sesión pise a la otra.

**Seguridad de estado concurrente:** `bin/matrix` toma un lock global (`flock`) al arrancar cualquier comando, así que si corrés dos comandos `bin/matrix` al mismo tiempo desde sesiones distintas no se corrompen los archivos de estado compartidos (`workspace.yaml`, `.registry.json`, el ledger). Si `flock` no está disponible en tu sistema (por ejemplo, macOS sin GNU coreutils), el comando avisa y sigue sin lock — no instala nada nuevo, pero perdés esa protección puntual.

## Quick start

```bash
# Register and activate a project (writes nothing into it)
./bin/matrix add myproject /path/to/project
./bin/matrix select myproject

# Activate a second project without touching the first one
./bin/matrix add otherproject /path/to/otherproject
./bin/matrix select otherproject
./bin/matrix bindings          # both show as [warm]

# Or just warm several projects as bookmarks
./bin/matrix work myproject
./bin/matrix work otherproject
./bin/matrix bindings --warm-only

# Feature flags and project resolution helpers
./bin/matrix flags
./bin/matrix scope --tree

# Generate native artifacts and deploy them into Devin's global discovery path
./bin/matrix build   --target=devin
./bin/matrix install --target=devin
# (then invoke Neo via `/neo` in Devin CLI, from any project; the user always talks to Neo first)
```

## Runbook (comandos comunes, copiables)

```bash
# Contexto y estado
./bin/matrix scope --tree            # modo/proyecto + cadena de memoria
./bin/matrix status                  # checkpoints y Link del proyecto en scope
./bin/matrix checkpoint "qué hice y qué falta"

# Ruteo: cada route/handoff va al ledger; distinguí el dispatch del resultado verificado
./bin/matrix link route   mi-proyecto "plan+execute: Morpheus -> Architect -> Trinity -> Smith (session_id=<sid>)"
./bin/matrix link handoff mi-proyecto "Trinity -> Smith despachado; verificar con su gate E2E (session_id=<sid>)"

# Cierre de fase: el gate real es phase close; precheck es opcional (dry-run)
./bin/matrix phase close   '{"phase":"develop","e2e":true,"evidence":"ran ./suite.sh; 12/12 passed","session_id":"<sid>"}'
./bin/matrix phase close   '{"phase":"eval","e2e":true,"evidence":"gate Smith PASS","lesson":"N/A - no new lesson","session_id":"<sid>"}'
./bin/matrix phase precheck '{"phase":"develop","e2e":true,"evidence":"ran ./suite.sh; 12/12 passed","session_id":"<sid>"}'  # opcional
# Schema copiable sin efectos:  ./bin/matrix phase close --help

# Cierre de sesión (audita el protocolo; no reemplaza phase close)
./bin/matrix session close '{"session_id":"<sid>"}'

# Desde la raíz o sin cwd en el proyecto: ruta absoluta + MATRIX_PROJECT registrado
MATRIX_PROJECT=mi-proyecto /home/vos/matrix/bin/matrix phase close '{"phase":"spec","evidence":"brain/output/plans/myplan.md"}'
```

## Uso diario típico

- **Un solo proyecto, uso normal:** registralo (`matrix add <proyecto> <ruta>`) y activalo (`matrix select <proyecto>`) una vez; después simplemente abrís Devin CLI dentro de esa carpeta cuando quieras trabajar — Neo se activa solo. No hace falta re-seleccionar nada en cada sesión.
- **Cambiar de foco sin perder el anterior:** `matrix select <otro-proyecto>` no toca al proyecto anterior — los dos quedan activos. Si querés desactivar explícitamente uno, usá `matrix deselect <nombre>`.
- **Ver qué está pasando:** `matrix status` (resumen general), `matrix bindings` (estado known/warm de cada proyecto), `matrix scope --tree` (qué proyecto sos y qué cadena de proyectos anidados tenés), `matrix list` (todos los proyectos conocidos).
- **Dejar una nota para la próxima sesión:** `matrix checkpoint "lo que hice y lo que falta"`. Neo también lo hace automáticamente en hitos importantes.
- **Limpiar restos del sistema viejo:** si algún proyecto tiene todavía un `_brain` o un `AGENTS.local.md` (de antes del rework), `matrix migrate-nobind --all --dry-run` te muestra qué limpiaría; sin `--dry-run` lo limpia.
- **Trabajar en el propio Matrix (no en un proyecto):** parate en la raíz de este repo y hablale a Neo directamente — entra en "Matrix workspace mode" (sin proyecto en scope, trabajando sobre el sistema mismo).

## Principles

1. **Root intelligence + pulled projects.** The root repo is the brain; project repos are pulled on demand.
2. **One master, capability specialists.** Neo is the face; specialists are capabilities, not topics. Roster discipline: add one → retire one.
3. **CLI-agnostic core.** The brain speaks capabilities; adapters speak CLIs.
4. **File-based state.** No database. Managed by the CLI; agents never mutate state by hand.
5. **Reality decides.** Nothing is done without an E2E happy-path check. (Sacred foundation.)
6. **Sacred foundation (Zion).** Non-negotiable values baked into Neo's identity.

See [`AGENTS.md`](AGENTS.md) for the full contract and [`DEVIN.md`](DEVIN.md) for Devin-specific notes.
