# Matrix — Devin Adapter Notes

Devin CLI is the **only** host Matrix currently runs under; this file documents the Devin-specific binding (Layer 3, the Trainman). The brain ([`AGENTS.md`](AGENTS.md) + `brain/`) is CLI-agnostic.

## Prime directives

AGENTS.md §1-§4 + §8 are the contract. AGENTS.md carries one canonical CLI mention (the current Devin binding, §1); all other Devin-specific material lives here. #1 Read AGENTS.md first.

## Capability → Devin tool mapping (the Trainman table)

Source: `adapters/devin/adapter.yaml`, transcribed in "The live `adapter.yaml` binding" below. Every generated `AGENT.md` also gets a Devin-native `allowed-tools:` grant from the same `capabilities:` list via the `allowed_tools:` map — see "Least-privilege" below.

The Trainman is a **two-step** flow:

```bash
bin/matrix build   --target=devin   # 1. generate artifacts → adapters/devin/generated/.agents/
bin/matrix install --target=devin   # 2. deploy them into Devin's global discovery path
```

- **build** renders thin-pointer artifacts from `brain/agents/*.md` into `adapters/devin/generated/` (gitignored, ephemeral). Each pointer references the brain by **absolute path**, so it resolves from any working directory.
- **install** *copies* those pointers (not symlinks) into Devin's global path; copies survive even if `generated/` is wiped because they point at the git-tracked brain. Re-run both after changing an agent's `name`/`description` or the roster.

### Where the artifacts land (global discovery)

| Artifact | Global path | Effect |
| --- | --- | --- |
| Neo (master) | `~/.config/devin/skills/neo/SKILL.md` | `/neo` and autonomous invocation in **every** project |
| Specialists | `~/.config/devin/agents/<name>/AGENT.md` | Subagent profiles available in **every** project |

Global install is deliberate: Neo must be reachable from any repo. The installer also prunes stale Matrix-owned legacy symlinks (never touches non-Matrix entries).

**Native mapping:** Master → Devin Skill (`SKILL.md`), specialists → Devin Subagents (`AGENT.md`), routed via `run_subagent` (incl. Matrix workspace mode); enforcement → portable `hooks/*.py` via `bin/matrix hooks <name>`.

## Model policy

Every generated `SKILL.md`/`AGENT.md` carries a `model:` frontmatter field, resolved at build time from the agent's `model_policy` tier (`cheap`/`reasoning`/`auto`, declared in `brain/agents/<name>.md`) through `adapters/devin/adapter.yaml`'s `model_policy` map (or a `model_template_*` preset when `--template=` is given). User priority = compute-unit consumption; every tier runs DeepSeek (or a low-cost SWE variant):

| Tier | Model | Used by | Why |
| --- | --- | --- | --- |
| `cheap` | `swe-1-7-medium` | Lock, Logos Sparks | Mechanical/plumbing. Proven key (26 sessions). The free key is `swe-1-6` (credit multiplier 0), used by the `gratis` template; the default `equilibrado`/fallback keeps `swe-1-7-medium` as cheap-but-paid. |
| `reasoning` | `deepseek-v4-pro-high` | Architect, Morpheus | Planning/architecture/research/eval. Verified key. |
| `auto` | `deepseek-v4-flash-high` | Neo, Trinity, Smith, Oracle | Mixed workloads. Compute-priority default — also the global `agent.model` in `~/.config/devin/config.json`. Verified key. |

**Key syntax (2026-09-05):** DeepSeek keys are **lowercase with a reasoning-level suffix** — `deepseek-v4-flash-high`, `deepseek-v4-flash-max`, `deepseek-v4-pro-high`; bare `deepseek-V4-*` (wrong case, no suffix) does not resolve. Real fast tiers: `swe-1-6-fast` (0.5 credits), `swe-1-7-lightning` (6 credits). `swe-1.7` and `swe-1-7` normalize to the same canonical id. Map + `model_template_*` presets re-verified 2026-09-05; re-verify periodically after any Devin upgrade.

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
| `docs-lookup` | `context7` | `mcp__context7` | user (`~/.config/devin/config.json`) | 2026-07-15 | Oracle |

Both are **user-scope**, so they follow Neo/the specialists globally rather than needing per-project setup. Neither is required: the capability is simply unavailable if the server isn't configured, and the agent should say so (Foundation 3). context7 works unauthenticated (rate-limited, verified live).

**Binding note:** `mcp__<server>__<tool>` is Devin's MCP naming convention, not a capability-map concept.

## Least-privilege `allowed-tools`

Every specialist's generated `AGENT.md` carries an `allowed-tools:` list from its `capabilities:` via the `allowed_tools:` map in `adapters/devin/adapter.yaml` (categories: `read`, `edit`, `write`, `grep`, `glob`, `exec`, `mcp__server__tool` patterns). Re-measure: `sed -n '2,/^---$/p' adapters/devin/generated/.agents/agents/<name>/AGENT.md` vs. `diff` the installed copy. Current full-capability grant: `read, edit, write, grep, glob, exec, mcp__chrome-browser__*` (`edit`+`write` both appear because abstract `edit` maps to both — accepted widening).

Grant-resolution timing status: `brain/output/research/devin-tool-grant-resolution-timing.md`.

**Known fixes (one-line pointers):**

- `pre_exec_guard.py` token-match false-positive fix → `brain/output/eval/pre-exec-guard-false-positive-fix.md`.
- Logos-Sparks `run-command` removal + exec allowlist for subagents → `brain/output/eval/devin-subagent-exec-hardening.md`.

Neo's `SKILL.md` deliberately has no `allowed-tools` (`run_subagent`/`ask_user_question` aren't nameable entries).

## Subagents can never ask the user directly

Pointer: full mechanism in "`ask-user` withheld from every subagent (mechanics)" below.

**User-only restriction (observed runtime):** the host's saved sessions carry a system-level restriction — "Do not use subagents unless the user explicitly asks you to." Host runtime behavior, not a user request or Matrix change. Ask the user explicitly once before delegating; never override the host.

## Federated ships and `max-nesting`

Pointer: full `max-nesting` mechanism (formula `depth_from_root + subtree_depth`, Logos example) in "`run-subagent` in nestable artifacts" below.

## Session hygiene

See [`AGENTS.md`](AGENTS.md) §11.

## Matrix workspace mode auto-bootstrap (AGENTS.md §6 step 0)

Reuses `adapters/devin/hooks/session_audit.py` + the `activation.reinject` flag (`hooks/_flags.py`).

- **Wiring.** `session_audit.py` wired to `SessionStart`/`UserPromptSubmit`/`PostToolUse`/`PostCompaction`/`SessionEnd` in `~/.config/devin/config.json` by `adapters/devin/install-hooks.sh`.
- **Injection.** `activation.reinject` (effective value → `bin/matrix flags`; source `adapters/devin/config.yaml#flags`) renders `brain/data/activation-preamble.tmpl` (same source as `matrix_block_tmp()` in `bin/matrix` and the generated `neo` SKILL.md) as `hookSpecificOutput.additionalContext` in `SessionStart`/`UserPromptSubmit`.
- **`{{ADAPTER_DOC_PATH}}`** → `DEVIN.md` (`binding.doc_path` in `adapters/devin/adapter.yaml`); all three surfaces (`matrix_block_tmp()`, `adapters/_build.py`, `session_audit.py`'s `_render_activation_preamble()`) resolve it to an **absolute** path.
- **Scope.** `_activation_reinject_scope()` applies in workspace mode and in registry-resolved projects, on every `session_start`/`user_prompt_submit`, via `bin/matrix scope`.
- **Flag state.** See `bin/matrix flags` for the effective value of `activation.reinject`; it affects both workspace mode and project sessions.

### `activation.reinject_full` (throttled since 2026-09-01, Camino 2 Q1-A)

Effective value: see `bin/matrix flags` (absorbs legacy `experiment.activation_inject_userprompt_full`); full preamble on turn 1, again roughly every 10 turns; sentinel between.

- **Revert criterion.** Back to `true` only if (a) observed BLOCK ratio > 21% over ≥ 20 phase closes, **or** (b) a contract violation is traced to a throttled turn.
- **Known gap.** No env-var kill-switch — only editing `adapters/devin/config.yaml` directly.

## Hardening `permissions.deny` for secret stores

**Current status: DISABLED** (user decision, 2026-09-07, incident `incident-secret-deny-overblock-tl0090`). `permissions.deny` in `~/.config/devin/config.json` is empty and the `secret_deny` block of `adapters/devin/config.yaml` is `enabled: false`. State of the three flags required by `the_source`'s `config_flags_missing` check (post-deny-list-off 2026-09-07): `class_b_repo_secrets` (`enabled: false`, `patterns: []`), `static: []`, `exclude: []`. To re-enable: restore the declarative config and run `bin/matrix harden --target=devin --apply`.

Mechanics (valid if re-enabled): `bin/matrix harden --target=devin` reconciles `permissions.deny` against the `secret_deny` block of `adapters/devin/config.yaml`. Dry-run by default; `--apply` writes, `--revert` removes Matrix-managed entries. Uses the sidecar (`~/.config/devin/.matrix-managed-deny.json`) to respect manual deletions. `secret_deny.discover` scans `$HOME` for `credentials/` folders and `.env` files, emitting directory-level `Read(...)` patterns — never credential file names.

**Why it was disabled (semantics verified 2026-09-07, Devin CLI 3000.6.14):** `permissions.deny` with `Read(...)` does not only block the `read` tool: it also blocks `grep`/`glob` and `exec` commands that READ content with a literal path (`cat`, `ls`). It does NOT block predicates (`test -f`), `source`, or variable indirection (`$HOME`). The over-broad list (`~/.local/share/devin/**`) broke reading the CLI's own docs; the running session keeps its permission snapshot until restart. If re-enabled: use `test -f` for existence and `source` to load tokens (see lesson 65). The `pre_tool_use_guard` hook blocks dump verbs on denied paths (inactive with an empty deny list).

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
  browser: mcp__chrome-browser     # visual QA; no-op if unconfigured. Re-verified 2026-09-16.
  docs-lookup: mcp__context7       # version-pinned library docs
render:
  master: skill        # → .agents/skills/<name>/SKILL.md
  specialist: subagent # → .agents/agents/<name>/AGENT.md
```

This block is the `capabilities:` map (abstract capability → concrete tool id). A **separate** `allowed_tools:` map in the same `adapter.yaml` translates capabilities into Devin's *allowlist categories* — see "Least-privilege" above. The two maps use different nomenclatures on purpose.

### `run-subagent` in nestable artifacts (the `max-nesting` mechanism)

Under Devin, `run_subagent`/`read_subagent` are disabled inside a subagent by default (all core specialists are depth-1 children of Neo). They become available when the subagent profile carries a `max-nesting` frontmatter field whose value is at least the depth of the children it needs to spawn. The Trainman derives this value from the ship manifest's `captain`/`crew` graph — `depth_from_root + subtree_depth` — and injects it **only** into the captain's artifact. Crew leaves do not carry the field. For Logos: `logos-niobe` → `max-nesting: 2`; `logos-ghost`/`logos-sparks` → no field. **Formula verified only for depth 2; depth ≥3 needs a spike first.** **Nesting verified in vivo** → `brain/output/research/adapter-lessons-detail.md` §14.

### `ask-user` withheld from every subagent (mechanics)

Devin **never** allows a subagent to call `ask_user_question` — withheld unconditionally (platform rule, not configurable). Several specialists declare `ask-user` in the agnostic brain, but under the Devin adapter they run as **subagents**, so they cannot exercise it directly. Resolution: a specialist that needs to ask the user stops and returns the question to **Neo** (the master skill, not a subagent, so it retains `ask_user_question`). Neo relays and re-delegates. Devin-adapter concern only.

### Model policy → Devin frontmatter (mechanics)

The Trainman resolves each agent's `model_policy` tier through the adapter's `model_policy` map and writes the result as `model: <name>` in the generated `SKILL.md`/`AGENT.md` frontmatter. Re-run `bin/matrix build --target=devin && bin/matrix install --target=devin` after changing the map for the change to take effect globally.

## Boot WARN channel (D-boot)

`pre_activation_check` runs a `boot_warn` channel with seven information-only emitters (`surface_budget`, `the_source`, `validate_layer2`, `validate_lessons`, `model_drift`, `ttl_expired`, `snapshot_due`). The channel never blocks activation and never writes to `errors`/`checks`; it populates `boot_warn.warns` in the JSON and the `additionalContext` reinjected on `session_start` when the session is in scope.

- `surface_budget` token: size budget for the shared surface (`AGENTS.md` **bytes** warn 15,500 / fail 16,200; `DEVIN.md` **chars** warn 19,500 / fail 20,000; `brain/agents/neo.md` **chars** warn 19,500 / fail 20,000). Asymmetry is real: injection truncates at 16,384 B, `read` at 20,000 chars. `ok:false` only if a surface exceeds its `fail`; a `warn` state never flips `ok`. Fix: slim the offending doc.
- `BOOT_WARN_ENABLED`/`MATRIX_BOOT_WARN`: legacy aliases of `hooks.boot_warn` (deprecated).
- `BOOT_WARN_BUDGET_S`/`MATRIX_BOOT_WARN_BUDGET_S`: internal deadline, default `6.0`.
- The `session_audit` pre-check timeout is hardcoded at 20 s; a `pre_activation_check_status` of `timeout` is distinguishable from `ok`/`failed`/`error`.

Two manual mechanisms via `bin/matrix link`:

```bash
bin/matrix link model:override <agent-or-skill-name> <model-name> until=YYYY-MM-DD
bin/matrix link ttl:path-decision-reform matrix until=YYYY-MM-DD motivo=fallback-A-C1
```

`model:override` suppresses `model_drift` for that artifact while active. `ttl:path-decision-reform` is the fallback-A TTL; if it expires with zero real `phase:path-decision` uses, `ttl_expired` warns.

## Shared-surface gate & writer lane (Q2-D)

The `PreToolUse` hook (`adapters/devin/hooks/pre_tool_use_guard.py`) covers the native edit tools (`edit`, `write`, `multi_edit`), but **only against the harness's shared surface**: `AGENTS.md`, `DEVIN.md`, `brain/agents/*`, `brain/data/lessons.md`, `brain/data/capability-map.md`, `hooks/`, `bin/`, `adapters/`. A `project` session (cwd in a registry-resolved project) is **blocked** from editing that surface — except the proactive lessons promotion (only `brain/data/lessons.md` core and `brain/data/lessons/<current-project>.md`, both under a per-file writer lane). Matrix workspace mode keeps full access (also under the lane). The flags `gate.shared_surface` and `gate.writer_lane` (default on) gate the isolation and the lane; `gate.pre_exec_guard` gates the shell-command guard.

- **Exception / kill-switch:** relaunch with `MATRIX_SHARED_SURFACE_ALLOW=1` (or `true`) to bypass the `project` block for the whole session (emergencies only; audited). The kill-switch does NOT bypass the lane.
- **Writer lane:** `brain/state/lanes/<sha1(rel_path)[:16]>.json` — acquired on `PreToolUse`, released on `PostToolUse`/`SessionEnd`, reclaimed after `MATRIX_WRITER_LANE_TTL_S` (default `120`). A held lane blocks the edit and logs `bin/matrix link incident:writer-collision`.
- **Wiring (conditional):** `adapters/devin/install-hooks.sh` registers `PreToolUse` matchers for `edit`/`write`/`multi_edit`/`exec` → `pre_tool_use_guard.py` **only when** at least one of `gate.shared_surface`, `gate.writer_lane`, `gate.pre_exec_guard`, `gate.secret_deny` is effectively on (single loader `hooks/_flags.py`, effective state; an inert `gate.writer_lane` does not count; loader failure fails closed → registers). The `run_subagent` → `session_audit.py` matcher is always registered. Re-run `bin/matrix install --target=devin` after this change.

## Feature flags (Devin adapter)

`hooks/_flags.py` is the single loader (precedence: env `MATRIX_<NAME>` > `adapters/devin/config.yaml#flags` > `brain/config.yaml#flags` > DEFAULTS). `bin/matrix flags` shows effective value, source, risk and state; `flags --validate` exits 1 if there are `dangerous`/`inert` flags.

**Anti-truncation (Devin):** `read` returns at most 20,000 chars and prints `(truncated)` when it stops early; a truncated read is not full — resume the same file with `offset = last returned line + 1` until EOF. This file is kept ≤19,500 chars so a single read normally suffices.

The 12 flags: `activation.reinject`, `activation.reinject_full`, `gate.shared_surface`, `gate.writer_lane`, `gate.pre_exec_guard`, `gate.secret_deny`, `hooks.pre_activation_check`, `hooks.boot_warn`, `hooks.session_extras`, `memory.tree`, `views.scoped`, `binding.artifacts`. Effective state: see `bin/matrix flags` — the values in this doc are not the current state.

`hooks.session_extras` (default `false`) is the umbrella switch for the **non-audit** extras of `session_audit.py`: orphan-session detection, `link flags:state`, periodic `validate_routing_signal` (every 20 tools) and the `phase_close` nudge. Off = only the audit trail (`audit_event`) + `pre_activation_check` (its own flag) + `session close` on SessionEnd run.

**`post_tool_use` selective trim (always):** every tool call still refreshes the liveness binding and releases the writer lane (`edit`/`write`/`multi_edit`; release is flag-independent), but `bin/matrix scope` is skipped and the `hook-audit.jsonl` append runs only for consuming tools (`write`/`edit`/`multi_edit`/`exec`/`run_command`/`run-command`/`run_subagent`). **Accepted cost (cambio 7):** per-tool usage evidence loses fidelity — reads no longer appear in `hook-audit.jsonl`.

Legacy env: `MATRIX_INJECT_ACTIVATION`→`activation.reinject`; `BOOT_WARN_ENABLED`/`MATRIX_BOOT_WARN`→`hooks.boot_warn`. `gate.secret_deny` defaults off; to re-enable: flag on + `bin/matrix harden --target=devin --apply` (sidecar `~/.config/devin/.matrix-managed-deny.json`). The numeric TTLs (`MATRIX_WRITER_LANE_TTL_S`, `BOOT_WARN_BUDGET_S`/`MATRIX_BOOT_WARN_BUDGET_S`) are NOT flags.

## Lessons — adapter detail

Per-lesson narrative (citations, versions, IDs, tool names) in `brain/output/research/adapter-lessons-detail.md`. `lessons.md` keeps the operable rule + pointer.
