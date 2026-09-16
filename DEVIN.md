# Matrix — Devin Adapter Notes

Devin CLI is the **only** host Matrix currently runs under; this file documents the Devin-specific binding. The brain ([`AGENTS.md`](AGENTS.md) + `brain/`) is CLI-agnostic; this adapter is the only one implemented today — Layer 3 (the Trainman).

## Prime directives

Prime directives: AGENTS.md §1-§4 + §8 are the contract. AGENTS.md carries one canonical CLI mention (the current Devin binding, §1); all other Devin-specific material lives in this file. #1 Read AGENTS.md first.

## Capability → Devin tool mapping (the Trainman table)

Pointer: the source is `adapters/devin/adapter.yaml`, transcribed in "The live `adapter.yaml` binding" below; it is not duplicated in a manual table.

Every generated `AGENT.md` also gets a Devin-native `allowed-tools:` grant from the same `capabilities:` list via the `allowed_tools:` map in `adapters/devin/adapter.yaml` — see "Least-privilege" below.

The Trainman is a **two-step** flow for Devin:

```bash
bin/matrix build   --target=devin   # 1. generate artifacts → adapters/devin/generated/.agents/
bin/matrix install --target=devin   # 2. deploy them into Devin's global discovery path
```

- **build** renders thin-pointer artifacts from `brain/agents/*.md` into `adapters/devin/generated/` (gitignored, ephemeral). Each pointer references the brain by **absolute path**, so it resolves from any working directory.
- **install** *copies* those pointers (not symlinks) into Devin's global path; copies survive even if `generated/` is wiped because they point at the git-tracked brain by absolute path. Re-run both after changing an agent's `name`/`description` or the roster.

### Where the artifacts land (global discovery)

| Artifact | Global path | Effect |
| --- | --- | --- |
| Neo (master) | `~/.config/devin/skills/neo/SKILL.md` | `/neo` and autonomous invocation in **every** project |
| Specialists | `~/.config/devin/agents/<name>/AGENT.md` | Subagent profiles available in **every** project |

Global install is deliberate: Neo must be reachable from any repo (Matrix, `clients/`, or unrelated). The installer also prunes stale Matrix-owned legacy symlinks (never touches non-Matrix entries).

**Native mapping:** Master → Devin Skill (`SKILL.md`), specialists → Devin Subagents (`AGENT.md`), routed via `run_subagent` (incl. Matrix workspace mode); enforcement → portable `hooks/*.py` via `bin/matrix hooks <name>` or skill pre/post steps.

## Model policy

Every generated `SKILL.md`/`AGENT.md` carries a `model:` frontmatter field, resolved at build time from the agent's `model_policy` tier (`cheap`/`reasoning`/`auto`, declared in `brain/agents/<name>.md`) through `adapters/devin/adapter.yaml`'s `model_policy` map (or a `model_template_*` preset when `--template=` is given). User priority = compute-unit consumption; every tier runs DeepSeek (or a low-cost SWE variant):

| Tier | Model | Used by | Why |
| --- | --- | --- | --- |
| `cheap` | `swe-1-7-medium` | Lock, Logos Sparks | Mechanical/plumbing. Proven key (26 sessions). `cheap` means low-cost, not free; the free key is `swe-1-6` (credit multiplier 0), used by the `gratis` template. The default `equilibrado`/fallback keeps `swe-1-7-medium` as cheap-but-paid. |
| `reasoning` | `deepseek-v4-pro-high` | Architect, Morpheus | Planning/architecture/research/eval. Verified key (sessions.db 2026-09-04). History: `opus` → `sonnet` (2026-07-27) → `deepseek-v4-pro-high` (2026-09-05). |
| `auto` | `deepseek-v4-flash-high` | Neo, Trinity, Smith, Oracle | Mixed workloads. Compute-priority default — also the global `agent.model` in `~/.config/devin/config.json`. Verified key (27 sessions). |

**Key syntax (2026-09-05):** DeepSeek keys are **lowercase with a reasoning-level suffix** — `deepseek-v4-flash-high`, `deepseek-v4-flash-max`, `deepseek-v4-pro-high`; bare `deepseek-V4-*` (wrong case, no suffix) does not resolve. Never observed: `swe-1-7-fast`, `swe-1-6-medium`; real fast tiers: `swe-1-6-fast` (0.5 credits), `swe-1-7-lightning` (6 credits, latency-focused). `swe-1.7` and `swe-1-7` normalize to the same canonical id (sessions.db) — dash vs. dot does not matter.

**Time-bound:** SWE-1.7's free preview ended ~2026-08-08 (date time-boxed, not re-verifiable live; consistent with the free tier being gone). Map + `model_template_*` presets (`gratis`/`barato`/`equilibrado`/`caro`/`veloz`) re-verified 2026-09-05 against sessions.db/`config.json`/CLI docs. Re-verify periodically after any Devin upgrade.

To move a tier: edit the `model_policy` map in `adapters/devin/adapter.yaml`, then rerun:

```bash
bin/matrix build   --target=devin
bin/matrix install --target=devin
```

No agent file changes — tier assignment is separate from its backing model.

## External MCP servers this brain assumes

| Capability | Server | Devin binding | Scope | Added | Used by |
| --- | --- | --- | --- | --- | --- |
| `browser` | `chrome-browser` | `mcp__chrome-browser` | user (`~/.config/devin/config.json`) | pre-existing | Smith |
| `docs-lookup` | `context7` | `mcp__context7` | user (`~/.config/devin/config.json`) | 2026-07-15, `devin mcp add context7 --url https://mcp.context7.com/mcp --scope user` | Oracle |

Both are **user-scope**, so they follow Neo/the specialists globally rather than needing per-project setup. Neither is required for the roster: the capability is simply unavailable if the server isn't configured, and the agent should say so (Foundation 3). context7 works unauthenticated (rate-limited, verified live).

**Binding note:** `mcp__<server>__<tool>` is Devin's MCP naming convention, not a capability-map concept — another adapter's binding would use its own MCP (or non-MCP) convention.

## Least-privilege `allowed-tools`

Every specialist's generated `AGENT.md` carries an `allowed-tools:` list from its `capabilities:` via the `allowed_tools:` map in `adapters/devin/adapter.yaml` (categories: `read`, `edit`, `write`, `grep`, `glob`, `exec`, `mcp__server__tool` patterns). Re-measure: `sed -n '2,/^---$/p' adapters/devin/generated/.agents/agents/<name>/AGENT.md` vs. `diff` the installed copy. Current full-capability grant: `read, edit, write, grep, glob, exec, mcp__chrome-browser__*` (`edit`+`write` both appear because abstract `edit` maps to both — accepted widening; `smith.md` `<boundaries>` has the narrower intent).

Grant-resolution timing status: `brain/output/research/devin-tool-grant-resolution-timing.md`.

**Known fixes (one-line pointers):**

- `pre_exec_guard.py` token-match false-positive fix → `brain/output/eval/pre-exec-guard-false-positive-fix.md`.
- Logos-Sparks `run-command` removal + exec allowlist for subagents (`permissions.allow`/`PreToolUse` guard) → `brain/output/eval/devin-subagent-exec-hardening.md`.

Neo's `SKILL.md` deliberately has no `allowed-tools` (`run_subagent`/`ask_user_question` aren't nameable entries).

## Subagents can never ask the user directly

Pointer: full mechanism (unconditional withholding + bounce-to-Neo) in "`ask-user` withheld from every subagent (mechanics)" below.

**User-only restriction (observed runtime):** the host's saved sessions carry a system-level restriction — "Do not use subagents unless the user explicitly asks you to." (first observed 2026-09-03 14:01:28 UTC). Host runtime behavior, not a user request, Matrix update, or model change. Ask the user explicitly once before delegating; never override the host.

## Federated ships and `max-nesting`

Pointer: full `max-nesting` mechanism (formula `depth_from_root + subtree_depth`, Logos example) in "`run-subagent` in nestable artifacts (the `max-nesting` mechanism)" below.

## Session hygiene

See [`AGENTS.md`](AGENTS.md) §11.

## Matrix workspace mode auto-bootstrap (AGENTS.md §6 step 0)

Reuses `adapters/devin/hooks/session_audit.py` + the `activation.reinject` flag (`hooks/_flags.py`).

- **Wiring.** `session_audit.py` wired to `SessionStart`/`UserPromptSubmit`/`PostToolUse`/`PostCompaction`/`SessionEnd` in `~/.config/devin/config.json` by `adapters/devin/install-hooks.sh`.
- **Injection.** `activation.reinject: true` (via `adapters/devin/config.yaml#flags`) renders `brain/data/activation-preamble.tmpl` (same source as `matrix_block_tmp()` in `bin/matrix` and the generated `neo` SKILL.md) as `hookSpecificOutput.additionalContext` in `SessionStart`/`UserPromptSubmit`.
- **`{{ADAPTER_DOC_PATH}}`** → `DEVIN.md` (`binding.doc_path` in `adapters/devin/adapter.yaml`); all three surfaces (`matrix_block_tmp()`, `adapters/_build.py`, `session_audit.py`'s `_render_activation_preamble()`) resolve it to an **absolute** path.
- **Scope.** `_activation_reinject_scope()` (B1-Option 1) applies in workspace mode and in registry-resolved projects, on every `session_start`/`user_prompt_submit`, via `bin/matrix scope` (wrapper around `resolve_scope()`).
- **Flag state.** See `bin/matrix flags` for the effective value of `activation.reinject`; it affects both workspace mode and project sessions.

### `activation.reinject_full` (throttled since 2026-09-01, Camino 2 Q1-A)

Current value: **`false`** in `adapters/devin/config.yaml#flags` (it absorbs the legacy `experiment.activation_inject_userprompt_full`) — full preamble on turn 1, again roughly every 10 turns; sentinel preamble between.

- **Revert criterion.** Back to `true` only if (a) observed BLOCK ratio > 21% over ≥ 20 phase closes, **or** (b) a contract violation is traced to a throttled turn (the missing full preamble caused it).
- **Known gap.** No env-var kill-switch — only editing `adapters/devin/config.yaml` directly.

**Verified 2026-07-28**: `hook-audit.jsonl` shows reads of `AGENTS.md` then `neo.md`; re-verify on upgrade → `brain/output/research/adapter-lessons-detail.md`.

## Hardening `permissions.deny` for secret stores

**Current status: DISABLED** (user decision, 2026-09-07, incident
`incident-secret-deny-overblock-tl0090`). `permissions.deny` in
`~/.config/devin/config.json` is empty and the `secret_deny` block of
`adapters/devin/config.yaml` is set to `enabled: false`. State of the three
flags required by `the_source`'s `config_flags_missing` check (all in their
post-deny-list-off 2026-09-07 state): `class_b_repo_secrets` (`enabled: false`,
`patterns: []`), `static: []` and `exclude: []`. To re-enable: restore the
declarative config and run `bin/matrix harden --target=devin --apply`.

Mechanics (valid if re-enabled): `bin/matrix harden --target=devin`
reconciles `permissions.deny` against the `secret_deny` block of
`adapters/devin/config.yaml`. Dry-run by default; `--apply` writes, `--revert`
removes the Matrix-managed entries. It only touches `permissions.deny` and uses
the sidecar (`~/.config/devin/.matrix-managed-deny.json`) to respect manual
deletions. `secret_deny.discover` scans `$HOME` for `credentials/` folders and
`.env` files, emitting directory-level `Read(...)` patterns — never credential
file names.

**Why it was disabled (semantics verified 2026-09-07, Devin CLI 3000.6.14):**
`permissions.deny` with `Read(...)` does not only block the `read` tool: it also
blocks `grep`/`glob` and `exec` commands that READ content with a literal path
(`cat`, `ls`). It does NOT block predicates (`test -f`), `source`, or variable
indirection (`$HOME`). The over-broad list (`~/.local/share/devin/**`) broke
reading the CLI's own docs; the running session keeps its permission snapshot
until restart. Sanctioned workaround (applicable if re-enabled):
`test -f "$HOME/.avature/credentials/<host>.env"` for existence,
`source "$HOME/.avature/credentials/<host>.env"` to load the token. The
`pre_tool_use_guard` hook blocks dump verbs on denied paths with guidance
(inactive with an empty deny list). See lesson 65.

## Headless / non-interactive execution (`devin -p`)

`devin -p "<prompt>" [--permission-mode dangerous] [-r <session_id>]` runs one turn non-interactively and exits. **Exit code 0 ≠ success** — parse the printed text (refusals also exit 0). Full spike: `brain/output/research/devin-headless-execution.md`.

## Why enforcement is portable, not Devin-coupled

Enforcement = portable `hooks/*.py` (JSON in/out contract), fired by `bin/matrix hooks <name>`; the adapter only decides *when* to fire them. Same checks run unchanged under any future adapter — see `AGENTS.md` §8.

## Relocated from `brain/data/capability-map.md` (Phase 2, `validate_layer2` remediation)

Concrete companion naming Devin's real tool identifiers; the brain stays CLI-agnostic.

### The live `adapter.yaml` binding (concrete, not illustrative)

```yaml
# adapters/devin/adapter.yaml
capabilities:
  read: read_file
  edit: [edit, multi_edit, write]
  search: [grep_search, find_by_name]
  code-nav: codebase_search        # fallback: grep_search
  run-subagent: run_subagent
  run-command: run_command
  ask-user: ask_user_question
  browser: mcp__chrome-browser     # visual QA; no-op if unconfigured. Re-verified 2026-09-16: chrome-browser MCP tools are present.
  docs-lookup: mcp__context7       # version-pinned library docs
render:
  master: skill        # → .agents/skills/<name>/SKILL.md
  specialist: subagent # → .agents/agents/<name>/AGENT.md
```

This block is the `capabilities:` map (abstract capability → concrete tool id). A **separate** `allowed_tools:` map in the same `adapter.yaml` translates capabilities into Devin's *allowlist categories* (`read`, `grep`, `glob`, `exec`, `mcp__server__tool` patterns) — see "Least-privilege" above. The two maps use different nomenclatures on purpose.

### `run-subagent` in nestable artifacts (the `max-nesting` mechanism)

Under Devin, `run_subagent`/`read_subagent` are disabled inside a subagent by default (all core specialists are depth-1 children of Neo). They become available when the subagent profile carries a `max-nesting` frontmatter field whose value is at least the depth of the children it needs to spawn. The Trainman derives this value from the ship manifest's `captain`/`crew` graph — `depth_from_root + subtree_depth` — and injects it **only** into the captain's artifact. Crew leaves do not carry the field, because they have no subordinates to spawn. This is the Devin representation of the abstract `run-subagent` capability; it is not an `allowed-tools` grant. For Logos: `logos-niobe` → `max-nesting: 2` (captain depth 1 from Neo, crew depth 2); `logos-ghost`/`logos-sparks` → no field — Niobe calls `run_subagent`/`read_subagent` directly on her crew. **Formula verified only for depth 2; depth ≥3 (sub-captains) needs a spike first.** **Nesting verified in vivo:** depth-1 subagent with `max-nesting: 2` spawned `subagent_explore`, read via `read_subagent(block=true)` → `brain/output/research/adapter-lessons-detail.md` §14.

### `ask-user` withheld from every subagent (mechanics)

Devin **never** allows a subagent to call `ask_user_question` — it is withheld from every subagent unconditionally, regardless of `allowed-tools` or permissions (platform rule, not configurable). Several specialists (Architect, Morpheus, Oracle, Trinity) declare the `ask-user` capability in the agnostic brain, but under the Devin adapter they run as **subagents** (`.agents/agents/<name>/AGENT.md`), so they cannot exercise it directly.

Resolution for the Devin adapter: a specialist that needs to ask the user stops and returns the question to **Neo** (the master skill — not a subagent, so it retains `ask_user_question`) instead of calling it itself. Neo relays the question, gets the answer, and re-delegates. This is a Devin-adapter concern only; the brain's `ask-user` capability declaration does not change, because another CLI's adapter may not have this restriction.

### Model policy → Devin frontmatter (mechanics)

The Trainman resolves each agent's `model_policy` tier (`cheap`/`reasoning`/`auto`) through the adapter's `model_policy` map and writes the result as `model: <name>` in the generated `SKILL.md`/`AGENT.md` frontmatter (see `extensibility/skills` and `subagents` in the Devin CLI docs — both support a `model` override field). Re-run `bin/matrix build --target=devin && bin/matrix install --target=devin` after changing `adapters/devin/adapter.yaml`'s `model_policy` map for the change to take effect globally.

## Boot WARN channel (D-boot)

`pre_activation_check` now runs a `boot_warn` channel with seven information-only emitters (`surface_budget`, `the_source`, `validate_layer2`, `validate_lessons`, `model_drift`, `ttl_expired`, `snapshot_due`). The channel never blocks activation and never writes to `errors`/`checks`; it populates `boot_warn.warns` in the JSON and the `additionalContext` reinjected on `session_start` when the session is in scope.

- `surface_budget` token: size budget for the shared document surface (`AGENTS.md` warn 15,500 B / fail 16,200 B; `DEVIN.md` warn 20 KiB / fail 24 KiB; `brain/agents/neo.md` warn 18 KiB / fail 22 KiB). `ok:false` only if a surface exceeds its `fail`; a `warn` state never flips `ok` and never feeds the hook's global `ok`. Fix: slim the offending doc. Raising a threshold is the full-chain case, not a routine fix.
- `BOOT_WARN_ENABLED`/`MATRIX_BOOT_WARN`: legacy aliases of `hooks.boot_warn` (deprecated).
- `BOOT_WARN_BUDGET_S`/`MATRIX_BOOT_WARN_BUDGET_S`: internal deadline, default `6.0`.
- The `session_audit` pre-check timeout is hardcoded at 20 s; a `pre_activation_check_status` of `timeout` is distinguishable from `ok`/`failed`/`error`.

Two new manual mechanisms are supported by `bin/matrix link`:

```bash
bin/matrix link model:override <agent-or-skill-name> <model-name> until=YYYY-MM-DD
bin/matrix link ttl:path-decision-reform matrix until=YYYY-MM-DD motivo=fallback-A-C1
```

`model:override` suppresses `model_drift` for that artifact while active. `ttl:path-decision-reform` is the fallback-A TTL; if it expires with zero real `phase:path-decision` uses, `ttl_expired` warns.

## Shared-surface gate & writer lane (Q2-D)

The `PreToolUse` hook (`adapters/devin/hooks/pre_tool_use_guard.py`) now also covers the native edit tools (`edit`, `write`, `multi_edit`), but **only against the harness's shared surface**: `AGENTS.md`, `DEVIN.md`, `brain/agents/*`, `brain/data/lessons.md`, `brain/data/capability-map.md`, `hooks/`, `bin/`, `adapters/`. A `project` session (cwd in a registry-resolved project) is **blocked** from editing that surface — except the proactive lessons promotion, which only allows `brain/data/lessons.md` (core) and `brain/data/lessons/<current-project>.md` (subject = innermost), both under a per-file writer lane. Matrix workspace mode keeps full access (also under the lane). The flags `gate.shared_surface` and `gate.writer_lane` (default on) gate the isolation and the lane; `gate.pre_exec_guard` gates the shell-command guard.

- **Exception / kill-switch:** relaunch the session with `MATRIX_SHARED_SURFACE_ALLOW=1` (or `true`) to bypass the `project` session block for the whole session (emergencies only; the decision stays audited). The kill-switch does NOT bypass the lane.
- **Writer lane:** `brain/state/lanes/<sha1(rel_path)[:16]>.json` — acquired on `PreToolUse`, released on `PostToolUse`/`SessionEnd`, reclaimed after `MATRIX_WRITER_LANE_TTL_S` (default `120`). A held lane blocks the edit and logs `bin/matrix link incident:writer-collision`.
- **Wiring:** `adapters/devin/install-hooks.sh` registers `PreToolUse` matchers for `edit`/`write`/`multi_edit` → `pre_tool_use_guard.py`. Re-run `bin/matrix install --target=devin` after this change.

## Feature flags (Devin adapter)

`hooks/_flags.py` is the single loader (precedence: env `MATRIX_<NAME>` > `adapters/devin/config.yaml#flags` > `brain/config.yaml#flags` > DEFAULTS). `bin/matrix flags` shows the effective value, source, risk and state; `flags --validate` exits 1 if there are `dangerous`/`inert` flags.

The 12 flags: `activation.reinject`, `activation.reinject_full`, `gate.shared_surface`, `gate.writer_lane`, `gate.pre_exec_guard`, `gate.secret_deny`, `hooks.pre_activation_check`, `hooks.boot_warn`, `hooks.session_extras`, `memory.tree`, `views.scoped`, `binding.artifacts`. Effective state: see `bin/matrix flags` — the values in this doc are not the current state.

`hooks.session_extras` (default `false`) is the umbrella switch for the **non-audit** extras of `session_audit.py`: orphan-session detection, `link flags:state`, periodic `validate_routing_signal` (every 20 tools) and the `phase_close` nudge. Off = only the audit trail (`audit_event`) + `pre_activation_check` (its own flag) + `session close` on SessionEnd run.

Legacy env: `MATRIX_INJECT_ACTIVATION`→`activation.reinject`; `BOOT_WARN_ENABLED`/`MATRIX_BOOT_WARN`→`hooks.boot_warn`. `gate.secret_deny` defaults off; to re-enable: flag on + `bin/matrix harden --target=devin --apply` (sidecar `~/.config/devin/.matrix-managed-deny.json`). The numeric TTLs (`MATRIX_WRITER_LANE_TTL_S`, `BOOT_WARN_BUDGET_S`/`MATRIX_BOOT_WARN_BUDGET_S`) are NOT flags.

## Lessons — adapter detail

Per-lesson narrative (citations, versions, IDs, tool names) in `brain/output/research/adapter-lessons-detail.md`. `lessons.md` keeps the operable rule + pointer.
