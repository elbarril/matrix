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
| `cheap` | `swe-1-7-medium` | Keymaker, Lock, Logos Sparks | Gratis hoy durante su beta; apto para trabajo mecánico/plumbing. La fecha exacta de cierre de su free preview no es re-verificable hoy en una fuente viva. |
| `reasoning` | `opus` (Claude Opus 5) | Architect, Morpheus, Oracle, Smith | `opus` es un alias flotante: la documentación de Devin confirma explícitamente que sigue la versión más reciente de la familia Claude Opus. Devin también lo recomienda, junto con `gpt`, para deep reasoning/architecture/research/evaluation. Real cost hoy: $5/$25 per MTok, 1M context. |
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

Every specialist's generated `AGENT.md` carries an `allowed-tools:` list, resolved from its `capabilities:` frontmatter through the `allowed_tools:` map in `adapters/devin/adapter.yaml` (categories: `read`, `edit`, `grep`, `glob`, `exec`, plus `mcp__server__tool` patterns — the actual Devin frontmatter vocabulary, distinct from the tool-call names in the `capabilities:` map above). Verified end-to-end: a restricted `keymaker` subagent (only `read`+`exec`) successfully ran `git status`/`git log`; a restricted `smith` subagent (adds `mcp__chrome-browser__*`) successfully read and grepped its own brain file; a restricted `oracle` subagent (adds `mcp__context7__*`) successfully resolved a library id and queried its docs through context7.

Neo's `SKILL.md` is the one exception — deliberately left with no `allowed-tools`. Neo needs `run_subagent` and `ask_user_question`, and neither is a nameable `allowed-tools` entry (see below), so restricting Neo's list to the nameable categories risks silently dropping tools that were never in scope to restrict in the first place. The blast radius of an unrestricted Neo is also lower in practice: it runs in the foreground, user-approved, not as an unattended subagent.

## Subagents can never ask the user directly

Devin withholds `ask_user_question` from every subagent unconditionally — not configurable via `allowed-tools` or `permissions`. Specialists that declare the `ask-user` capability (Architect, Keymaker, Morpheus, Oracle, Trinity) run as Devin subagents, so they cannot call it. When one of them needs a decision from the user, it stops and reports the question back to Neo (the master skill, not a subagent — it keeps `ask_user_question`), which asks and re-delegates. `run_subagent`/`read_subagent` are similarly unavailable inside a subagent by default (nesting is disabled beyond the root agent unless `max-nesting` is set — none of our core specialists need it, they're all depth-1 children of Neo).

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

## Why enforcement is portable, not Devin-coupled

Enforcement lives in `hooks/*.py` with a JSON in/out contract, fired by `bin/matrix hooks <name>`. The logic travels with the brain, not with Devin — so the exact same checks would run unchanged under a future CLI adapter, if one is ever built. The adapter only decides *when* to fire them.
