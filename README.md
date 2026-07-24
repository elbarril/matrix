# Matrix — Personal Intelligence Engine (built for Devin CLI)

Matrix is your personal intelligence layer: one root repo holds the brain, projects live outside and are pulled on demand, and a `_brain` symlink bridges an active project to the intelligence. The brain is written to be **CLI-agnostic in design** — it speaks only in capabilities, never a specific CLI's tools — but **today it is built, installed, and maintained for Devin CLI only**. Adding another CLI later would cost one small adapter, not a brain rewrite.

> Themed after the Matrix trilogy. Every component is named after the character or place whose function it mirrors. See [`AGENTS.md`](AGENTS.md) for the canonical contract.

---

## Empezá acá si no sabés mucho de agentes IA

Esta sección explica todo el sistema en criollo, sin asumir que sabés cómo trabajan los agentes de IA. Si ya lo tenés claro, saltá a [El problema que resuelve Matrix](#el-problema-que-resuelve-matrix).

### ¿Qué es un "agente de IA" en este contexto?

Un agente es un asistente de IA (en este caso, Devin CLI) al que le das una tarea en lenguaje natural y que puede leer archivos, escribir código, correr comandos de terminal, y tomar decisiones sobre qué hacer paso a paso, sin que vos le digas cada click. No es un chatbot que solo contesta preguntas: puede efectivamente modificar tu proyecto.

El problema de un agente "pelado" (sin nada de esto) es que cada sesión nueva no sabe nada de las anteriores, no sabe cómo querés que trabaje, no sabe tus reglas, y hay que explicarle todo de cero cada vez. Matrix existe para que eso no pase.

### ¿Qué es Matrix, en una frase?

Matrix es un cerebro persistente y compartido que le da a Devin CLI memoria, reglas de comportamiento, y un equipo de "especialistas" con roles fijos — todo guardado en archivos de texto plano en este repositorio, para que cualquier sesión de Devin, en cualquiera de tus proyectos, tenga el mismo criterio y el mismo historial.

### ¿Cómo se activa esto en la práctica? (la magia del `_brain`)

1. Este repo (`matrix/`) tiene el "cerebro": reglas, agentes, memoria.
2. Cada proyecto tuyo (otro repo, en otra carpeta) puede **enlazarse** a este cerebro corriendo `bin/matrix select <nombre>`. Eso crea dos cosas dentro del proyecto:
   - un **symlink** llamado `_brain` que apunta a esta carpeta `matrix/` (así el proyecto puede "ver" el cerebro sin copiarlo);
   - un archivo `AGENTS.local.md` con un bloque especial que le dice a Devin: *"antes de responder cualquier cosa en este proyecto, leé primero el contrato de Matrix y el agente maestro Neo"*.
3. Devin CLI lee automáticamente `AGENTS.local.md` al arrancar en esa carpeta. Por eso la activación de Neo **no depende de que te acuerdes de invocarlo**: es automática, mecánica, no probabilística.
4. Una vez activo, siempre hablás con **Neo** (el agente maestro). Neo nunca te hace elegir un especialista de un menú: interpreta lo que pedís y, si hace falta, delega en el especialista correcto por su cuenta.
5. El proyecto en sí **nunca se ensucia** con la inteligencia: solo tiene un symlink y un bloque de texto en un archivo que está en `.gitignore`. Si algún día "desconectás" el proyecto (`matrix deselect`), esos dos elementos se limpian solos.

### ¿Quién hace qué? (el equipo, en criollo)

No hay un solo "modelo" haciendo todo. Matrix reparte el trabajo entre roles con un propósito claro, para que cada tarea la resuelva quien mejor la sabe hacer:

| Quién | Qué hace, en criollo |
|---|---|
| **Neo** | Es con quien vos hablás siempre. Entiende el pedido y decide si lo resuelve él mismo (algo chico) o si llama a un especialista (trabajo real). |
| **The Oracle** | El investigador. Lo llamás (indirectamente, vía Neo) cuando hace falta averiguar algo, comparar opciones, o confirmar hechos antes de actuar. |
| **Morpheus** | El planificador. Convierte un pedido ambiguo ("quiero que el sistema soporte X") en una lista ordenada de pasos concretos. |
| **The Architect** | El diseñador. Revisa el plan de Morpheus y decide cómo encaja técnicamente antes de que se escriba una sola línea de código. |
| **Trinity** | El que construye. Implementa el código real, el que efectivamente cambia archivos. |
| **Agent Smith** | El evaluador. Prueba lo que construyó Trinity, busca fallas reales (no en la teoría, corriendo comandos de verdad), y bloquea el cierre si algo no anda. |
| **The Keymaker** | Git/operaciones. Solo entra en juego si el pedido es explícitamente sobre ramas, merges, o control de versiones. |

Un pedido de "arreglame un bug" típicamente pasa por Smith (encuentra la causa) → Trinity (arregla) → Smith (confirma que ahora sí funciona). Un pedido de "quiero una funcionalidad nueva" típicamente pasa por Morpheus (plan) → Architect (revisión) → Trinity (construye) → Smith (gate final). **Vos nunca hablás con ellos directamente** — es Neo quien los invoca como sub-agentes y te cuenta el resultado.

### Dos gates que se llaman parecido pero preguntan cosas distintas

Es fácil confundirlos porque los dos son hooks de Seraph y los dos aparecen al "cerrar" algo, pero responden preguntas distintas:

- **`validate_phase_close`** — el gate de **realidad del contenido**: "¿esto que decís que funciona, funciona de verdad?". No escribe nada en disco por sí mismo; recibe `{"phase","e2e","evidence","lesson"}` y devuelve PASS/BLOCK por stdout. Es manual: solo corre si el agente decide invocarlo al cerrar una fase (`spec`/`develop`/`test`/`eval`). Nada de Devin lo dispara solo.
- **`post_run_audit`** — el gate de **proceso**: "¿el agente siguió los pasos obligatorios de activación?" (no si el trabajo es real, sino si se hizo el ritual: `pre_activation_check`, etc.). Este sí persiste: escribe `brain/state/validation-report.json`. Se alimenta automáticamente de eventos reales del ciclo de vida de Devin (`SessionStart`, `PostToolUse`, `SessionEnd`) vía el adaptador (`adapters/devin/hooks/session_audit.py` → `hooks/audit_event.py` → `hooks/session_close.py`).

En criollo: uno audita el **qué** (¿el trabajo es real?), el otro audita el **cómo** (¿se siguió el protocolo?). Podés pasar uno y fallar el otro.

### ¿Por qué tantas capas / nombres raros?

Porque así el sistema no queda atado a Devin CLI para siempre. Las reglas y los agentes (`brain/`) están escritos en un lenguaje neutral — nunca dicen "usá la herramienta X de tal CLI", dicen "necesito la capacidad de leer archivos". Un traductor delgado (**el adaptador de Devin**, en `adapters/devin/`) es lo único que sabe que hoy el CLI es Devin. Si el día de mañana usás otro CLI, se cambia ese traductor (chico) y el cerebro entero se reutiliza tal cual.

### ¿Qué es "el estado" y por qué no se sube a git?

Matrix necesita recordar cosas entre sesiones: qué proyecto es tu foco actual, qué proyectos tenés "calientes", un historial de checkpoints, un log de eventos. Todo eso son **archivos de texto** en `brain/state/` — nunca una base de datos. Cambian todo el tiempo y son específicos de tu máquina, así que están en `.gitignore`: no se commitean, no ensucian el historial del repo.

### ¿Qué es un "checkpoint"? ¿Y en qué se diferencia de una "lesson"?

Un **checkpoint** es una nota con fecha que Neo (o vos) guarda cuando algo importante pasó ("implementé X, quedó pendiente Y"). Es memoria de **corto plazo**: sirve para retomar un hilo cortado (una sesión que se compactó, un cambio de foco), no para acordarse de algo para siempre. Se escribe con `bin/matrix checkpoint "nota"`, nunca a mano.

Por default, `matrix status` y `matrix activity` muestran los checkpoints/eventos del **proyecto activo únicamente** (resuelto igual que Neo: symlink `_brain` del directorio donde estás parado > `primary` de `.context.yaml`). Esto es a propósito: `checkpoints.jsonl` es un archivo único y compartido entre *todos* tus proyectos, así que una vista global mezclaría el historial de sandisk con el de calian y el que te importa quedaría enterrado apenas trabajes en otro proyecto. Usá `matrix status --all` o `matrix activity --all` cuando de verdad quieras la vista cruzada, o `matrix activity --project=<nombre>` para mirar otro proyecto sin moverte de carpeta.

Una **lesson** (`brain/data/lessons.md` o `brain/data/lessons/<proyecto>.md`) es memoria de **largo plazo**: cosas que la realidad enseñó y que valen para siempre (una decisión del cliente, un link de acceso a una instancia, un bug real y su causa). A diferencia del checkpoint, no se cae de ninguna ventana — se lee siempre, íntegro, al bindear ese proyecto. El workflow `eval` (`brain/workflows/eval.md`) es el que la escribe, y desde ahora el hook `validate_phase_close` **bloquea** cerrar la fase `eval` si no se declaró explícitamente qué se aprendió (o un "N/A" razonado) — antes era solo una convención que se podía saltear en silencio.

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

One master, five core specialists, one opt-in sixth. Names map to function.

- **Neo** — *master*. The single voice. Routes, holds context, carries the sacred foundation, bridges every CLI.
- **The Oracle** — *researcher*. Gathers, compares, cites, foresees. "What is true / what exists."
- **Morpheus** — *planner*. Turns ambiguity into ordered scope. "What / when."
- **The Architect** — *architect*. Designs structure, names trade-offs, reviews plans before build. "How it fits."
- **Trinity** — *builder*. Implements and ships real, working code.
- **Agent Smith** — *evaluator*. Tests, critiques, finds the flaw, blocks weak work.
- **The Keymaker** — *git/ops, opt-in*. Branches, paths, access, version control.

**Routing seam:** Morpheus answers *what/when*; the Architect answers *how it fits* and reviews the plan before Trinity builds; Smith gates the result before "done".

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
├── .context.yaml              # primary/default project (fallback, not exclusive — see "Multi-project")
├── .registry.json             # all known projects
├── bin/matrix                 # CLI orchestrator (Layer 1)
├── hooks/                     # Seraph — portable enforcement (python)
│   ├── pre_activation_check.py
│   ├── validate_phase_close.py
│   └── post_run_audit.py
├── adapters/                  # Trainman — Layer 3 (devin/ only, for now)
├── brain/                     # Layer 2 — the intelligence core
│   ├── config.yaml            # GITIGNORED: per-machine (user, language, timezone)
│   ├── agents/                # neo, oracle, morpheus, architect, trinity, smith, keymaker
│   ├── workflows/             # spec → develop → test → eval
│   ├── data/                  # lessons.md, code-quality-review-lens.md, capability-map.md
│   ├── subsystems/            # the fleet (federated ships)
│   ├── state/                 # GITIGNORED: workspace.yaml, activity.log, checkpoints.jsonl, ...
│   └── output/                # GITIGNORED: Matrix-workspace-mode scratch (see AGENTS.md §1)
├── docs/SYSTEM_TRUTH.md       # The Source (generated/validated)
└── clients/                   # GITIGNORED: pulled project repos
```

Work artifacts for a **bound project** are written to that project's own `matrix-output/` directory (sibling to its `_brain` symlink) — never inside this repo. See `AGENTS.md` §1. `matrix select` auto-adds `matrix-output/` (plus `AGENTS.local.md` and `_brain`) to that project's `.gitignore`, so it never leaks into the project's own git history.

## CLI commands

```text
list                      List registered projects
add <name> [path]         Register a project
select <name>             Bind a project: create its _brain symlink + AGENTS.local.md
                           block and make it the primary/default. Does NOT unbind
                           other already-bound projects (see "Multi-project" below).
deselect [name]           Unbind the named project (or the current primary if no
                           name is given). Other bound projects are untouched.
work <name>               Warm a project into the active set (bookmark; does not
                           create the _brain symlink and does not unbind anything)
unwork <name>             Remove a project from the warm set; if it was bound,
                           unbind it first
workspace                 Show the warm set, marking which entries are [bound]
bindings                  List every registered project, verifying in real time
                           whether its _brain symlink + AGENTS.local.md block
                           actually exist on disk right now
status [--all]            Show primary/default, bound count+names, warm count,
                           registered count, recent checkpoints and Link events —
                           scoped to the resolved project by default; --all for
                           the old unfiltered, cross-project view
checkpoint "<note>"       Write a checkpoint (+ Link entry)
activity [n] [--all] [--project=<name>]   Show last n Link events, scoped to the
                           resolved project by default (default n=20)
hooks <name> [json]       Run a Seraph hook
build --target=<cli>      Trainman: generate native CLI artifacts
install --target=<cli>    Trainman: deploy generated artifacts into the CLI's discovery path
help                      Usage
```

## Multi-project: varios proyectos "vivos" a la vez

Podés tener **más de un proyecto bindeado (`bound`) al mismo tiempo** — cada uno con su propio symlink `_brain` y su propio bloque en `AGENTS.local.md`, activando a Neo automáticamente sin que se molesten entre sí. Esto es útil si trabajás en paralelo (por ejemplo, dos terminales, dos proyectos distintos, cada uno con su sesión de Devin CLI).

Hay tres conceptos distintos, y es importante no confundirlos:

- **`bound` (bindeado)** — un hecho del *filesystem*, no un flag guardado en ningún archivo: un proyecto está bindeado si y solo si tiene un symlink `_brain` válido apuntando a este cerebro **y** un bloque `AGENTS.local.md` vigente. `matrix bindings` siempre chequea esto en vivo, nunca confía en un caché. Pueden estar bindeados varios proyectos a la vez.
- **`warm` (caliente)** — un proyecto "de interés" guardado en `brain/state/workspace.yaml`. Es solo una lista de bookmarks; estar en la lista NO implica tener el symlink creado. Todo proyecto bindeado está automáticamente en la lista warm, pero no al revés.
- **`primary`/default** — el único proyecto guardado en `.context.yaml`. Ya **no es exclusivo**: es simplemente el proyecto que se usa como *fallback* cuando una sesión no puede resolver su proyecto de otra forma (sin `--project`, sin `$MATRIX_PROJECT`, y sin estar parado dentro de una carpeta con `_brain`).

**¿Cómo resuelve Neo qué proyecto es "el suyo" en una sesión dada?** Con esta prioridad: `--project <nombre>` (si lo pasaste explícito) > variable de entorno `$MATRIX_PROJECT` > el symlink `_brain` de la carpeta donde estás parado (`cwd`) > el `primary` de `.context.yaml` como último recurso. En la práctica esto significa: **si abrís una terminal dentro de un proyecto bindeado, esa sesión ya sabe cuál es su proyecto sin importar qué otro proyecto hayas seleccionado como "primary" en otro lado.**

Ejemplo de uso real con dos proyectos a la vez:

```bash
./bin/matrix add sitio-web /home/vos/proyectos/sitio-web
./bin/matrix add api-backend /home/vos/proyectos/api-backend

./bin/matrix select sitio-web      # bindea sitio-web (symlink + AGENTS.local.md)
./bin/matrix select api-backend    # bindea api-backend SIN desbindear a sitio-web

./bin/matrix bindings
#  ✓ sitio-web -> /home/vos/proyectos/sitio-web [bound]
#  ✓ api-backend -> /home/vos/proyectos/api-backend [bound]

./bin/matrix status
# Primary project: api-backend       (el último select-eado, es el default)
# Bound: 2 project(s) (sitio-web api-backend)
# Warm set: 2 project(s)

./bin/matrix deselect sitio-web    # desbindea SOLO sitio-web; api-backend sigue intacto
```

Ahora podés abrir Devin CLI dentro de `sitio-web/` y dentro de `api-backend/` (en dos terminales distintas, o en momentos distintos) y ambas sesiones activan a Neo automáticamente, cada una con el contexto de su propio proyecto — sin que una sesión pise el binding de la otra.

**Seguridad de estado concurrente:** `bin/matrix` toma un lock global (`flock`) al arrancar cualquier comando, así que si corrés dos comandos `bin/matrix` al mismo tiempo desde sesiones distintas no se corrompen los archivos de estado compartidos (`workspace.yaml`, `.registry.json`, `.context.yaml`, el ledger). Si `flock` no está disponible en tu sistema (por ejemplo, macOS sin GNU coreutils), el comando avisa y sigue sin lock — no instala nada nuevo, pero perdés esa protección puntual.

## Quick start

```bash
# Register and bind a project
./bin/matrix add myproject /path/to/project
./bin/matrix select myproject

# Bind a second project without losing the first one's binding
./bin/matrix add otherproject /path/to/otherproject
./bin/matrix select otherproject
./bin/matrix bindings          # both show as [bound]

# Or just warm several projects as bookmarks, without binding them
./bin/matrix work myproject
./bin/matrix work otherproject
./bin/matrix workspace

# Generate native artifacts and deploy them into Devin's global discovery path
./bin/matrix build   --target=devin
./bin/matrix install --target=devin
# (then invoke Neo via `/neo` in Devin CLI, from any project; the user always talks to Neo first)
```

## Uso diario típico

- **Un solo proyecto, uso normal:** `matrix select <proyecto>` una vez; después simplemente abrís Devin CLI dentro de esa carpeta cuando quieras trabajar — Neo se activa solo. No hace falta re-seleccionar nada en cada sesión.
- **Cambiar de foco sin perder el anterior:** `matrix select <otro-proyecto>` no rompe el binding del proyecto anterior — solo cambia cuál es el `primary`/default. Si querés desactivar explícitamente uno, usá `matrix deselect <nombre>`.
- **Ver qué está pasando:** `matrix status` (resumen general), `matrix bindings` (verificación real en disco de cuáles proyectos tienen Neo activo ahora), `matrix workspace` (lista de bookmarks/warm), `matrix list` (todos los proyectos conocidos).
- **Dejar una nota para la próxima sesión:** `matrix checkpoint "lo que hice y lo que falta"`. Neo también lo hace automáticamente en hitos importantes.
- **Trabajar en el propio Matrix (no en un proyecto):** parate en la raíz de este repo y hablale a Neo directamente — entra en "Matrix workspace mode" (sin proyecto bindeado, trabajando sobre el sistema mismo).

## Principles

1. **Root intelligence + pulled projects.** The root repo is the brain; project repos are pulled on demand.
2. **One master, capability specialists.** Neo is the face; specialists are capabilities, not topics. Roster discipline: add one → retire one.
3. **CLI-agnostic core.** The brain speaks capabilities; adapters speak CLIs.
4. **File-based state.** No database. Managed by the CLI; agents never mutate state by hand.
5. **Reality decides.** Nothing is done without an E2E happy-path check. (Sacred foundation.)
6. **Sacred foundation (Zion).** Non-negotiable values baked into Neo's identity.

See [`AGENTS.md`](AGENTS.md) for the full contract and [`DEVIN.md`](DEVIN.md) for Devin-specific notes.
