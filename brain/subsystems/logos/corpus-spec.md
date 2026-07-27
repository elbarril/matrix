# corpus-spec.md — Logos corpus convention

The corpus is the evidence store of the Logos. Every research topic lives in its own directory under `brain/subsystems/logos/corpus/<topic-slug>/`.

## Directory layout

```text
corpus/<topic-slug>/
├── _topic.yaml
├── sources/
│   ├── 01-<slug>.md
│   └── 02-<slug>.md
├── appraisals/
│   ├── 01-<slug>.md
│   └── 02-<slug>.md
└── synthesis.md
```

## `_topic.yaml`

| Field | Meaning |
|---|---|
| `question` | The research question. |
| `ref` | The Link `ref` that ties the topic to `research:request` / `research:result`. |
| `opened` | ISO-8601 timestamp when the topic was opened. |
| `status` | Lifecycle status: `open` → `ingested` → `appraised` → `synthesized` → `closed`. |
| `evidence-bar` | Minimum grade floor required for claims to leave the ship. |

## `sources/<nn>-<slug>.md` (Sparks)

Frontmatter:
```yaml
id: s01
title: <real title>
origin: <url | path | transcript-id>
retrieved: <ISO-8601>
ingested_by: sparks
type: doc | code | transcript | dataset | prior-oracle-pass
```

Body: verbatim excerpt or full source, without interpretation.

Rules:
- `sources/` is **append-only**; never edit a source after it is written.
- A source with incomplete frontmatter is rejected.

## `appraisals/<nn>-<slug>.md` (Ghost)

Frontmatter:
```yaml
source_id: s01
grade: high | moderate | low | very-low
grounds: <one-line reason>
appraised_by: ghost
appraised: <ISO-8601>
```

Body: concise reasoning for the grade.

Rules:
- One appraisal per source.
- `grade` and `grounds` are mandatory.
- `appraised_by` must be `ghost` and must not be the captain or the ingestor.

## `synthesis.md` (Niobe)

Frontmatter:
```yaml
ref: <R>
sources_used: [s01, s02]
grade_floor: <lowest grade cited>
gated_by: niobe
```

Body: graded synthesis. Every claim cites a source ID and its grade. Claims supported only by `very-low` sources are rejected.

## Lifecycle

1. `open` — Niobe opens the topic.
2. `ingested` — Sparks has written one or more `sources/`.
3. `appraised` — Ghost has written the matching `appraisals/`.
4. `synthesized` — Niobe has written `synthesis.md`.
5. `closed` — `research:result` has been written to the Link ledger.
