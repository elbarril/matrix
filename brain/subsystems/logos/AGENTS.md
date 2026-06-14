# AGENTS.md — the Logos (federated research ship)

> The Logos is a ship in the fleet: its own captain, its own crew, its own contract. It coordinates with the core (Nebuchadnezzar) only through the shared **Link** ledger — never by reaching into the core's state.

The Logos is the **deep-research subsystem**: evidence-graded investigation with a structured corpus, for questions too big for a single Oracle pass. It is **lazy-loaded** — only spun up when explicitly invoked. The core works without it.

## Why a separate ship

Deep research has its own discipline (evidence grading, provenance, an integrity gate) that would bloat the core roster. Federation keeps that discipline contained on its own ship, with its own master, instead of swelling Neo's roster. (Roster discipline applies per ship.)

## The crew

- **Niobe** — *captain / master*. Charts the research course, routes within the ship, holds the corpus. The Logos's single voice. (See `agents/niobe.md`.)
- **Ghost** — *evidence appraiser*. Reads deep, grades each source for quality and provenance (a GRADE-style ladder: high / moderate / low / very low).
- **Sparks** — *operator / ingestion*. Pulls signals into the corpus (file drops, transcripts, fetched docs) and keeps provenance attached.

> Adding a fourth crew member requires retiring or merging one. Three is plenty for v1 of the ship.

## Hard rule — the integrity gate

No claim leaves the Logos to the user (via the core) without:

1. a graded evidence trail (every assertion cites a source with its grade), and
2. a final integrity pass by the captain that rejects anything ungrounded.

"Si no es real, no cuenta" applies twice as hard here: a confident-sounding synthesis with weak sources is a failure, not a result.

## Coordination with the core

- The Logos reads the request handed to it via the Link ledger (`research:request`) and writes its result back as `research:result`.
- It never edits the core's `brain/state/` directly. The ledger is the only shared surface.
- Neo presents the Logos's graded result to the user; the Logos never speaks to the user directly.

## State

Ship state lives under `brain/subsystems/logos/`:

```text
brain/subsystems/logos/
├── AGENTS.md            # this contract
├── agents/niobe.md      # captain
└── corpus/              # structured, provenance-tagged sources (gitignored)
```
