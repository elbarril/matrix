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
| `cheap` | `swe-1-7-medium` | Lock, Logos Sparks, Oracle | Gratis hoy durante su beta; apto para trabajo mecánico/plumbing. Oracle añadido en C3 Opción A: su investigación es mayoritariamente recolección mecánica de evidencia (búsquedas, lecturas, docs-lookup); riesgo bajo porque Oracle nunca gatea — solo informa — y sus propios criterios de confianza actúan como red de seguridad (ver propuesta C3 §4/§5). La fecha exacta de cierre de su free preview no es re-verificable hoy en una fuente viva. |
| `reasoning` | `sonnet` (Claude Sonnet 5) | Architect, Morpheus, Smith | Cambiado de `opus` a `sonnet` (2026-07-27, decisión explícita del usuario: velocidad/costo sobre calidad máxima). Anthropic posiciona Sonnet 5 como "broadly comparable to Opus 4.8... while being faster and cheaper"; brecha de benchmark medida y chica (SWE-bench Verified 85.2% vs 88.6% de Opus). Real cost hoy: $2/$10 per MTok (introductorio hasta 2026-08-31, luego $3/$15) vs $5/$25 de Opus — ~60% más barato. |
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

Grant-resolution timing status: `brain/output/research/devin-tool-grant-resolution-timing.md`.

**Known fixes (one-line pointers):**
- `pre_exec_guard.py` token-match false-positive fix → `brain/output/eval/pre-exec-guard-false-positive-fix.md`.
- Logos-Sparks `run-command` capability removal + exec allowlist for subagents (`permissions.allow` /
  `PreToolUse` guard) → `brain/output/eval/devin-subagent-exec-hardening.md`.

Neo's `SKILL.md` is deliberately left without `allowed-tools` (needs `run_subagent`/`ask_user_question`,
neither is a nameable `allowed-tools` entry). The blast radius of an unrestricted Neo is also lower
in practice: it runs in the foreground, user-approved, not as an unattended subagent.

## Subagents can never ask the user directly

Devin withholds `ask_user_question` from every subagent unconditionally — not configurable via `allowed-tools` or `permissions`. Specialists that declare the `ask-user` capability (Architect, Morpheus, Oracle, Trinity) run as Devin subagents, so they cannot call it. When one of them needs a decision from the user, it stops and reports the question back to Neo (the master skill, not a subagent — it keeps `ask_user_question`), which asks and re-delegates. `run_subagent`/`read_subagent` are similarly unavailable inside a subagent by default (nesting is disabled beyond the root agent unless `max-nesting` is set — none of our core specialists need it, they're all depth-1 children of Neo).

**Nesting verified in vivo:** depth-1 subagent with `max-nesting: 2` spawned `subagent_explore` and read via `read_subagent(block=true)` — details → `brain/output/research/adapter-lessons-detail.md` §14.

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

AGENTS.md §6 step 0: Neo must activate in Matrix workspace mode without relying
on topic-matching alone. **Reuses `adapters/devin/hooks/session_audit.py` and its
`experiment.activation_inject` flag.** See `lessons.md:35`.

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

**Activation injection verified 2026-07-28**: model replied only `OK`, but `hook-audit.jsonl` shows it read `AGENTS.md` then `neo.md`. Check audit log, not prose; re-verify on upgrade. → `brain/output/research/adapter-lessons-detail.md`.

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

Narrativa por-lección (citas, versiones, IDs, nombres de tools) en `brain/output/research/adapter-lessons-detail.md`. `lessons.md` conserva la regla operable + puntero.
