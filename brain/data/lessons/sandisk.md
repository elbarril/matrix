# Lessons — sandisk (Portal Templates Group)

## Backfill note (2026-07-23)

This file did not exist when the eval phase closed on 2026-07-23 for the
agency/docusign work (T1221203_sandisk_AgencyFoundational) — the durable
info below lived only in a checkpoint and in the project's own
`matrix-output/eval/sandisk-agency-T1221203.md`. Reconstructed from those
sources; see `brain/state/checkpoints.jsonl` (2026-07-23T18:10:12) for the
full narrative if more detail is needed.

## Repo/portal context

- `sandisk` has only 2 real portals: `agency` (base corelayer ~25.9, newer
  but not yet branded) and `docusign` (base ~25.8, older but already
  finished to brand: local Pilat fonts, brand social icons, theme fixes).
  Same brand values (identical swatches) across both.
- External canonical reference for structure/lineage: `foundationals/agency`
  (golden). F0a (lineage chrome) verified with no real diff vs it.
- Working ticket: `T1221203_sandisk_AgencyFoundational`. No commit/push was
  made at close of the 2026-07-23 session — the `agency` working tree was
  left with the changes ready for the user to review visually before
  committing.

## Decisions confirmed by the owner/user (don't re-ask)

- Banner copy: do NOT touch, stays placeholder.
- Footer logo → `logo--default.svg`.
- Job-cards architecture: bounded macro `jobCardValues(job)` for the fields
  block only; shells/banner stay in-place (Option C — rejected both a
  "god-macro" and pure in-place duplication).
- Candidates table (6 columns: Candidate Name / Submitted for /
  Requisition # / Submission status / Submitted on / Last updated) applies
  to BOTH the Dashboard widget and the full `MyReferrals.page`.
- `Requisition #` must read from `person.req` (builtin corelayer field),
  not `person.jobId` (that's the internal ID) — confirmed correct by
  cross-portal pattern in ~10 other portals with the same Library-v3
  architecture.

## Known gaps (declared, non-blocking, pending a future session)

- POST `/agency/ReferCandidate` returns HTTP 500 on real submit. Root cause
  reproduced and confirmed as **backend/instance config**, not this
  session's code: Record Picker field `6326 "Agency Name"` is explicitly
  marked "HIDDEN BECAUSE PAS INTERVENTION IS NEEDED" in the served form.
  Needs PAS/instance-admin intervention — no template fix will resolve it.
- Custom field IDs `220` (Job Type), `135` (Type of Employment), `8`
  (Business Unit) are wired in `Default.config` but not yet validated
  against the instance's real schema — pending a future session with the
  Figma sample screens.
- `Requisition #` appeared empty for one test candidate because that
  specific `JobPerson` record has no `person.req` populated (data gap on
  that record, not a template bug — the field choice itself is correct).

## Process notes

- **Dev-instance render link (agency)**, bypasses Login and stays
  authenticated (same `DataCompletionRequest?uid=...` pattern as
  `saintlukes.md`): `https://obfint54486.ir02.obfuscate.xcade.dev/DataCompletionRequest?uid=ihP4lcEURQ1uXdJ7`.
  Found on 2026-07-24 not saved anywhere in-repo — it lives only on TEG
  case `1221203` notes (`teg-get-notes.sh 1221203`). **Lesson learned the
  hard way (user called it out): as soon as a dev-instance link is found,
  save it here immediately, don't leave it to be re-discovered next
  session.** CSS/template changes reflect on this instance right after a
  `git push` to the branch (no tag-pull wait observed for CSS); new
  binary assets (svg/webp/fonts) may still need the tag pull — not
  confirmed either way yet, this session's new SVG happened to show up
  immediately.
- `config.enableRecommendAFriend` is OFF on this instance → `.banner--extra`
  (recommend-a-friend block, `agency/tpt/recommendAFriend.tpt`) never
  renders here. Any change touching it can only be verified statically,
  not visually, until an instance with that flag enabled is available.

## Decisions confirmed by the owner/user — Actions & Links (buttons/links) task (2026-07-24)

- Scope: `agency` portal only (not `docusign`), same branch `T1221203_sandisk_AgencyFoundational`,
  no push without explicit ask in-session.
- Link mismatch (invisible underline at rest, no hover color change to brand red, no click-focus
  indicator): fix it directly in `agency` (`specifics.css`/`library__theme.css`, consuming the
  already-existing `--t-gs--color--text--link--hover` token) rather than waiting to confirm an
  external/core layer first.
- Figma's "Link S" (breadcrumbs/footer) and "Link M" (general) variants: formalize as explicit
  `.link--s`/`.link--m` classes (don't keep the current implicit context-based `.footer .link`
  sizing).
- Tertiary button / Disabled button / link "Selected" state: user wants these actively found and
  tested live (not left as declared gaps) before implementing.
- Breakpoints: include mobile and tablet in this pass, not just desktop.

## Roster-discipline fix applied (2026-07-24), per the pending gap from the banner text-size session

`figma-audit` subagent is used strictly in its intended read-only role (produces a discrepancy
table only, per its own AGENT.md — never implements/commits/pushes). The actual flow for this
task: figma-audit (audit) -> Architect (reviews the discrepancy table, classifies CODE/EXTERNAL-
BRAND/CONTENT/ASSET-MISSING) -> Trinity (implements) -> Smith (gate, re-audit against the same
cited sources). No commit/push without the user asking for it explicitly in-session — this was
the exact gap flagged by the user in the previous session (unauthorized push after a banner fix).

- Client styleguide (Figma export) lives at
  `sandisk/1221191 - [Sandisk] - Style Guide/07 Stylesheet - Layout.svg`
  (+ a broken/huge companion `.png` — use the `.svg`, crop it with
  `convert -crop WxH+X+Y` and resize down, the raw file is 1920x9981 and
  too big to read directly). Confirmed banner spec found there: solid
  brand-red background + "SANDISK" wordmark SVG top-right + white heading
  text, exact min-heights per breakpoint: Desktop Large/Small 300px,
  Tablet 350px, Mobile 375px (agency's pre-existing height tokens didn't
  match this and caused a real heading/logo overlap bug on mobile — see
  2026-07-24 checkpoint).
