# Matrix — Devin Adapter Notes

Devin CLI is the **only** host Matrix currently runs under. This file documents the Devin-specific binding. The brain itself ([`AGENTS.md`](AGENTS.md) + `brain/`) is written to stay CLI-agnostic (so a second adapter would be cheap to add later), but this adapter is the only one implemented and maintained today — this is Layer 3 (the Trainman) for Devin.

## Prime directives

1. **Read [`AGENTS.md`](AGENTS.md) first.** It is the document of record for all agent behavior.
2. **The user talks only to Neo.** Specialists are reached through Neo's routing, never directly.
3. **Sacred foundation (Zion) is non-negotiable.** See `AGENTS.md` §4.
4. **State is files.** Managed by `bin/matrix`. Agents never mutate state files by hand.
5. **Reality decides.** Nothing is "done" without an E2E happy-path check (`validate_phase_close`).

## Capability → Devin tool mapping (the Trainman table)

The brain declares abstract capabilities; the Devin adapter binds them:

| Capability | Devin native |
|---|---|
| `read` | read file |
| `edit` | edit / multi-edit |
| `search` | grep / find |
| `code-nav` | semantic search (or fallback to search) |
| `run-subagent` | `run_subagent` |
| `ask-user` | `ask_user_question` |
| `run-command` | `run_command` |
| `browser` | `mcp__chrome-browser__*` (visual QA; no-op if that MCP server isn't configured) |
| `docs-lookup` | `mcp__context7__*` (version-pinned library/framework docs; Oracle) |

Every generated `AGENT.md` also gets a Devin-native `allowed-tools:` grant, resolved from the same `capabilities:` list through a second, smaller map (`allowed_tools:` in `adapters/devin/adapter.yaml`) — see "Least-privilege" in `capability-map.md`. Neo's `SKILL.md` is deliberately left without `allowed-tools` (see below).

The Trainman is a **two-step** flow for Devin:

```bash
bin/matrix build   --target=devin   # 1. generate artifacts → adapters/devin/generated/.agents/
bin/matrix install --target=devin   # 2. deploy them into Devin's global discovery path
```

- **build** renders thin-pointer artifacts from the agnostic `brain/agents/*.md` into `adapters/devin/generated/` (gitignored, ephemeral). Each pointer references the brain by **absolute path** so it resolves from any working directory.
- **install** *copies* those pointers (self-contained, not symlinks) into Devin's global path. Copies survive even if `generated/` is wiped, because they point at the git-tracked brain by absolute path. Re-run both steps after changing an agent's `name`/`description` or the roster.

### Where the artifacts land (global discovery)

| Artifact | Global path | Effect |
|---|---|---|
| Neo (master) | `~/.config/devin/skills/neo/SKILL.md` | `/neo` and autonomous invocation in **every** project |
| Specialists | `~/.config/devin/agents/<name>/AGENT.md` | Subagent profiles available in **every** project |

Global install is deliberate: Neo must be reachable from any repo — inside Matrix, inside `clients/`, or an unrelated project. The installer also removes stale, broken Matrix-owned symlinks left by older ad-hoc wiring (it never touches non-Matrix entries).

## Model policy

Every generated `SKILL.md`/`AGENT.md` carries a `model:` frontmatter field, resolved at build time from the agent's `model_policy` tier (`cheap`/`reasoning`/`auto`, declared in `brain/agents/<name>.md`) through `adapters/devin/adapter.yaml`'s `model_policy` map. Re-derived 2026-07-17 from `devin-master-documentation`'s model pages (`docs/22-devin-cli-models-overview.md`, `docs/26-cognition-swe-models.md`), which mirror Devin CLI's own model-selection guidance: "multi-file refactors, architecture changes, deep reasoning" → `opus`/`gpt`; "quick edits, bug fixes, cost-sensitive work" → `swe` (fast); mixed workloads → `adaptive` (Cognition's per-task router):

| Tier | Model | Used by | Why |
|---|---|---|---|
| `cheap` | `swe-1-7-medium` | Lock, Logos Sparks | Gratis hoy durante su beta; apto para trabajo mecánico/plumbing. La fecha exacta de cierre de su free preview no es re-verificable hoy en una fuente viva. |
| `reasoning` | `sonnet` (Claude Sonnet 5) | Architect, Morpheus, Oracle, Smith | Cambiado de `opus` a `sonnet` (2026-07-27, decisión explícita del usuario: velocidad/costo sobre calidad máxima). Anthropic posiciona Sonnet 5 como "broadly comparable to Opus 4.8... while being faster and cheaper"; brecha de benchmark medida y chica (SWE-bench Verified 85.2% vs 88.6% de Opus). Real cost hoy: $2/$10 per MTok (introductorio hasta 2026-08-31, luego $3/$15) vs $5/$25 de Opus — ~60% más barato. |
| `auto` | `adaptive` | Neo, Trinity | Mixed work (routing + implementation spans trivial to complex); Cognition's own per-task router picks cheap/fast vs. capable per request instead of pinning one model. La ventana de precio introductorio ($0.50/$2.00 per MTok) venció el 2026-07-07; la tarifa posterior es desconocida y depende del plan de billing del usuario. |

**Both `swe-1.7` and `swe-1-7` are accepted and normalize to the same canonical id** (confirmed via the sessions database — do not assume dash vs. dot matters). `swe-1-7-lightning` is a genuinely distinct, faster model, not just an alias.

**Time-bound:** SWE-1.7 está gratis hoy durante su beta, pero la fecha 2026-08-08 atribuida al fin de su free preview no es re-verificable hoy en una fuente viva; conservarla solo como fecha no confirmada y hacer un próximo recheck sugerido el 2026-08-08 (además de revisiones periódicas). La ventana introductoria de Adaptive venció el 2026-07-07; no afirmar una tarifa post-intro sin consultar el plan de billing del usuario. Re-verify this table periodically (repeat the `--model X -p "OK"` + sessions.db check, or just watch `/model`'s selector) and update the map if needed. This is exactly the kind of drift this file exists to catch.

To move a tier onto a different model, edit the map in `adapters/devin/adapter.yaml` and rerun:

```bash
bin/matrix build   --target=devin
bin/matrix install --target=devin
```

No agent file needs to change — the tier assignment (which kind of work an agent does) is separate from which model backs that tier.

## External MCP servers this brain assumes

| Server | Scope | Added | Used by |
|---|---|---|---|
| `chrome-browser` | user (`~/.config/devin/config.json`) | pre-existing | Smith (`browser` capability) |
| `context7` | user (`~/.config/devin/config.json`) | 2026-07-15, `devin mcp add context7 --url https://mcp.context7.com/mcp --scope user` | Oracle (`docs-lookup` capability) |

Both are **user-scope**, so they follow Neo/the specialists globally rather than needing per-project setup. Neither is required for the roster to function — the corresponding capability (`browser`, `docs-lookup`) is simply unavailable if the server isn't configured on a given machine, and the agent should say so rather than fake the check (Foundation 3). context7 works unauthenticated (rate-limited, verified live); running `devin mcp add ...` again prints an OAuth URL for higher rate limits — optional, not required.

## Least-privilege `allowed-tools`

Every specialist's generated `AGENT.md` carries an `allowed-tools:` list, resolved from its
`capabilities:` frontmatter through the `allowed_tools:` map in `adapters/devin/adapter.yaml`
(categories: `read`, `edit`, `write`, `grep`, `glob`, `exec`, plus `mcp__server__tool` patterns).
Re-measure, don't trust prose: `sed -n '2,/^---$/p' adapters/devin/generated/.agents/agents/<name>/AGENT.md`
vs. `diff` against the installed copy. Current written grant for a full-capability specialist:
`read, edit, write, grep, glob, exec, mcp__chrome-browser__*` — `edit`+`write` both appear because
the abstract `edit` capability maps to both here (Matrix accepts that widening; see `smith.md`
`<boundaries>` for the narrower intent).

Grant-resolution timing (subagent tool-grant snapshotting at CLI process start vs. hot-reload;
audit-log session-id attribution for inner subagents) is now **resolved for the timing question**
(snapshot-at-start, confirmed) but still has an open item on audit attribution — see
`brain/output/research/devin-tool-grant-resolution-timing.md` for the spikes and current status.

**Known fixes to this mapping (detail moved out, one-line pointer each):**
- `pre_exec_guard.py` token-match false-positive fix → `brain/output/eval/pre-exec-guard-false-positive-fix.md`.
- Logos-Sparks `run-command` capability removal + exec allowlist for subagents (`permissions.allow` /
  `PreToolUse` guard) → `brain/output/eval/devin-subagent-exec-hardening.md`.

Neo's `SKILL.md` is deliberately left without `allowed-tools` (needs `run_subagent`/`ask_user_question`,
neither is a nameable `allowed-tools` entry). The blast radius of an unrestricted Neo is also lower
in practice: it runs in the foreground, user-approved, not as an unattended subagent.

## Subagents can never ask the user directly

Devin withholds `ask_user_question` from every subagent unconditionally — not configurable via `allowed-tools` or `permissions`. Specialists that declare the `ask-user` capability (Architect, Morpheus, Oracle, Trinity) run as Devin subagents, so they cannot call it. When one of them needs a decision from the user, it stops and reports the question back to Neo (the master skill, not a subagent — it keeps `ask_user_question`), which asks and re-delegates. `run_subagent`/`read_subagent` are similarly unavailable inside a subagent by default (nesting is disabled beyond the root agent unless `max-nesting` is set — none of our core specialists need it, they're all depth-1 children of Neo).

**Nesting spike (verified, not just documented):** a temporary custom subagent profile (`max-nesting: 2` in its frontmatter, no other restriction) was spawned by Neo and successfully called `run_subagent` itself, spawning a grandchild `subagent_explore` and reading its result back via `read_subagent(block=true)` — full round trip, no denial, no silent fallback. Confirms the docs' claim (`subagents.mdx` "Nesting Depth") is accurate in this environment: a depth-1 custom subagent with `max-nesting` set can legitimately spawn and read depth-2 children. This matters for federated ships (see `brain/subsystems/FEDERATION.md`): a ship's captain (e.g. Niobe) can be generated with `max-nesting: 2` and delegate directly to her own crew, instead of needing a courier protocol where the root agent spawns the crew on the captain's behalf.

## Federated ships and `max-nesting`

Federated ship captains (e.g. `logos-niobe`) are generated as custom subagent profiles with a `max-nesting` frontmatter value. The value is derived by the Trainman from the ship manifest's `captain`/`crew` graph (`depth_from_root + subtree_depth`) and injected **only** into the captain's artifact. Crew leaves (e.g. `logos-ghost`, `logos-sparks`) do not carry the field.

For Logos:
- `logos-niobe/AGENT.md` → `max-nesting: 2` (captain at depth 1 from Neo, crew at depth 2).
- `logos-ghost/AGENT.md` and `logos-sparks/AGENT.md` → no `max-nesting` field.

This lets Niobe call `run_subagent` and `read_subagent` directly on her crew without a courier protocol. The formula is verified only for depth 2; a ship with sub-captains (depth ≥3) needs a new spike before trusting the same derivation.

## Mapping to Devin's native structure

- **Master (Neo)** → a Devin Skill (`.agents/skills/neo/SKILL.md`), generated by the adapter, installed globally.
- **Specialists** → Devin Subagents (`.agents/agents/<name>/AGENT.md`), generated by the adapter, installed globally. Neo routes to them via `run_subagent` — including in **Matrix workspace mode**, where Neo delegates real work to specialists and only handles trivial single-step changes itself.
- **Enforcement (Seraph)** → the same portable `hooks/*.py`, invoked via `bin/matrix hooks <name>` or the skill's pre/post steps.

## Session hygiene

See [`AGENTS.md`](AGENTS.md) §12. In short: read the contract, know the registry, resolve context, read recent checkpoints + lessons, respect boundaries, never log secrets, checkpoint progress, verify reality before "done".

## Matrix workspace mode auto-bootstrap (AGENTS.md §6 step 0)

AGENTS.md §6 step 0 says becoming Neo in Matrix workspace mode must not depend
on topic-matching heuristics alone. **This reuses existing infrastructure —
`adapters/devin/hooks/session_audit.py` and its "Etapa G/H3" activation-inject
experiment — rather than a new hook.** (A first pass at this added a brand-new
project-level `.devin/config.json` + a second SessionStart script; that was
reverted the same session once this existing, more complete mechanism was
found. Lesson: check `adapters/<target>/` for an existing lever before adding
a new one — see `brain/data/lessons.md`.)

- `session_audit.py` is already wired into `~/.config/devin/config.json`'s
  `hooks.SessionStart` / `UserPromptSubmit` / `PostToolUse` / `PostCompaction` /
  `SessionEnd` by `adapters/devin/install-hooks.sh`, which `adapters/devin/install.sh`
  now calls automatically as its last step — so `bin/matrix install --target=devin`
  sets this up on any machine, not just this one.
- The experiment flag `experiment.activation_inject` in `adapters/devin/config.yaml`
  gates an extra behavior on `SessionStart`/`UserPromptSubmit`: render
  `brain/data/activation-preamble.tmpl` (the **same** template already used for
  the generated `neo` skill and for bound projects' `AGENTS.local.md` block —
  see `matrix_block_tmp()` in `bin/matrix`) and emit it as Devin's
  `hookSpecificOutput.additionalContext`. One wording, three delivery surfaces.
- This file (`DEVIN.md`) is the doc that `{{ADAPTER_DOC_PATH}}` resolves to in
  `brain/data/activation-preamble.tmpl`, via `binding.doc_path: "DEVIN.md"` in
  `adapters/devin/adapter.yaml`. The three surfaces that render that template —
  `bin/matrix matrix_block_tmp()`, `adapters/_build.py` (the generated `neo`
  SKILL.md), and `session_audit.py`'s `_render_activation_preamble()` — all
  resolve the placeholder to an absolute path to this file, never a literal
  `"DEVIN.md"` baked into Layer 1/3 code. A future non-devin adapter only needs
  its own `binding.doc_path`; no code in `bin/matrix`/`_build.py`/hooks changes.
- `_activation_reinject_scope()` (added under B1-Option 1, post-audit backlog —
  see `brain/output/architecture/matrix-system-health-audit.md`) scopes that
  injection to sessions whose cwd resolves to Matrix workspace mode **or**
  a real bound external project (valid `_brain` symlink + managed
  `AGENTS.local.md` block), via `bin/matrix scope` — a thin wrapper around
  the existing `resolve_scope()` "where am I?" resolver, reused instead of
  re-implemented to avoid a second, divergence-prone copy of that logic in
  Python. Bound projects were originally excluded on the theory that the
  one-shot block written into their `AGENTS.local.md` by `bin/matrix select`
  was enough; the audit measured the real symptom that assumption caused
  (no delegation / no checkpoint discipline outside the Matrix root once a
  session's context window pushed that one-shot block out), so reinjection
  now also fires there, every `session_start` / `user_prompt_submit`, the
  same way it already did for workspace mode.
- `activation_inject` is now `true` in `adapters/devin/config.yaml` (was `false`
  since it was first built, 2026-07-17, and evidently never turned on). It now
  affects both Matrix workspace mode and bound external projects, by design.

**2026-07-28 — verified with ground-truth evidence, not just a text response.**
`devin -p "reply with just the word OK" --permission-mode dangerous` was run in
a fresh process with cwd at the Matrix root. The final reply was just `"OK"` —
the model did not narrate an activation — but `brain/state/hook-audit.jsonl`
shows the *actual tool calls* of that exact session (`fringe-boat`,
`session_start` → `session_end` in the matching time window): `read
/home/emiliano/www/emisrepos/matrix/AGENTS.md` immediately followed by `read
.../brain/agents/neo.md`, i.e. the session-start-bootstrap block was correctly
delivered and followed, even though the visible task never mentioned Neo or
Matrix and the final text gave no indication either way. **Silence in the
reply is not evidence of failure here — check the audit log, not the prose.**
Re-verify after any Devin CLI upgrade, since this depends on `SessionStart` +
`additionalContext` injection continuing to work as documented in
`extensibility/hooks/lifecycle-hooks.mdx`.

## Hardening `permissions.deny` for secret stores

`bin/matrix harden --target=devin` reconciles Devin's `permissions.deny` list
against the declarative `secret_deny` block in `adapters/devin/config.yaml`.
It is dry-run by default; use `--apply` to write and `--revert` to remove
Matrix-managed entries. The command only touches `permissions.deny` and uses a
sidecar (`~/.config/devin/.matrix-managed-deny.json`) so manual deletions are
respected across runs.

The static list covers common credential stores (SSH, AWS, GPG, kubeconfig,
browser logins, Devin's own local state, etc.). Auto-discovery scans `$HOME`
up to `max_depth` for hidden directories containing a `credentials/` folder or
`.env` files, emitting directory-level `Read(...)` patterns only — it never
writes specific credential filenames into the repo or logs.

**Important:** `permissions.deny` with `Read(...)` only blocks the `read_file`
tool. It does **not** block `grep`/`glob` or `exec` (e.g. `cat`). It is a partial
mitigation against incidental reads, not a sandbox.

## Headless / non-interactive execution (`devin -p`)

`devin -p "<prompt>" [--permission-mode dangerous] [-r <session_id>]` runs a single turn
non-interactively and exits — the real headless primitive Hardline/AFK builds on. Exit code 0
does not mean success (parse the printed text; refusals also exit 0). Full spike findings,
version-pinned details, and open items: `brain/output/research/devin-headless-execution.md`.

## Why enforcement is portable, not Devin-coupled

Enforcement lives in `hooks/*.py` with a JSON in/out contract, fired by `bin/matrix hooks <name>`. The logic travels with the brain, not with Devin — so the exact same checks would run unchanged under a future CLI adapter, if one is ever built. The adapter only decides *when* to fire them.

## Relocated from `brain/data/capability-map.md` (Phase 2, `validate_layer2` remediation)

The concrete, Devin-specific material below used to live inline in `brain/data/capability-map.md`. It was moved here wholesale (no semantic change) so that file could stay CLI-agnostic per the Layer-2 golden rule, while this concrete detail — which legitimately must name Devin's real tool identifiers — keeps living somewhere. `capability-map.md` now carries only the abstract capability list, the model-policy concept, and the least-privilege concept; this section is the "what it actually resolves to today" companion.

### The live `adapter.yaml` binding (concrete, not illustrative)

```yaml
# adapters/devin/adapter.yaml
capabilities:
  read: read_file
  edit: [edit, multi_edit, write]
  search: [grep_search, find_by_name]
  code-nav: codebase_search        # fallback: search
  run-subagent: run_subagent
  run-command: run_command
  ask-user: ask_user_question
  browser: mcp__chrome-browser     # visual QA; no-op if unconfigured; live subagent testing (2026-07-27) found mcp__chrome-browser__* CONFIRMED ABSENT despite this declared binding — see "Least-privilege allowed-tools" above
  docs-lookup: mcp__context7       # version-pinned library docs
render:
  master: skill        # → .agents/skills/<name>/SKILL.md
  specialist: subagent # → .agents/agents/<name>/AGENT.md
```

### `run-subagent` in nestable artifacts (the `max-nesting` mechanism)

Under Devin, `run_subagent`/`read_subagent` are disabled inside a subagent by default. They become available when the subagent profile carries a `max-nesting` frontmatter field whose value is at least the depth of the children it needs to spawn. The Trainman derives this value from the ship manifest's `captain`/`crew` graph (`depth_from_root + subtree_depth`) and injects it **only** into the captain's artifact. Crew leaves do not carry the field, because they have no subordinates to spawn. This is the Devin representation of the abstract `run-subagent` capability; it is not an `allowed-tools` grant.

### `ask-user` withheld from every subagent (mechanics)

Devin **never** allows a subagent to call `ask_user_question` — it is withheld from every subagent unconditionally, regardless of `allowed-tools` or permissions (platform rule, not configurable). Several specialists (Architect, Morpheus, Oracle, Trinity) declare the `ask-user` capability in the agnostic brain, but under the Devin adapter they run as **subagents** (`.agents/agents/<name>/AGENT.md`), so they cannot exercise it directly.

Resolution for the Devin adapter: a specialist that needs to ask the user stops and returns the question to **Neo** (the master skill — not a subagent, so it retains `ask_user_question`) instead of calling it itself. Neo relays the question, gets the answer, and re-delegates. This is a Devin-adapter concern only; the brain's `ask-user` capability declaration does not change, because another CLI's adapter may not have this restriction.

### MCP tool bindings (concrete)

`browser` resolves to `mcp__chrome-browser` and `docs-lookup` resolves to `mcp__context7` (see "External MCP servers this brain assumes" above for scope/setup). Both are Devin's MCP tool-naming convention (`mcp__<server>__<tool>`), not a capability-map concept — another adapter's docs-lookup/browser binding would use that CLI's own MCP (or non-MCP) tool-naming convention instead.

### Model policy → Devin frontmatter (mechanics)

The Trainman resolves each agent's `model_policy` tier (`cheap`/`reasoning`/`auto`) through the adapter's `model_policy` map and writes the result as `model: <name>` in the generated `SKILL.md`/`AGENT.md` frontmatter (see `extensibility/skills` and `subagents` in the Devin CLI docs — both support a `model` override field). Re-run `bin/matrix build --target=devin && bin/matrix install --target=devin` after changing `adapters/devin/adapter.yaml`'s `model_policy` map for the change to take effect globally.

## Lessons — detalle de adapter

`brain/data/lessons.md` keeps the universal operable rule for each lesson below; this section carries the Devin/Claude-Code-specific narrative and citations that were split out of it during the `validate_layer2` remediation, cross-referenced by lesson number. No rule content was lost in the split — only the platform-specific evidence moved here.

### Lesson 11

Se sospechó que subagents en background auto-deniegan tools MCP no aprobadas (basado en `subagents.mdx`). 4 tests controlados (MCP read-only y con side-effects, foreground vs background) no reprodujeron el bloqueo en este entorno. La causa real de un bloqueo pasado (figma-audit) fue más probablemente el grant de capabilities del *perfil* del subagente, no el flag `is_background`.

### Lesson 13

Evaluación real (Smith, 11 sesiones): Devin aplica `deny: ["Read(<ruta>/**)"]` sobre `read_file` inclusive en `--permission-mode dangerous`, y se propaga a subagentes. Ese mismo `deny` no bloquea `grep`/`glob` ni `exec` (`cat`, etc.).

### Lesson 14 (steps 2 and 3)

2. `subagents.mdx` "Nesting Depth" documentaba `max-nesting` desde el principio, y `capability-map.md` lo citaba correctamente ("subagents cannot spawn subagents **by default**") — la cláusula estaba ahí. El diseño leyó "by default" como "nunca".

3. El spike fue un subagente temporal, un `max-nesting: 2`, un `run_subagent`, un `read_subagent`.

### Lesson 18

Primera pasada (Architect, agent_id=1b0251ef, feasibility review, sin medir) encontró 3 líos en `brain/agents/neo.md` y afirmó 2 supuestos sobre Claude Code que resultaron **falsos** al verificarlos contra `claude-master-documentation/docs/` en la auditoría siguiente (agent_id=09c037aa, con lectura real de doc en vez de inferencia): Claude Code SÍ anida subagentes por default (profundidad 3, sin opt-in) y SÍ expone `agent_id`/`agent_type` en el payload de sus hooks — ambos mejor que Devin, no peor. El único hallazgo real que sobrevivió verificación: Claude Code no tiene un primitivo de **resume de subagente** (el resume de sesión sí existe, pero no es direccionable a un hijo específico), así que el patrón *Secure build* de `neo.md:57,98` (resumir la sesión del mismo Trinity con el fix puntual) no porta.

### Lesson 19 / 24 (twin findings, same flag)

La prueba solo es válida corriendo con permisos abiertos (`--permission-mode dangerous` o equivalente) y `write`/`edit`/`exec` disponibles.

### Lesson 20

La lección 18 original nació de una feasibility review (lectura + inferencia, sin spike) y afirmó 2 de 3 supuestos sobre Claude Code que resultaron falsos al re-verificarlos con lectura real de `docs/` en la auditoría siguiente.

### Lesson 21

Auditoría repo-wide (Architect, agent_id=09c037aa, 2026-07-27) encontró 29 puntos de acoplamiento a Devin fuera de `adapters/devin/` (16 en `brain/`, 6 en `hooks/`+`bin/matrix`, 7 en `_build.py`/docs), de los cuales 3 producen **falso verde**: `hooks/validate_ship.py` reporta PASS si no encuentra artifacts de Devin en vez de fallar fuerte; `bin/matrix`'s `path_is_bound()` define "bound" por la presencia de `AGENTS.local.md` (formato Devin) como parte del predicado de estado; `adapters/_harden.py` adivina una ruta de config para cualquier target desconocido y reporta éxito al escribir un archivo que esa plataforma nunca lee.

### Lesson 23

Re-verificación en vivo (Smith, agent_id=f920c882, 2026-07-27) de los 29 hallazgos de la lección 21 encontró: 27 siguen presentes, 0 arreglados, y `niobe.md` (0→4 menciones), `capability-map.md` (8→10) y `lessons.md` (+4, las propias lecciones 18/20/21 nombran Devin/Claude Code en `brain/`) **crecieron** en acoplamiento durante la misma ventana de trabajo que documentó el problema.

### Lesson 25

El bug real era que el productor (`bin/matrix phase_close()`) nunca escribía ese `session_id` correcto (correlacionaba con un marker de sesión stale, porque la restricción de diseño "Devin no expone session id a los hooks" quedó obsoleta con una versión nueva del CLI y nadie la re-midió).

### Lesson 26

Al re-otorgarle `edit` a Smith (rol de evaluador-con-remediación, 2026-07-27), Trinity verificó `generated/.../smith/AGENT.md` == `~/.config/devin/agents/smith/AGENT.md` (idénticos) y lo dio por medido. El spike en vivo posterior (Neo, mismo proceso de CLI que corrió el `install`) mostró que una sesión `smith` recién spawneada solo tenía `read, grep, find_by_name, exec` — sin `edit`/`write`. Ninguna doc revisada (`09-advanced-cli-features.md`, `07-troubleshooting.md`) especifica si la resolución de tools de un subagente se cachea al arrancar el proceso de CLI o se lee en vivo.

### Lesson 27

El spike de Neo en un proceso de CLI genuinamente nuevo (arrancado después del `install` de 2026-07-27) confirmó la hipótesis pendiente de la lección 26: el subagente `smith` recién spawneado reportó `read, edit, exec, grep, find_file_by_name` — `edit` estaba vivo — mientras que un profile de control de solo lectura siguió reportando su set restringido de siempre. Una llamada `edit` real del subagente `smith` llegó a `brain/state/hook-audit.jsonl` con `tool_name` y `tool_paths` correctos, pero el `session_id` registrado fue el de la sesión padre Neo (`pointy-goldfish`), no un id propio del subagente. Un segundo spike independiente en un proceso fresco confirmó que `write` y `mcp__chrome-browser__*` están **CONFIRMED ABSENT** para subagentes independientemente de su declaración en `allowed-tools`, mientras que `glob` sí está presente bajo el nombre `find_file_by_name`. El mecanismo más probable para la creación de un artefacto nuevo pese a `write` ausente es `exec` con redirección de shell.

### Lesson 28

Fase-0 (Oracle) probó `.devin/config.json` con `permissions.deny: ["Exec(git commit)","Exec(git push)"]` a nivel de proyecto y vio bloquear un commit real bajo `--permission-mode dangerous`. Fase-4 (Trinity), invocando `devin -p` sin REPL contra el mismo tipo de proyecto, encontró que esa misma regla de proyecto **no bloqueó** un commit real — pasó. El mecanismo que sí funcionó de forma reproducible (confirmado independientemente por Neo, dos corridas: una sin `--config` que comiteó, una con `--config` que bloqueó): generar un archivo de config temporal que fusiona el `~/.config/devin/config.json` real del usuario con las reglas `deny`, y pasarlo explícitamente con `--config <path>` en la invocación. La causa exacta de por qué `.devin/config.json` de proyecto no se carga de forma confiable bajo `-p` queda **sin resolver** — no se investigó a fondo el motivo (¿se resuelve el cwd distinto al pasar `-p` con `--config`? ¿hay algún orden de precedencia distinto en modo no-interactivo?), solo se confirmó el síntoma y el workaround. Ver `hardline-dispatch.sh` (`adapters/devin/`) para la implementación real.

### Lesson 29

El pedido era "que Neo arranque solo en modo workspace de Matrix". Primera respuesta descartada: `hooks/session_start_bootstrap.py` (Seraph) + `adapters/devin/session-start-hook.sh` + un `.devin/config.json` de proyecto nuevo registrando `hooks.SessionStart`. Funcionaba (confirmado con un spike real de `devin -p`), pero duplicaba `adapters/devin/hooks/session_audit.py`, que ya estaba wireado globalmente en `~/.config/devin/config.json` por `adapters/devin/install-hooks.sh` (instalado a mano en esta máquina, nunca por el flujo de `bin/matrix install --target=devin`) y que ya tenía un experimento llamado "Etapa G/H3" (`experiment.activation_inject` en `adapters/devin/config.yaml`, `false` desde que se escribió el 2026-07-17) para inyectar la misma clase de contenido vía `hookSpecificOutput.additionalContext`. La corrección real: se borraron los tres archivos nuevos; se agregó `_is_workspace_mode()` (compara `os.getcwd()` contra `MATRIX_ROOT`) y `_render_activation_preamble()` (renderiza `brain/data/activation-preamble.tmpl`, la misma plantilla que ya usa el `neo` skill generado y el bloque `AGENTS.local.md` de proyectos bindeados vía `matrix_block_tmp()` en `bin/matrix`) a `session_audit.py`; se prendió `activation_inject: true` acotado por ese chequeo de cwd; y se agregó la llamada a `install-hooks.sh` al final de `adapters/devin/install.sh`, que antes no la incluía.

### Lesson 34

El hook de ciclo de vida mencionado en la lección 34 es `Stop`; el CLI concreto al que aplica es **Devin CLI**. El detalle del bug y la batería de inyección de errores quedan en `brain/data/lessons.md` lección 34.

### Lesson 37

En Devin CLI, el archivo de estado local del proyecto es `.devin` (directorio `.devin/` en la raíz del proyecto). En `saintlukes`, el `.gitignore` del proyecto solo tenía `_brain`, `AGENTS.local.md` y `.devin`; faltaba `matrix-output/`, por lo que un artefacto de research escrito ahí corría riesgo real de ser trackeado en el repo del cliente.

**Nota post-`workspace-mode-refinements` (no reescribe el incidente, lo contextualiza):** el mecanismo que este incidente motivó ya no aplica de la misma forma. Desde la sesión que retiró `matrix-output/` (ver `AGENTS.md` §1), los artefactos de research/plan/architecture/eval de un proyecto bindeado ya no se escriben en ningún directorio dentro del propio repo del cliente — van a `brain/output/<project>/<sub>/` en este repo. Por eso `matrix select` ya no agrega `matrix-output/` al `.gitignore` del proyecto: no hace falta, porque nada se vuelve a escribir ahí. El riesgo real de `saintlukes` (un artefacto trackeado en el repo de un cliente) sigue siendo un incidente real que pasó; lo que cambió es la superficie que lo hacía posible, no el hecho de que haya ocurrido.

### Lesson 38

`sessions.db` (SQLite local del CLI) tuvo 2 incidentes de corrupción confirmados. Regla
operable: `sqlite3 ... ".dump"` puede cerrar en `ROLLBACK` en vez de `COMMIT` sin error
visible (exit 0, stderr vacío) — siempre revisar la última línea del dump antes de
reimportar. Diagnóstico completo (procedimiento de reparación, auditoría de filas
perdidas, causa raíz sin confirmar): `brain/output/research/devin-sessions-db-corruption-incidents.md`.

### Lesson 42

El hook de auditoría de sesión que implementa los mecanismos de detección de sesiones huérfanas es `adapters/devin/hooks/session_audit.py`, wireado globalmente en `~/.config/devin/config.json` por `adapters/devin/install-hooks.sh`.

### Lesson 51

Al retirar Keymaker del roster (2026-08-07), `adapters/devin/install.sh`'s `deploy()` regeneró e instaló correctamente los 10 artefactos vigentes en `~/.config/devin/agents/` y `~/.config/devin/skills/`, pero la carpeta `agents/keymaker/` (instalada en una corrida anterior) siguió existiendo intacta — `deploy()` itera sobre lo generado y sobreescribe/crea, nunca compara contra lo ya instalado para borrar lo que ya no tiene fuente; se borró a mano (`rm -rf`). Separado, se encontró un árbol de instalación completo `.agents/` (formato "thin pointer" viejo, con fecha 2026-06-15, distinto del formato actual con contenido inline) — deuda de una convención de wiring anterior a `skills/`+`agents/`, sin relación con el cambio de roster puntual; también se borró completo. Candidato real a mecanizar, no implementado esta sesión: que `install.sh` compare el directorio instalado contra el generado y pode las carpetas de specialists que ya no están en `brain/agents/*.md`, igual que ya hace `clean_broken_matrix_links` con symlinks rotos.

### Saint Luke's

La regla dura del usuario de `brain/data/lessons/saintlukes.md` surgió de una sesión con Devin CLI en la que el usuario compartía el working tree del proyecto `saintlukes` con ediciones manuales propias; dos cambios reales del usuario (`referrals/css/specifics.css` y el token `--t-tc--buttons--font--family` en `library__theme.css`) fueron revertidos por error al asumir que eran drift de un subagente.
