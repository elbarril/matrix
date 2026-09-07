# Matrix — Devin Adapter Notes

Devin CLI is the **only** host Matrix currently runs under; this file documents the Devin-specific binding. The brain ([`AGENTS.md`](AGENTS.md) + `brain/`) is CLI-agnostic; this adapter is the only one implemented today — Layer 3 (the Trainman).

## Prime directives

1. **Read [`AGENTS.md`](AGENTS.md) first.** It is the document of record for all agent behavior.
2. **The user talks only to Neo.** Specialists are reached through Neo's routing, never directly.
3. **Sacred foundation (Zion) is non-negotiable.** See `AGENTS.md` §4.
4. **State is files.** Managed by `bin/matrix`. Agents never mutate state files by hand.
5. **Reality decides.** Nothing is "done" without an E2E happy-path check (`validate_phase_close`).

## Capability → Devin tool mapping (the Trainman table)

The Devin adapter binds the brain's abstract capabilities:

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

Every generated `AGENT.md` also gets a Devin-native `allowed-tools:` grant from the same `capabilities:` list via the `allowed_tools:` map in `adapters/devin/adapter.yaml` — see "Least-privilege" below. Neo's `SKILL.md` deliberately has none.

The Trainman is a **two-step** flow for Devin:

```bash
bin/matrix build   --target=devin   # 1. generate artifacts → adapters/devin/generated/.agents/
bin/matrix install --target=devin   # 2. deploy them into Devin's global discovery path
```

- **build** renders thin-pointer artifacts from `brain/agents/*.md` into `adapters/devin/generated/` (gitignored, ephemeral). Each pointer references the brain by **absolute path**, so it resolves from any working directory.
- **install** *copies* those pointers (not symlinks) into Devin's global path; copies survive even if `generated/` is wiped because they point at the git-tracked brain by absolute path. Re-run both after changing an agent's `name`/`description` or the roster.

### Where the artifacts land (global discovery)

| Artifact | Global path | Effect |
|---|---|---|
| Neo (master) | `~/.config/devin/skills/neo/SKILL.md` | `/neo` and autonomous invocation in **every** project |
| Specialists | `~/.config/devin/agents/<name>/AGENT.md` | Subagent profiles available in **every** project |

Global install is deliberate: Neo must be reachable from any repo (Matrix, `clients/`, or unrelated). The installer also removes stale Matrix-owned symlinks left by older ad-hoc wiring (never touches non-Matrix entries).

## Model policy

Every generated `SKILL.md`/`AGENT.md` carries a `model:` frontmatter field, resolved at build time from the agent's `model_policy` tier (`cheap`/`reasoning`/`auto`, declared in `brain/agents/<name>.md`) through `adapters/devin/adapter.yaml`'s `model_policy` map (or a `model_template_*` preset when `--template=` is given). User priority = compute-unit consumption; every tier runs DeepSeek (or a low-cost SWE variant):

| Tier | Model | Used by | Why |
|---|---|---|---|
| `cheap` | `swe-1-7-medium` | Lock, Logos Sparks, Oracle | Mechanical/plumbing. Proven key (26 sessions). SWE-1.7's free preview ended ~2026-08-08; only confirmed free key today: `swe-1-6` (credit multiplier 0). |
| `reasoning` | `deepseek-v4-pro-high` | Architect, Morpheus, Smith | Planning/architecture/research/eval. Verified key (sessions.db 2026-09-04). History: `opus` → `sonnet` (2026-07-27) → `deepseek-v4-pro-high` (2026-09-05). |
| `auto` | `deepseek-v4-flash-high` | Neo, Trinity | Mixed workloads. Compute-priority default — also the global `agent.model` in `~/.config/devin/config.json`. Verified key (27 sessions). |

**Key syntax (2026-09-05):** DeepSeek keys are **lowercase with a reasoning-level suffix** — `deepseek-v4-flash-high`, `deepseek-v4-flash-max`, `deepseek-v4-pro-high`; bare `deepseek-V4-*` (wrong case, no suffix) does not resolve. Never observed: `swe-1-7-fast`, `swe-1-6-medium`; real fast tiers: `swe-1-6-fast` (0.5 credits), `swe-1-7-lightning` (6 credits, latency-focused). `swe-1.7` and `swe-1-7` normalize to the same canonical id (sessions.db) — dash vs. dot does not matter.

**Time-bound:** SWE-1.7's free preview ended ~2026-08-08 (date time-boxed, not re-verifiable live; consistent with the free tier being gone). Map + `model_template_*` presets (`gratis`/`barato`/`equilibrado`/`caro`/`veloz`) re-verified 2026-09-05 against sessions.db/`config.json`/CLI docs. Re-verify periodically (repeat `--model X -p "OK"` + sessions.db check, or watch `/model`'s selector), especially after any Devin upgrade — update the map if needed.

To move a tier: edit the `model_policy` map in `adapters/devin/adapter.yaml`, then rerun:

```bash
bin/matrix build   --target=devin
bin/matrix install --target=devin
```

No agent file changes — tier assignment is separate from its backing model.

## External MCP servers this brain assumes

| Server | Scope | Added | Used by |
|---|---|---|---|
| `chrome-browser` | user (`~/.config/devin/config.json`) | pre-existing | Smith (`browser` capability) |
| `context7` | user (`~/.config/devin/config.json`) | 2026-07-15, `devin mcp add context7 --url https://mcp.context7.com/mcp --scope user` | Oracle (`docs-lookup` capability) |

Both are **user-scope**, so they follow Neo/the specialists globally rather than needing per-project setup. Neither is required for the roster to function — the corresponding capability (`browser`, `docs-lookup`) is simply unavailable if the server isn't configured on a given machine, and the agent should say so rather than fake the check (Foundation 3). context7 works unauthenticated (rate-limited, verified live); running `devin mcp add ...` again prints an OAuth URL for higher rate limits — optional, not required.

## Least-privilege `allowed-tools`

Every specialist's generated `AGENT.md` carries an `allowed-tools:` list from its `capabilities:` via the `allowed_tools:` map in `adapters/devin/adapter.yaml` (categories: `read`, `edit`, `write`, `grep`, `glob`, `exec`, `mcp__server__tool` patterns). Re-measure: `sed -n '2,/^---$/p' adapters/devin/generated/.agents/agents/<name>/AGENT.md` vs. `diff` the installed copy. Current full-capability grant: `read, edit, write, grep, glob, exec, mcp__chrome-browser__*` (`edit`+`write` both appear because abstract `edit` maps to both — accepted widening; `smith.md` `<boundaries>` has the narrower intent).

Grant-resolution timing status: `brain/output/research/devin-tool-grant-resolution-timing.md`.

**Known fixes (one-line pointers):**
- `pre_exec_guard.py` token-match false-positive fix → `brain/output/eval/pre-exec-guard-false-positive-fix.md`.
- Logos-Sparks `run-command` removal + exec allowlist for subagents (`permissions.allow`/`PreToolUse` guard) → `brain/output/eval/devin-subagent-exec-hardening.md`.

Neo's `SKILL.md` deliberately has no `allowed-tools` (`run_subagent`/`ask_user_question` aren't nameable entries); blast radius is lower — foreground, user-approved, not an unattended subagent.

## Subagents can never ask the user directly

Devin withholds `ask_user_question` from every subagent unconditionally (not configurable via `allowed-tools`/`permissions`); specialists with `ask-user` run as subagents and report the question back to Neo to ask — mechanics: "ask-user withheld" below. `run_subagent`/`read_subagent` are likewise unavailable inside a subagent by default (nesting disabled beyond the root unless `max-nesting` is set; all core specialists are depth-1 children of Neo). **Nesting verified in vivo:** depth-1 subagent with `max-nesting: 2` spawned `subagent_explore`, read via `read_subagent(block=true)` → `brain/output/research/adapter-lessons-detail.md` §14.

## Federated ships and `max-nesting`

Ship captains (e.g. `logos-niobe`) get a `max-nesting` value derived by the Trainman from the manifest's `captain`/`crew` graph — mechanism below ("run-subagent in nestable artifacts"). For Logos: `logos-niobe` → `max-nesting: 2` (captain depth 1 from Neo, crew depth 2); `logos-ghost`/`logos-sparks` → no field. This lets Niobe call `run_subagent`/`read_subagent` directly on her crew. Formula verified only for depth 2; depth ≥3 (sub-captains) needs a spike first.

## Mapping to Devin's native structure

Master (Neo) → Devin Skill (`.agents/skills/neo/SKILL.md`); specialists → Devin Subagents (`.agents/agents/<name>/AGENT.md`), routed via `run_subagent` (incl. Matrix workspace mode); enforcement → portable `hooks/*.py` via `bin/matrix hooks <name>` or skill pre/post steps.

## Session hygiene

See [`AGENTS.md`](AGENTS.md) §12.

## Matrix workspace mode auto-bootstrap (AGENTS.md §6 step 0)

Reuses `adapters/devin/hooks/session_audit.py` + `experiment.activation_inject` (`lessons.md:35`).

- **Wiring.** `session_audit.py` wired to hooks `SessionStart`/`UserPromptSubmit`/`PostToolUse`/`PostCompaction`/`SessionEnd` in `~/.config/devin/config.json` by `adapters/devin/install-hooks.sh`; `install.sh` runs it last, so `bin/matrix install --target=devin` sets it up anywhere.
- **Injection.** `experiment.activation_inject: true` renders `brain/data/activation-preamble.tmpl` (same template as `matrix_block_tmp()` in `bin/matrix` and the generated `neo` SKILL.md) as `hookSpecificOutput.additionalContext` on `SessionStart`/`UserPromptSubmit`.
- **`{{ADAPTER_DOC_PATH}}`** → `DEVIN.md` via `binding.doc_path: "DEVIN.md"` in `adapters/devin/adapter.yaml`; the three surfaces (`matrix_block_tmp()`, `adapters/_build.py`, `session_audit.py`'s `_render_activation_preamble()`) all resolve it to an **absolute path**.
- **Scope.** `_activation_reinject_scope()` (B1-Option 1) applies to Matrix workspace mode **and** bound external projects (valid `_brain` symlink + managed `AGENTS.local.md`), via `bin/matrix scope` (wrapper over `resolve_scope()`), every `session_start`/`user_prompt_submit`.
- **Flag state.** `activation_inject` is `true` (was `false` since first built 2026-07-17, never turned on); affects both workspace mode and bound projects.

### `activation_inject_userprompt_full` (throttled since 2026-09-01, Camino 2 Q1-A)

Current value: **`false`** in `adapters/devin/config.yaml` — full preamble on turn 1, again roughly every 10 turns; sentinel preamble between.

- **Revert criterion.** Back to `true` only if (a) observed BLOCK ratio > 21% over ≥ 20 phase closes, **or** (b) a contract violation is traced to a throttled turn (the missing full preamble caused it).
- **Known gap.** No env-var kill-switch — only editing `adapters/devin/config.yaml` directly.

**Verified 2026-07-28**: model replied `OK` but `hook-audit.jsonl` shows reads of `AGENTS.md` then `neo.md` — audit log, not prose; re-verify on upgrade. → `brain/output/research/adapter-lessons-detail.md`.

## Hardening `permissions.deny` for secret stores

**Estado actual: DESHABILITADA** (decisión del usuario, 2026-09-07, incidente
`incident-secret-deny-overblock-tl0090`). `permissions.deny` en
`~/.config/devin/config.json` está vacío y el bloque `secret_deny` de
`adapters/devin/config.yaml` está en `enabled: false`. Para re-habilitar:
restaurar la config declarativa y correr `bin/matrix harden --target=devin --apply`.

Mecánica (válida si se re-habilita): `bin/matrix harden --target=devin`
reconcilia `permissions.deny` contra el bloque `secret_deny` de
`adapters/devin/config.yaml`. Dry-run por defecto; `--apply` escribe, `--revert`
elimina las entradas Matrix-managed. Solo toca `permissions.deny` y usa el
sidecar (`~/.config/devin/.matrix-managed-deny.json`) para respetar borrados
manuales. El `secret_deny.discover` escanea `$HOME` buscando carpetas
`credentials/` y archivos `.env`, emitiendo patrones `Read(...)` a nivel
directorio — nunca nombres de archivo de credenciales.

**Por qué se deshabilitó (semántica verificada 2026-09-07, Devin CLI 3000.6.14):**
`permissions.deny` con `Read(...)` no solo bloquea el tool `read`: bloquea
también `grep`/`glob` y los comandos `exec` que LEEN contenido con path literal
(`cat`, `ls`). NO bloquea predicados (`test -f`), `source`, ni indirección de
variable (`$HOME`). La lista over-broad (`~/.local/share/devin/**`) rompió la
lectura de la doc del propio CLI; la sesión en curso conserva el snapshot de
permisos hasta reiniciar. Workaround sancionado (aplicable si se re-habilita):
`test -f "$HOME/.avature/credentials/<host>.env"` para existencia,
`source "$HOME/.avature/credentials/<host>.env"` para cargar el token. El hook
`pre_tool_use_guard` bloquea con guía los verbos de volcado sobre rutas
denyadas (inactivo con deny vacía). Ver lección 65.

## Headless / non-interactive execution (`devin -p`)

`devin -p "<prompt>" [--permission-mode dangerous] [-r <session_id>]` runs one turn non-interactively and exits. **Exit code 0 ≠ success** — parse the printed text (refusals also exit 0). Full spike: `brain/output/research/devin-headless-execution.md`.

## Why enforcement is portable, not Devin-coupled

Enforcement = portable `hooks/*.py` (JSON in/out contract), fired by `bin/matrix hooks <name>`; the adapter only decides *when* to fire them. Same checks run unchanged under any future adapter — see `AGENTS.md` §8.

## Relocated from `brain/data/capability-map.md` (Phase 2, `validate_layer2` remediation)

Moved here wholesale from `capability-map.md` (no semantic change) so that file stays CLI-agnostic; this is the concrete companion naming Devin's real tool identifiers.

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

## Boot WARN channel (D-boot)

`pre_activation_check` now runs a `boot_warn` channel with six information-only emitters (`the_source`, `validate_layer2`, `validate_lessons`, `model_drift`, `ttl_expired`, `snapshot_due`). The channel never blocks activation and never writes to `errors`/`checks`; it populates `boot_warn.warns` in the JSON and the `additionalContext` reinjected on `session_start` when the session is in scope.

- `BOOT_WARN_ENABLED`/`MATRIX_BOOT_WARN`: `0`/`false`/`off` disables the channel.
- `BOOT_WARN_BUDGET_S`/`MATRIX_BOOT_WARN_BUDGET_S`: internal deadline, default `6.0`.
- `PRE_ACTIVATION_TIMEOUT_S`: external `session_audit` timeout raised to `20` s; an internal `pre_activation_check_status` of `timeout` is now distinguishable from `ok`/`failed`/`error`.

Two new manual mechanisms are supported by `bin/matrix link`:

```bash
bin/matrix link model:override <agent-or-skill-name> <model-name> until=YYYY-MM-DD
bin/matrix link ttl:path-decision-reform matrix until=YYYY-MM-DD motivo=fallback-A-C1
```

`model:override` suppresses `model_drift` for that artifact while active. `ttl:path-decision-reform` is the fallback-A TTL; if it expires with zero real `phase:path-decision` uses, `ttl_expired` warns.

## Shared-surface gate & writer lane (Q2-D)

El hook `PreToolUse` (`adapters/devin/hooks/pre_tool_use_guard.py`) ahora también cubre las tools nativas de edición (`edit`, `write`, `multi_edit`), pero **solo contra la superficie compartida del harness**: `AGENTS.md`, `DEVIN.md`, `brain/agents/*`, `brain/data/lessons.md`, `brain/data/capability-map.md`, `hooks/`, `bin/`, `adapters/`. Una sesión bound a un proyecto externo queda **bloqueada** para editar esa superficie — salvo la promoción proactiva de lessons, que solo permite `brain/data/lessons.md` (core) y `brain/data/lessons/<proyecto-actual>.md`, ambas bajo un lane de escritor per-file. Matrix workspace mode conserva acceso completo (también bajo lane).

- **Excepción / kill-switch:** relanzar la sesión con `MATRIX_SHARED_SURFACE_ALLOW=1` (o `true`) para bypassar el bloqueo de modo-bound durante toda la sesión (solo emergencias; la decisión queda auditada). El kill-switch NO bypassa el lane.
- **Lane de escritor:** `brain/state/lanes/<sha1(rel_path)[:16]>.json` — adquirido en `PreToolUse`, liberado en `PostToolUse`/`SessionEnd`, reclamado tras `MATRIX_WRITER_LANE_TTL_S` (default `120`). Un lane tomado bloquea el edit y loguea `bin/matrix link incident:writer-collision`.
- **Wireado:** `adapters/devin/install-hooks.sh` registra matchers `PreToolUse` para `edit`/`write`/`multi_edit` → `pre_tool_use_guard.py`. Re-correr `bin/matrix install --target=devin` tras este cambio.

## Lessons — detalle de adapter

Narrativa por-lección (citas, versiones, IDs, nombres de tools) en `brain/output/research/adapter-lessons-detail.md`. `lessons.md` conserva la regla operable + puntero.
