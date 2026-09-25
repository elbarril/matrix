#!/usr/bin/env python3
"""extract_metrics.py — single deterministic extraction of Matrix harness
health metrics (commits, checkpoints, activity log, lessons, validation
report, routing signal history, orphan-close attempts).

Python 3 stdlib only. No external dependencies, no `pip install`.

See .devin/skills/harness-health-report/SKILL.md for the full workflow this
script is part of, and contracts/metrics-schema.json for the JSON Schema
that validates its --out JSON output.
"""

import argparse
import json
import re
import subprocess
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path

KNOWN_COMMIT_TYPES = ["feat", "fix", "docs", "chore", "refactor", "test"]

# Ordered list of contract files measured under context_bytes. The trio
# (AGENTS.md, neo.md, DEVIN.md) is summed separately as trio_total.
CONTEXT_FILES = [
    "AGENTS.md",
    "brain/agents/neo.md",
    "DEVIN.md",
    "brain/data/lessons.md",
    "brain/data/activation-preamble.tmpl",
]

# Minimal YAML-value reader for the single boolean flag we need.
# The file is hand-maintained and simple key: value; this avoids adding a
# third-party dependency to a stdlib-only script.
def _read_yaml_boolean(path: Path, key: str):
    if not path.is_file():
        return None
    key_re = re.compile(rf"^\s*{re.escape(key)}\s*:\s*(\S.*?)$")
    for line in path.read_text(encoding="utf-8").splitlines():
        match = key_re.match(line)
        if not match:
            continue
        value = match.group(1).split("#", 1)[0].strip().lower()
        if value in ("true", "yes", "on"):
            return True
        if value in ("false", "no", "off"):
            return False
    return None

# Conventional Commits prefix at the START of the subject line, optional
# (scope) that may contain dots/slashes/underscores/hyphens, optional `!`
# before the colon (breaking-change marker), e.g.:
#   feat: ...
#   fix(module.sub-part): ...
#   refactor(a/b_c)!: ...
COMMIT_PREFIX_RE = re.compile(r"^([a-z]+)(\([^)]*\))?!?:")

# Line format of lessons.md numbered entries: "50. **text**"
LESSON_LINE_RE = re.compile(r"^(\d+)\.")

# activity.log's real, current line format is pipe-delimited with an
# ISO8601-with-offset (or Z) timestamp as the first column, e.g.:
#   2026-06-13T22:03:57-03:00 | project:work | chron | ...
# A small number of legacy lines predate this format entirely, e.g.:
#   [2024-06-23T10:30:00Z] phase:close | smith | ... | ...
# which does not carry the timestamp in column 1 and would otherwise
# corrupt both by_event_type and first_ts/last_ts if naively split on "|".
# Those lines are counted in total_lines (they are real, non-empty lines)
# but excluded from by_event_type/first_ts/last_ts, with a warning.
ACTIVITY_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")


def resolve_matrix_root(start: Path) -> Path:
    """Walk up from this script's location until brain/ + AGENTS.md are
    found. Same pattern used elsewhere in the repo (see AGENTS.md ->
    "Root resolution (robust)"). Never assume cwd.
    """
    current = start.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "brain").is_dir() and (candidate / "AGENTS.md").is_file():
            return candidate
    raise RuntimeError(
        "Could not resolve Matrix root: no ancestor of "
        f"{start} contains both brain/ and AGENTS.md"
    )


def run_git(matrix_root: Path, args):
    result = subprocess.run(
        ["git", *args],
        cwd=str(matrix_root),
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout


def build_git_log_args(since):
    """Build the `git log` argument list honoring --since.

    Criterion (documented, simplest-that-works per Foundation 4): if the
    value looks like a git ref/range (contains ".." or matches a
    hex-ish/short-sha-like or branch-name token without spaces and without
    a leading digit-date shape), treat it as `git log <since>..HEAD`.
    Otherwise treat it as a date/duration understood by `git log --since=`
    (e.g. "2026-08-01", "2 weeks ago"). This is a heuristic, not a strict
    parser — good enough for the interface to accept both forms without
    breaking when --since is omitted entirely.
    """
    args = ["log", "--pretty=%s"]
    if not since:
        return args
    if ".." in since:
        args.append(since)
    elif re.match(r"^[A-Za-z0-9._/-]+$", since) and not re.match(r"^\d{4}-\d{2}-\d{2}", since):
        args.append(f"{since}..HEAD")
    else:
        args.insert(1, f"--since={since}")
    return args


def extract_commits_by_type(matrix_root: Path, since, warnings):
    args = build_git_log_args(since)
    raw = run_git(matrix_root, args)
    subjects = [line for line in raw.splitlines() if line.strip() != ""]
    counts = OrderedDict((t, 0) for t in KNOWN_COMMIT_TYPES)
    counts["other"] = 0
    for subject in subjects:
        match = COMMIT_PREFIX_RE.match(subject)
        commit_type = match.group(1) if match else None
        if commit_type in KNOWN_COMMIT_TYPES:
            counts[commit_type] += 1
        else:
            counts["other"] += 1
    counts["_total"] = len(subjects)
    if counts["other"] > 0:
        warnings.append(
            f"commits_by_type: {counts['other']} commit(s) did not match any "
            "known Conventional Commits prefix and were counted as 'other'"
        )
    return dict(counts)


def read_lines(path: Path):
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def extract_checkpoints(matrix_root: Path, warnings):
    path = matrix_root / "brain/state/checkpoints.jsonl"
    lines = read_lines(path)
    result = {
        "total_lines": 0,
        "by_agent": {},
        "first_ts": None,
        "last_ts": None,
    }
    if lines is None:
        warnings.append(f"checkpoints: file not found at {path}")
        return result

    parse_errors = 0
    timestamps = []
    parsed_any = False
    for line in lines:
        if line.strip() == "":
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            parse_errors += 1
            continue
        result["total_lines"] += 1
        ts = record.get("timestamp")
        if isinstance(ts, str) and ts:
            timestamps.append(ts)
        parsed_any = True

    if parse_errors:
        warnings.append(
            f"checkpoints: {parse_errors} line(s) failed JSON parsing and were skipped"
        )

    # by_agent: the current checkpoints.jsonl schema (timestamp/user/project/
    # note/context) has no clean, dedicated agent/actor field -- agent names
    # only appear inline inside free-text `note` values (e.g. "Trinity(...)")
    # which is not a reliable structured field to aggregate on. Left as {}
    # rather than inventing a fragile regex-over-prose heuristic.
    if parsed_any:
        warnings.append(
            "checkpoints.by_agent: no dedicated agent/actor field exists in the "
            "current checkpoints.jsonl format; left empty rather than parsing "
            "free-text notes"
        )

    if timestamps:
        timestamps.sort()
        result["first_ts"] = timestamps[0]
        result["last_ts"] = timestamps[-1]

    return result


def extract_activity_log(matrix_root: Path, warnings):
    path = matrix_root / "brain/state/activity.log"
    lines = read_lines(path)
    result = {
        "total_lines": 0,
        "by_event_type": {},
        "first_ts": None,
        "last_ts": None,
    }
    if lines is None:
        warnings.append(f"activity_log: file not found at {path}")
        return result

    # Real line format (pipe-delimited columns):
    #   <ISO8601-with-offset> | <event_type>      | <field3>         | <field4...>
    event_counts = Counter()
    timestamps = []
    malformed = 0
    for line in lines:
        if line.strip() == "":
            continue
        result["total_lines"] += 1
        parts = line.split("|")
        ts_raw = parts[0].strip()
        if len(parts) < 2 or not ACTIVITY_TS_RE.match(ts_raw):
            malformed += 1
            continue
        event_type = parts[1].strip()
        if event_type:
            event_counts[event_type] += 1
        if ts_raw:
            timestamps.append(ts_raw)

    if malformed:
        warnings.append(
            f"activity_log: {malformed} line(s) did not match the current "
            "pipe-delimited '<ISO8601 ts> | <event_type> | ...' format "
            "(legacy format) and were excluded from by_event_type/first_ts/"
            "last_ts, though still counted in total_lines"
        )

    result["by_event_type"] = dict(event_counts)
    if timestamps:
        timestamps.sort()
        result["first_ts"] = timestamps[0]
        result["last_ts"] = timestamps[-1]

    return result


def extract_context_bytes(matrix_root: Path, warnings):
    result = {"files": {}, "trio_total": None}
    trio_keys = {"AGENTS.md", "brain/agents/neo.md", "DEVIN.md"}
    trio_sum = 0
    all_found = True
    for rel in CONTEXT_FILES:
        path = matrix_root / rel
        if not path.is_file():
            warnings.append(f"context_bytes: file not found at {rel}")
            result["files"][rel] = None
            all_found = False
            continue
        size = path.stat().st_size
        result["files"][rel] = size
        if rel in trio_keys:
            trio_sum += size
    result["trio_total"] = trio_sum if all_found else None
    return result


def extract_artifact_counts(matrix_root: Path):
    output_dir = matrix_root / "brain/output"
    result = {"total": 0, "by_subdirectory": {}}
    if not output_dir.is_dir():
        return result
    for subdir in sorted(output_dir.iterdir()):
        if not subdir.is_dir():
            continue
        count = sum(1 for _ in subdir.rglob("*") if _.is_file())
        if count:
            result["by_subdirectory"][subdir.name] = count
            result["total"] += count
    return result


def extract_phase_close_verdicts(matrix_root: Path, warnings):
    path = matrix_root / "brain/state/activity.log"
    lines = read_lines(path)
    result = {"pass": 0, "block": 0, "ratio": None}
    if lines is None:
        warnings.append(f"phase_close_verdicts: file not found at {path}")
        return result

    pass_count = 0
    block_count = 0
    for line in lines:
        if line.strip() == "":
            continue
        parts = line.split("|")
        ts_raw = parts[0].strip() if parts else ""
        if len(parts) < 4 or not ACTIVITY_TS_RE.match(ts_raw):
            continue
        if parts[1].strip() != "phase:close":
            continue
        verdict = parts[3].strip().upper()
        if verdict == "PASS":
            pass_count += 1
        elif verdict == "BLOCK":
            block_count += 1

    result["pass"] = pass_count
    result["block"] = block_count
    total = pass_count + block_count
    result["ratio"] = round(block_count / total, 4) if total else 0.0
    return result


def extract_audit_log(matrix_root: Path, warnings):
    path = matrix_root / "brain/state/hook-audit.jsonl"
    result = {"bytes": None, "lines": None}
    if not path.is_file():
        warnings.append(f"audit_log: file not found at {path}")
        return result
    result["bytes"] = path.stat().st_size
    result["lines"] = sum(1 for _ in path.read_text(encoding="utf-8").splitlines() if _.strip() != "")
    return result


def extract_activation_throttle(matrix_root: Path, warnings):
    path = matrix_root / "adapters/devin/config.yaml"
    result = {"value": None, "source": str(path.relative_to(matrix_root))}
    value = _read_yaml_boolean(path, "activation_inject_userprompt_full")
    if value is None:
        warnings.append(
            f"activation_throttle: could not read activation_inject_userprompt_full "
            f"from {path}"
        )
        return result
    result["value"] = value
    return result


def extract_lessons(matrix_root: Path, warnings):
    path = matrix_root / "brain/data/lessons.md"
    lines = read_lines(path)
    result = {"total_count": 0, "last_lesson_number": 0}
    if lines is None:
        warnings.append(f"lessons: file not found at {path}")
        return result

    numbers = []
    for line in lines:
        match = LESSON_LINE_RE.match(line)
        if match:
            numbers.append(int(match.group(1)))

    result["total_count"] = len(numbers)
    result["last_lesson_number"] = max(numbers) if numbers else 0
    return result


def extract_validation_report(matrix_root: Path, warnings):
    rel_path = "brain/state/validation-report.json"
    path = matrix_root / rel_path
    result = {"path": rel_path, "exists": False, "raw": {}}
    if not path.is_file():
        warnings.append(f"validation_report: file not found at {path}")
        return result
    result["exists"] = True
    try:
        result["raw"] = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        warnings.append(f"validation_report: failed to parse JSON ({exc})")
        result["raw"] = {}
    return result


def count_nonempty_lines(path: Path, label, warnings):
    lines = read_lines(path)
    if lines is None:
        warnings.append(f"{label}: file not found at {path}")
        return 0
    return sum(1 for line in lines if line.strip() != "")


def build_metrics(matrix_root: Path, since, warnings):
    git_head = run_git(matrix_root, ["rev-parse", "--short", "HEAD"]).strip()
    now = datetime.now(timezone.utc)

    metrics = {
        "snapshot": {
            "generated_at_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "generated_at_epoch": int(now.timestamp()),
            "git_head": git_head,
            "matrix_root": str(matrix_root),
        },
        "datasets": {
            "commits_by_type": extract_commits_by_type(matrix_root, since, warnings),
            "checkpoints": extract_checkpoints(matrix_root, warnings),
            "activity_log": extract_activity_log(matrix_root, warnings),
            "lessons": extract_lessons(matrix_root, warnings),
            "validation_report": extract_validation_report(matrix_root, warnings),
            "harness_cost": {
                "context_bytes": extract_context_bytes(matrix_root, warnings),
                "artifact_counts": extract_artifact_counts(matrix_root),
                "phase_close_verdicts": extract_phase_close_verdicts(matrix_root, warnings),
                "audit_log": extract_audit_log(matrix_root, warnings),
                "activation_throttle": extract_activation_throttle(matrix_root, warnings),
            },
            "routing_signal_history": {
                "total_lines": count_nonempty_lines(
                    matrix_root / "brain/state/routing-signal-history.jsonl",
                    "routing_signal_history",
                    warnings,
                ),
                "note": (
                    "campo mutable en vivo — ver snapshot.generated_at_* para "
                    "el punto de comparación"
                ),
            },
            "orphan_close_attempts": {
                "total_lines": count_nonempty_lines(
                    matrix_root / "brain/state/orphan-close-attempts.jsonl",
                    "orphan_close_attempts",
                    warnings,
                ),
            },
        },
        "warnings": warnings,
    }
    return metrics


def render_markdown(metrics: dict) -> str:
    """Human-readable mirror of the same in-memory dict used for the JSON
    output. Derived, not recomputed."""
    snap = metrics["snapshot"]
    ds = metrics["datasets"]
    lines = []
    lines.append("# Harness health metrics")
    lines.append("")
    lines.append(f"- Generated at (UTC): `{snap['generated_at_utc']}`")
    lines.append(f"- Git HEAD: `{snap['git_head']}`")
    lines.append(f"- Matrix root: `{snap['matrix_root']}`")
    lines.append("")

    lines.append("## Commits by type")
    lines.append("")
    lines.append("| type | count |")
    lines.append("|---|---|")
    for key, value in ds["commits_by_type"].items():
        lines.append(f"| {key} | {value} |")
    lines.append("")

    lines.append("## Checkpoints")
    lines.append("")
    cp = ds["checkpoints"]
    lines.append(f"- total_lines: {cp['total_lines']}")
    lines.append(f"- by_agent: `{json.dumps(cp['by_agent'])}`")
    lines.append(f"- first_ts: {cp['first_ts']}")
    lines.append(f"- last_ts: {cp['last_ts']}")
    lines.append("")

    lines.append("## Activity log")
    lines.append("")
    al = ds["activity_log"]
    lines.append(f"- total_lines: {al['total_lines']}")
    lines.append(f"- first_ts: {al['first_ts']}")
    lines.append(f"- last_ts: {al['last_ts']}")
    lines.append("")
    lines.append("| event_type | count |")
    lines.append("|---|---|")
    for key, value in sorted(al["by_event_type"].items(), key=lambda kv: -kv[1]):
        lines.append(f"| {key} | {value} |")
    lines.append("")

    lines.append("## Lessons")
    lines.append("")
    ls = ds["lessons"]
    lines.append(f"- total_count: {ls['total_count']}")
    lines.append(f"- last_lesson_number: {ls['last_lesson_number']}")
    lines.append("")

    lines.append("## Validation report")
    lines.append("")
    vr = ds["validation_report"]
    lines.append(f"- path: `{vr['path']}`")
    lines.append(f"- exists: {vr['exists']}")
    lines.append(f"- raw: `{json.dumps(vr['raw'])}`")
    lines.append("")

    lines.append("## Harness cost")
    lines.append("")
    hc = ds["harness_cost"]
    cb = hc["context_bytes"]
    lines.append("### Context bytes")
    lines.append("")
    for key, value in cb["files"].items():
        lines.append(f"- {key}: {value}")
    lines.append(f"- trio_total: {cb['trio_total']}")
    lines.append("")
    ac = hc["artifact_counts"]
    lines.append("### Artifact counts")
    lines.append("")
    lines.append(f"- total: {ac['total']}")
    lines.append("")
    if ac["by_subdirectory"]:
        lines.append("| subdirectory | count |")
        lines.append("|---|---|")
        for key, value in sorted(ac["by_subdirectory"].items()):
            lines.append(f"| {key} | {value} |")
        lines.append("")
    pcv = hc["phase_close_verdicts"]
    lines.append("### Phase close verdicts")
    lines.append("")
    lines.append(f"- pass: {pcv['pass']}")
    lines.append(f"- block: {pcv['block']}")
    lines.append(f"- ratio: {pcv['ratio']}")
    lines.append("")
    alog = hc["audit_log"]
    lines.append("### Audit log")
    lines.append("")
    lines.append(f"- bytes: {alog['bytes']}")
    lines.append(f"- lines: {alog['lines']}")
    lines.append("")
    at = hc["activation_throttle"]
    lines.append("### Activation throttle")
    lines.append("")
    lines.append(f"- value: {at['value']}")
    lines.append(f"- source: `{at['source']}`")
    lines.append("")

    lines.append("## Routing signal history")
    lines.append("")
    rsh = ds["routing_signal_history"]
    lines.append(f"- total_lines: {rsh['total_lines']}")
    lines.append(f"- note: {rsh['note']}")
    lines.append("")

    lines.append("## Orphan close attempts")
    lines.append("")
    oca = ds["orphan_close_attempts"]
    lines.append(f"- total_lines: {oca['total_lines']}")
    lines.append("")

    lines.append("## Warnings")
    lines.append("")
    if metrics["warnings"]:
        for warning in metrics["warnings"]:
            lines.append(f"- {warning}")
    else:
        lines.append("(none)")
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, help="Output JSON path")
    parser.add_argument(
        "--since",
        default=None,
        help="Optional git log scoping: an ISO8601 date/duration (passed as "
        "git log --since=<value>) or a git ref/range (passed as "
        "git log <value>..HEAD). Omit for full history.",
    )
    parser.add_argument(
        "--pretty", action="store_true", help="Pretty-print the JSON output"
    )
    parser.add_argument(
        "--out-md", default=None, help="Optional markdown mirror output path"
    )
    parser.add_argument(
        "--emit-ledger-event",
        action="store_true",
        help="Emit a metrics:snapshot Link ledger event via bin/matrix (off by default)",
    )
    args = parser.parse_args()

    script_path = Path(__file__)
    matrix_root = resolve_matrix_root(script_path.parent)

    warnings = []
    metrics = build_metrics(matrix_root, args.since, warnings)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if args.pretty:
        out_path.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    else:
        out_path.write_text(json.dumps(metrics), encoding="utf-8")

    if args.out_md:
        md_path = Path(args.out_md)
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(render_markdown(metrics), encoding="utf-8")

    if args.emit_ledger_event:
        epoch = metrics["snapshot"]["generated_at_epoch"]
        subprocess.run(
            [
                str(matrix_root / "bin/matrix"),
                "link",
                "metrics:snapshot",
                "matrix",
                f"epoch={epoch} path={out_path}",
            ],
            cwd=str(matrix_root),
            check=False,
        )


if __name__ == "__main__":
    main()
