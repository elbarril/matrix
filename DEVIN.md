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

Every specialist's generated `AGENT.md` carries an `allowed-tools:` list, resolved from its `capabilities:` frontmatter through the `allowed_tools:` map in `adapters/devin/adapter.yaml` (categories: `read`, `edit`, `write`, `grep`, `glob`, `exec`, plus `mcp__server__tool` patterns — the actual Devin frontmatter vocabulary, distinct from the tool-call names in the `capabilities:` map above). **Re-measure, don't trust this paragraph:** `sed -n '2,/^---$/p' adapters/devin/generated/.agents/agents/<name>/AGENT.md` shows what the Trainman emitted, and `diff` against `~/.config/devin/agents/<name>/AGENT.md` shows whether `install` propagated it. Last re-verification: **2026-07-27**, after Smith's evaluator-with-remediation role change. The *written* grant is `read, edit, write, grep, glob, exec, mcp__chrome-browser__*` (confirmed on disk, generated == installed, byte-identical) — note `edit` and `write` **both** appear, because the abstract `edit` capability maps to `[edit, write]` here, so granting modification also grants file creation; Matrix accepts that widening and constrains creation in `smith.md`'s `<boundaries>` prose instead of splitting a new capability. **Live spike run same day, result: NOT reproduced in-session (Needs verification).** A `smith`-profile subagent spawned from Neo, mid-session, in the *same* CLI process that ran `install`, reported only `read, grep, find_by_name, exec` available — no `edit`/`write` — and correctly refused to bypass via `exec`. The `keymaker`-profile negative control also had no edit tool, as expected (restriction still holds). This means either (a) subagent profile/tool-grant resolution is snapshotted at CLI process start and does not hot-reload mid-session, or (b) some other caching layer is in play — **neither is confirmed**; no doc in this repo's `devin-master-documentation` copy states the discovery timing either way (checked `09-advanced-cli-features.md`, `07-troubleshooting.md`: no match). Re-run of the same positive/negative control pair from a **freshly started** CLI session (started after today's `bin/matrix install --target=devin`) now confirms Smith's `edit` is **live**: the spawned `smith` subagent reported exactly `read, edit, exec, grep, find_file_by_name` (5 tools, `edit` present), and the `keymaker` negative control again reported exactly `exec, read` (no edit). This refutes the earlier same-process negative result and confirms hypothesis (a) from lesson #26: subagent tool-grant resolution is snapshotted at CLI process start. That question is now **CLOSED** after a second independent fresh-process `smith` spike reported the identical full tool list, `edit, exec, find_file_by_name, grep, read` (5 tools). `write` is **CONFIRMED ABSENT** for subagents despite being declared in the installed `allowed-tools`: Smith's file-creation reach via the `edit`→`[edit,write]` capability widening does not work live for subagents, and only in-place modification of existing files is available. `glob` is **CONFIRMED PRESENT**, bound under the tool name `find_file_by_name` rather than literally named `glob`; there is no gap. `mcp__chrome-browser__*` is **CONFIRMED ABSENT** for subagents: no `mcp__*`-namespaced tool of any kind reaches a fresh `smith` subagent despite the installed declaration and Smith's `browser` capability, so that capability is non-functional for subagents today. This last point is a real, closed-but-unresolved-by-design gap: Neo/the user must decide whether to keep declaring `browser`/`mcp__chrome-browser__*` for Smith as documentation of an aspiration, or drop it until Devin exposes MCP tools to subagents. Earlier verified-restricted profiles, unchanged by this round: `keymaker` (only `read`+`exec`) ran `git status`/`git log`; `oracle` (adds `mcp__context7__*`) resolved a library id and queried its docs through context7.

Despite `write` being confirmed absent and `edit` confirmed unable to create new files (verified by a failed `edit`-with-empty-`old_string` attempt against a nonexistent path, which errors at the tool's own pre-flight existence check), a `smith` session was observed to successfully create a new eval artifact file. **Needs verification for the exact tool call:** the outcome (new file created, content present) is directly confirmed on disk; the most likely mechanism is `exec` with shell output redirection (`cat > file <<EOF` or equivalent), which remains available to every profile that has the `exec`/`run-command` capability regardless of `write`/`edit` grants.

### Inner-subagent audit observability

**2026-07-27 — measured TRUE, with a parent-session attribution caveat.** Neo dispatched a fresh `smith`-profile subagent in a genuinely new CLI process (started after today's `bin/matrix install --target=devin`) and it performed a real `edit` tool call against the scratch file `brain/state/scratch/m2-probe.txt` (gitignored, already deleted after the probe), changing the text from `scratch-M2-probe-baseline` to `scratch-M2-probe-edited-by-smith`. The call was captured in `brain/state/hook-audit.jsonl` (the file grew from 11794 to 11804 lines during the probe); the relevant appended line is verbatim: `{"timestamp": "2026-07-27T15:23:01.602822-03:00", "event": "post_tool_use", "pre_activation_check_ok": null, "session_id": "pointy-goldfish", "project_active": "claude-master-documentation", "tool_name": "edit", "tool_paths": ["/home/emiliano/www/emisrepos/matrix/brain/state/scratch/m2-probe.txt"]}`. M2 ("do inner-subagent tool calls reach the audit log") is therefore **confirmed TRUE**: the audit log records the correct `tool_name` and `tool_paths`. The caveat is that the recorded `session_id` (`pointy-goldfish`) is the **parent** Neo session's id, not a distinct id for the `smith` subagent that actually made the call. Today's audit log therefore cannot distinguish "Neo called `edit` directly" from "Neo's `smith` subagent called `edit`". This is the same category of attribution gap flagged at `brain/agents/neo.md:99` and in the earlier Claude-adapter feasibility checkpoint, now backed by a concrete measurement rather than a documentational concern.

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

Verified live against the installed binary (v3000.2.17) during Hardline/AFK Fase-0 research
(Oracle, this session — every claim below was run, not inferred from docs). This closes the
gap flagged by lesson-style D-f in `brain/output/plans/hardline-afk.md`: a real headless
primitive exists; it was simply never written down here.

- **The primitive:** `devin -p "<prompt>" [--permission-mode dangerous] [-r <session_id>]`.
  `-p`/`--print` runs a single turn non-interactively and exits — no REPL, no operator needed.
  Confirmed with a real end-to-end unattended run: `devin --permission-mode dangerous -p
  "create a file ... via shell"` actually created the file, zero human in the loop.
- **Exit code is not a success signal.** `devin -p` returns exit `0` whenever it completes a
  turn and prints a final response — including when the requested action was *refused* by
  permissions. Any wrapper must parse the printed text for refusal language (e.g. "rejected by
  the current permission mode") vs. success language; `$?` alone cannot distinguish them.
- **Unapproved tool calls auto-deny, they do not hang.** In default (`auto`) permission mode,
  a tool call requiring approval with no operator attached is auto-denied and the agent reports
  the refusal in its final text, then exits 0. Same "auto-deny, don't hang" behavior is
  documented for background subagents (`subagents.mdx`) — confirmed here to also hold at the
  top-level `-p` invocation, not just in-session.
- **`permissions.deny` survives `--permission-mode dangerous` when it is actually loaded.**
  A user-level config containing `permissions.deny` was tested to block a real commit attempt
  even under full `dangerous` mode. However, live Fase-4 verification found that a project-level
  `.devin/config.json` is **not reliably picked up by `devin -p`** in this installed version. The
  Fase-4 adapter therefore still writes the deny rules into the bound project's
  `.devin/config.json` (the design's requested location) and additionally passes a merged copy
  via `--config` so the rules are active at runtime. This is the real, working D5 guardrail.
- **Sessions are real and resumable.** Every `-p` run creates a listable session, resumable
  non-interactively via `devin -r <session_id> -p "<follow-up>"`. The `devin -p` invocation
  itself does not print a session id; immediately after the run, `devin list --format json`
  scoped to the project directory returns a JSON array of session objects. The `id` (or
  `short_id`) with the greatest `last_activity_at` timestamp is the session just created, and
  that is what the Fase-4 adapter captures and returns to Layer 1 for orphan recovery.
- **Docs-vs-live divergence:** the local docs bundle
  (`_versions/3000.2.17/share/devin/docs/reference/permissions.mdx` and
  `essential-commands.mdx`) names permission modes `normal`/`accept-edits`/`bypass`/`autonomous`.
  The live `--help` of that *same installed version* names them `auto`/`accept-edits`/`smart`/
  `dangerous`, and documents a `smart` mode and a `--agent-config` flag not present in the local
  bundle at all. **Treat live `devin --help` as ground truth for exact flag/value spelling**,
  even against a version-pinned local docs bundle — the concepts match, the exact names don't
  always.
- **Not yet spike-tested:** `--sandbox` (OS-level isolation via bubblewrap/seccomp/Seatbelt,
  documented in `sandbox.mdx`) and `devin cloud drs` / `/handoff` (cloud/detached execution).
  Both are real documented primitives but weren't exercised live in this research pass — worth
  a follow-up spike before relying on either.
- **Unrelated to any of the above:** the phantom headless subcommand string historically referenced
  in `brain/agents/lock.md:9`, `modules/hardline/README.md:31`, and `onboarding.html:836` is not a
  real Devin CLI command at any version — confirmed against the full `bin/matrix` dispatch
  table and the CLI's own changelog. It was phantom documentation debt, corrected in Fase 2 to
  `bin/matrix hardline dispatch <project> "<line>"` (not yet implemented — Fase 3).

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

Devin **never** allows a subagent to call `ask_user_question` — it is withheld from every subagent unconditionally, regardless of `allowed-tools` or permissions (platform rule, not configurable). Several specialists (Architect, Keymaker, Morpheus, Oracle, Trinity) declare the `ask-user` capability in the agnostic brain, but under the Devin adapter they run as **subagents** (`.agents/agents/<name>/AGENT.md`), so they cannot exercise it directly.

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

El spike de Neo en un proceso de CLI genuinamente nuevo (arrancado después del `install` de 2026-07-27) confirmó la hipótesis pendiente de la lección 26: el subagente `smith` recién spawneado reportó `read, edit, exec, grep, find_file_by_name` — `edit` estaba vivo — mientras que `keymaker` siguió reportando solo `exec, read`. Una llamada `edit` real del subagente `smith` llegó a `brain/state/hook-audit.jsonl` con `tool_name` y `tool_paths` correctos, pero el `session_id` registrado fue el de la sesión padre Neo (`pointy-goldfish`), no un id propio del subagente. Un segundo spike independiente en un proceso fresco confirmó que `write` y `mcp__chrome-browser__*` están **CONFIRMED ABSENT** para subagentes independientemente de su declaración en `allowed-tools`, mientras que `glob` sí está presente bajo el nombre `find_file_by_name`. El mecanismo más probable para la creación de un artefacto nuevo pese a `write` ausente es `exec` con redirección de shell.

### Lesson 28

Fase-0 (Oracle) probó `.devin/config.json` con `permissions.deny: ["Exec(git commit)","Exec(git push)"]` a nivel de proyecto y vio bloquear un commit real bajo `--permission-mode dangerous`. Fase-4 (Trinity), invocando `devin -p` sin REPL contra el mismo tipo de proyecto, encontró que esa misma regla de proyecto **no bloqueó** un commit real — pasó. El mecanismo que sí funcionó de forma reproducible (confirmado independientemente por Neo, dos corridas: una sin `--config` que comiteó, una con `--config` que bloqueó): generar un archivo de config temporal que fusiona el `~/.config/devin/config.json` real del usuario con las reglas `deny`, y pasarlo explícitamente con `--config <path>` en la invocación. La causa exacta de por qué `.devin/config.json` de proyecto no se carga de forma confiable bajo `-p` queda **sin resolver** — no se investigó a fondo el motivo (¿se resuelve el cwd distinto al pasar `-p` con `--config`? ¿hay algún orden de precedencia distinto en modo no-interactivo?), solo se confirmó el síntoma y el workaround. Ver `hardline-dispatch.sh` (`adapters/devin/`) para la implementación real.

### Lesson 29

El pedido era "que Neo arranque solo en modo workspace de Matrix". Primera respuesta descartada: `hooks/session_start_bootstrap.py` (Seraph) + `adapters/devin/session-start-hook.sh` + un `.devin/config.json` de proyecto nuevo registrando `hooks.SessionStart`. Funcionaba (confirmado con un spike real de `devin -p`), pero duplicaba `adapters/devin/hooks/session_audit.py`, que ya estaba wireado globalmente en `~/.config/devin/config.json` por `adapters/devin/install-hooks.sh` (instalado a mano en esta máquina, nunca por el flujo de `bin/matrix install --target=devin`) y que ya tenía un experimento llamado "Etapa G/H3" (`experiment.activation_inject` en `adapters/devin/config.yaml`, `false` desde que se escribió el 2026-07-17) para inyectar la misma clase de contenido vía `hookSpecificOutput.additionalContext`. La corrección real: se borraron los tres archivos nuevos; se agregó `_is_workspace_mode()` (compara `os.getcwd()` contra `MATRIX_ROOT`) y `_render_activation_preamble()` (renderiza `brain/data/activation-preamble.tmpl`, la misma plantilla que ya usa el `neo` skill generado y el bloque `AGENTS.local.md` de proyectos bindeados vía `matrix_block_tmp()` en `bin/matrix`) a `session_audit.py`; se prendió `activation_inject: true` acotado por ese chequeo de cwd; y se agregó la llamada a `install-hooks.sh` al final de `adapters/devin/install.sh`, que antes no la incluía.

### Lesson 34

El hook de ciclo de vida mencionado en la lección 34 es `Stop`; el CLI concreto al que aplica es **Devin CLI**. El detalle del bug y la batería de inyección de errores quedan en `brain/data/lessons.md` lección 34.

### Lesson 38

Tercer incidente confirmado de `~/.local/share/devin/cli/sessions.db` (el store SQLite local que respalda `/resume`, `-r`/`--resume`, `-c`/`--continue` y el picker de `/ls`) corrupto con `database disk image is malformed`. Dos antecedentes: uno con reparación registrada en el ledger de Matrix (`2026-07-20T12:10:52-03:00`, proyecto `generalmotors`: "recreada desde .dump sanitizado, 487 sesiones recuperadas, integrity_check ok" — sin detalle de metodología); otro sin lección escrita, encontrado solo porque el propio `prompt_history` recuperado de esta corrida conservaba la pregunta textual del usuario en una sesión previa ("quise usar /resume pero tiro este error... como se arregla?").

**Diagnóstico:** `PRAGMA integrity_check` marcó `btreeInitPage() returns error code 11` en dos árboles — `message_nodes` (rootpage de esa corrida, ~169k filas, transcripciones completas de mensajes) y `rendered_commits` (~44k filas, cache HTML de la vista de replay) — pero ninguno en `sessions`, `prompt_history`, `app_state` ni `tool_call_state`. La corrupción es parcial y despareja, no total.

**Vía que falló:** `sqlite3 <db> ".recover"` (la vía moderna que la propia documentación de SQLite recomienda para bases corruptas) devolvió directamente `sql error: no such table: sqlite_dbpage` — el binario `sqlite3` de este sistema (3.45.1, paquete de la distro) no está compilado con esa virtual table. Sin esa vía, la única alternativa viable es `.dump`.

**Vía que funcionó (procedimiento completo, reproducible):**

```bash
DEVIN_DIR="$HOME/.local/share/devin/cli"

# 1. Volcado tolerante a corrupción — exit 0 y stderr vacío NO implican volcado completo/válido
sqlite3 "$DEVIN_DIR/sessions.db" ".dump" > /tmp/dump.sql 2> /tmp/dump.err

# 2. LA TRAMPA: si sqlite3 detectó errores al recorrer una tabla, cierra el dump con
#    "ROLLBACK; -- due to errors" en vez de "COMMIT;". Todo el .dump vive en una sola
#    transacción BEGIN...COMMIT — reimportarlo tal cual da una base VACÍA, sin ningún
#    error visible (exit 0, stderr vacío). Verificar SIEMPRE la última línea:
tail -1 /tmp/dump.sql   # "ROLLBACK; -- due to errors" => hay que sanear antes de importar

# 3. Saneo mínimo: solo la última línea, no tocar nada más
sed '$s/^ROLLBACK; -- due to errors$/COMMIT;/' /tmp/dump.sql > /tmp/dump_sanitized.sql

# 4. Reconstrucción en un archivo nuevo (no pisar el original todavía)
sqlite3 /tmp/scratch.db < /tmp/dump_sanitized.sql

# 5. Verificación — debe devolver "ok"
sqlite3 /tmp/scratch.db "PRAGMA integrity_check;"

# 6. Swap con backup fechado (mismo criterio que el incidente de generalmotors),
#    incluyendo el -wal/-shm viejo para que la base nueva arranque sin arrastrar
#    un WAL de una generación de esquema distinta:
TS=$(date +%Y%m%d_%H%M%S)
mv "$DEVIN_DIR/sessions.db" "$DEVIN_DIR/sessions.db.corrupt.$TS"
mv "$DEVIN_DIR/sessions.db-wal" "$DEVIN_DIR/sessions.db.corrupt.$TS-wal" 2>/dev/null
mv "$DEVIN_DIR/sessions.db-shm" "$DEVIN_DIR/sessions.db.corrupt.$TS-shm" 2>/dev/null
mv /tmp/scratch.db "$DEVIN_DIR/sessions.db"
chmod 644 "$DEVIN_DIR/sessions.db"
```

Resultado real de esta corrida: 644 `sessions`, 1822 `prompt_history`, **169.323 `message_nodes`** (antes ilegible, ni siquiera `SELECT count(*)` corría), 44.327/44.445 `rendered_commits` (~99,7%; el resto son filas de cache de replay, no contenido fuente), `app_state`/`tool_call_state` intactos. Los únicos 3 puntos que `.dump` marcó explícitamente como perdidos aparecen como comentarios `/****** CORRUPTION ERROR *******/` inline en el dump, justo antes de la fila/tabla afectada — grepear ese literal ancla de línea (`^/\*\*\*\*\*\* CORRUPTION ERROR`) da un conteo exacto de filas irrecuperables, sin necesidad de adivinar.

**Verificación E2E real (no solo `integrity_check`):** `adapters/devin/session_query.py find <cwd_substring>` y `session_query.py dump <session_id>` corridos contra la base reparada reconstruyeron correctamente tanto el listado de sesiones de un proyecto real como la transcripción completa de una sesión histórica real (una de `saintlukes`, ~1200 líneas de conversación). Esto prueba que `message_nodes` recuperado es legible por el mismo tipo de consulta relacional que usaría la función real de resume — no solo que pasa un chequeo estructural de bajo nivel.

**Limitación operativa (no tiene workaround conocido):** un proceso de Devin CLI que ya tenía `sessions.db` abierto (por descriptor de archivo, no por path) sigue leyendo/escribiendo esa misma inode después del swap — un `mv` en el mismo path no lo afecta hasta que ese proceso vuelva a abrir el archivo. Consecuencia directa: la sesión que hace la reparación en vivo (y cualquier otro proceso de Devin CLI corriendo en simultáneo — REPL, integraciones ACP, etc.) nunca se ve a sí misma reparada; hace falta cerrarla y abrir una nueva para que `/resume`/`-r`/`-c` reflejen el historial recuperado. Confirmado en esta corrida: `session_query.py dump` sobre la sesión que ejecutó la propia reparación no encontró mensajes (esperado — esa sesión nunca estuvo en el `.dump` porque su contenido más reciente todavía no había pasado por un checkpoint de WAL al momento del volcado).

**Causa raíz de la corrupción en sí: no confirmada, queda abierta.** En el momento del hallazgo había 2 procesos de Devin CLI activos (`devin --permission-mode bypass` y `devin acp`), ambos corriendo el mismo binario/versión (descarta desincronización de esquema entre versiones distintas como causa en este caso puntual). `sessions.db` vive en ext4 local, no en red/FUSE, con >250 GB libres (descarta filesystem de red y disco lleno). Hipótesis más plausible y no verificada: escritura concurrente WAL desde 2+ procesos de Devin CLI sobre el mismo `sessions.db`, posiblemente agravada por un cierre abrupto (kill -9, crash) de alguno de ellos en algún momento entre incidentes. Recomendado reportar con `/bug` la próxima vez que se reproduzca, adjuntando PIDs, versiones y `ps aux` de los procesos de Devin CLI activos en ese momento — hoy no hay evidencia suficiente para que Cognition lo triangule.

**Corrección same-day (2026-07-30, ~40 min después del repair de arriba):** el usuario reportó un síntoma nuevo de `/resume` en una sesión nueva (`bead-maiasaura`, proyecto `saintlukes`): `Invalid column type Null at index: 0, name: id` — el texto exacto que produce el `Display` de `rusqlite::Error::InvalidColumnType` cuando el binario de Devin CLI lee la columna `id` de una fila de `sessions` y da NULL. Esto prueba que el diagnóstico original de esta lección ("ninguna corrupción en `sessions`") era incompleto: `PRAGMA integrity_check` y el conteo de comentarios `CORRUPTION ERROR` solo cubren lo que la herramienta *reconoce* haber tocado, no fila por fila.

*Por qué puede pasar en `sessions.id` y no en `prompt_history.id`/`rendered_commits.id`:* `sessions.id` es `TEXT PRIMARY KEY` **sin** `NOT NULL` explícito — un `PRIMARY KEY` no-`INTEGER` en SQLite no bloquea NULL (solo un alias de rowid `INTEGER PRIMARY KEY` lo hace, autoasignando en vez de aceptar NULL). `prompt_history.id`/`rendered_commits.id` sí son `INTEGER PRIMARY KEY` — por eso 0 filas NULL ahí, ni antes ni después.

*Auditoría real que encontró el alcance completo (no solo el síntoma reportado):*
```bash
DEVIN_DIR="$HOME/.local/share/devin/cli"
OLD="$DEVIN_DIR/sessions.db.corrupt.20260730_121318"   # el backup pre-repair de ESE MISMO día, no lo borres nunca en el mismo día del repair

# 1. Filas con columnas de tipo incorrecto (no solo NULL en id — cualquier columna NOT NULL con typeof() distinto del declarado)
sqlite3 "$DEVIN_DIR/sessions.db" "SELECT rowid,id,typeof(id),typeof(last_activity_at),typeof(created_at) FROM sessions WHERE typeof(id)!='text' OR typeof(last_activity_at)!='integer' OR typeof(created_at)!='integer';"

# 2. Diff completo de claves entre el backup pre-repair y la base reparada (la auditoría que realmente importa)
sqlite3 "file:$OLD?mode=ro" -readonly "SELECT id FROM sessions WHERE id IS NOT NULL;" | LC_ALL=C sort > /tmp/old_ids.txt
sqlite3 "file:$DEVIN_DIR/sessions.db?mode=ro" -readonly "SELECT id FROM sessions WHERE id IS NOT NULL;" | LC_ALL=C sort > /tmp/new_ids.txt
LC_ALL=C comm -23 /tmp/old_ids.txt /tmp/new_ids.txt   # ids perdidos por el repair, no solo corruptos en origen
```

Resultado de esta auditoría: 1 fila fantasma (`id` NULL) + **6 filas de `sessions` perdidas por completo** (`catnip-tarp`, `confusion-occupation`, `healthy-roundworm`, `plain-hellebore`, `somber-speaker`, `tungsten-pleasure`) que el `.dump` secuencial original nunca marcó con `CORRUPTION ERROR` ni hizo fallar `integrity_check` — desaparecieron en silencio. Confirmado irrecuperables: ni una búsqueda indexada directa por `id` contra `$OLD` (`WHERE id='catnip-tarp'`, etc., forzando el uso del índice en vez de un scan secuencial) ni sus `message_nodes`/`prompt_history` en la base reparada (0 filas huérfanas) las trajeron de vuelta. Pérdida real, no solo de metadata de listado.

*La trampa de la fila fantasma — no asumas que un valor sospechoso es la fila real con la columna corrida:* la fila con `id` NULL tenía en la posición de `working_directory` el string `elastic-numeric`, que **sí** es un `id` real de otra sesión — parecía una fila real con las columnas desalineadas por la corrupción. Cruzarlo contra una búsqueda indexada directa (`WHERE id='elastic-numeric'`) en `$OLD` mostró que esa sesión ya estaba sana y completa en su propia fila (rowid distinto) — el string en la fila fantasma era ruido de página corrupta que por casualidad coincidía con un id real ya existente en otro lado, no la misma fila corrida. Regla operable: antes de "reparar" una fila sospechosa reconstruyendo valores, buscá cada valor sospechoso por índice directo en el backup corrupto — si aparece sano en una fila propia, la fila sospechosa es ruido y el fix es borrarla, no fusionarla.

*Fix aplicado (mínimo, verificado):*
```bash
cp -p sessions.db "sessions.db.before-nullid-fix.$(date +%Y%m%d_%H%M%S)"
sqlite3 sessions.db "DELETE FROM sessions WHERE id IS NULL;"
```
Verificación E2E post-fix: `integrity_check` ok; `SELECT COUNT(*) FROM sessions WHERE id IS NULL` = 0; 0 filas con `typeof()` incorrecto en ninguna columna NOT NULL; lectura completa de las 644 filas restantes sin excepción; `session_query.py find` corrió limpio contra la base viva.

*Nota operativa nueva (corrige/matiza la limitación de arriba):* este fix fue un `DELETE`/`UPDATE` **in-place** sobre el mismo archivo/inode que los procesos de Devin CLI ya tenían abierto (confirmado con `fuser sessions.db` antes y después: mismos 2 PIDs) — a diferencia del swap de archivo (`mv`) de la reparación original, un DML in-place en modo WAL sí es visible para procesos ya abiertos sin necesidad de reiniciarlos. La limitación de "hace falta reiniciar" aplica al **swap de archivo**, no a una corrección puntual de filas sobre el archivo ya vigente — para fixes chirúrgicos post-repair, preferí DML in-place por esta razón.

### Lesson 37

En Devin CLI, el archivo de estado local del proyecto es `.devin` (directorio `.devin/` en la raíz del proyecto). En `saintlukes`, el `.gitignore` del proyecto solo tenía `_brain`, `AGENTS.local.md` y `.devin`; faltaba `matrix-output/`, por lo que un artefacto de research escrito ahí corría riesgo real de ser trackeado en el repo del cliente.

### Lesson 42

El hook de auditoría de sesión que implementa los mecanismos de detección de sesiones huérfanas es `adapters/devin/hooks/session_audit.py`, wireado globalmente en `~/.config/devin/config.json` por `adapters/devin/install-hooks.sh`.

### Saint Luke's

La regla dura del usuario de `brain/data/lessons/saintlukes.md` surgió de una sesión con Devin CLI en la que el usuario compartía el working tree del proyecto `saintlukes` con ediciones manuales propias; dos cambios reales del usuario (`referrals/css/specifics.css` y el token `--t-tc--buttons--font--family` en `library__theme.css`) fueron revertidos por error al asumir que eran drift de un subagente.
