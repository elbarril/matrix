#!/usr/bin/env python3
"""Seraph · post_run_audit — compliance, bypass, and Smith-remediation detection.

After a run, verifies the enforced steps were executed, writes
``brain/state/validation-report.json``, and flags non-compliant or bypassed
activations. Besides the existing input (``agent``, ``steps``, and optional
``required``), it accepts optional ``profile``, ``session_id``,
``eval_artifact``, ``edited_paths``, ``since``, and ``until`` keys.

A Smith-profile run with edits must point to an eval artifact containing one
``<!-- MATRIX:EVAL-PREREG v1 -->`` JSON block, terminated by
``<!-- MATRIX:EVAL-PREREG END -->``. Its JSON has ``prereg_version: 1``,
``agent: smith``, the audited ``session_id``, and non-empty ``findings``. Each
finding declares an id, tier, one-line fix, files, and before/after evidence.
The commands must be byte-identical; before must fail, after must pass, their
non-empty outputs must differ, and ISO-8601 evidence timestamps must increase.
Tier 3 is forbidden; Tier 2 requires an Architect review after the fix.

Reason codes include prereg_block_absent, prereg_block_unterminated,
prereg_block_duplicated, prereg_block_malformed, prereg_version_unsupported,
prereg_session_mismatch, check_command_mutated, before_not_failing,
after_not_passing, output_empty, output_unchanged, evidence_out_of_order,
tier3_self_fixed, tier2_review_missing, tier2_review_wrong_reviewer,
tier2_review_predates_fix, fix_not_one_sentence, since_unparseable, since_after_prereg,
until_unparseable, until_before_since, until_before_prereg,
and file_containment_violated.

Edited paths are the union of caller declaration and matching audit-log edit
events. When the host does not expose inner-subagent events, attribution is
self-report-only rather than an invented observation. Session-scoped observed
edits without profile metadata are conservatively attributed to Smith; a closed
``[since, until]`` window narrows that known false-positive mode, because
``session_id`` identifies the host session (verified to span ~38 h), not the
run being audited.

The eval artifact is always excluded from ``observed``/``declared`` before the
``evaluated`` set is computed: it is the *report*, never a *fix*, so a gate that
only wrote its artifact (and throwaway scripts) must not be flagged as a
mutating Smith run. Observed edits whose normalized path is absolute (outside
this root) are likewise excluded from ``evaluated`` and surfaced separately in
``observed_outside_root``. Accepted trade-off: this gate protects the integrity
of THIS root; a Smith edit outside it (a detached worktree, /tmp scripts) is
invisible to the remediation gate by design -- a real worktree remediation is a
separate design question, not an ad-hoc ``git rev-parse`` here.

Shell mutation detection is intentionally duplicated with pre_exec_guard;
the two hooks have a diverging fail policy — see the other module.
"""

import datetime
import json
import os
import shlex

from _common import current_session_id, emit, read_input, resolve_root

REQUIRED_STEPS = ["load_config", "resolve_context", "pre_activation_check"]
SMITH_ALIASES = {"smith", "agent smith", "agent_smith"}
EDIT_TOOLS = {"edit", "multi_edit", "write"}
MUTANT_TOOL_NAMES = {"exec", "run_command", "run-command"}
ALLOWED_MUTANT_PREFIX = "bin/matrix corpus-ingest"
_WRITE_ALL_ARGS = {"rm", "rmdir", "truncate", "tee"}
_WRITE_LAST_ARG = {"mv", "cp"}
_CONTROL_OPS = {";", "&&", "||", "|", "&"}
_WRITE_HINTS = (">", ">>", "tee ", "rm ", "rmdir ", "mv ", "cp ", "truncate ", "sed -i")


def _is_smith(value):
    return str(value or "").strip().lower() in SMITH_ALIASES


def _strip_heredocs(command):
    """Return the command's shell lines with heredoc bodies removed.

    A heredoc body is data, not shell syntax: an eval artifact written with
    `cat > path << 'EOF'` carries prose that must never reach the tokenizer
    (a `>` inside a sentence is not a redirection). Delimiter forms handled:
    << EOF, <<- EOF, << 'EOF', << "EOF".
    """
    lines, out, i = command.splitlines(), [], 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        marker = None
        idx = line.find("<<")
        if idx != -1 and not line[idx:].startswith("<<<"):
            rest = line[idx + 2:].lstrip()
            if rest.startswith("-"):
                rest = rest[1:].lstrip()
            token = rest.split()[0] if rest.split() else ""
            marker = token.strip("'\"") or None
        i += 1
        if marker:
            while i < len(lines) and lines[i].strip() != marker:
                i += 1
            i += 1  # skip the terminating delimiter line
    return out


def _lexical_chunks(lines):
    """Group physical shell lines into minimal chunks that shlex can parse.

    A shell command is ONE lexical unit even when it spans several physical
    lines: a quote opened on line 1 and closed on line 7 is valid syntax, not
    garbage. Tokenizing line-by-line reported `python3 -c "` as unparseable
    write intent and fail-closed on a command whose only target was /tmp.

    shlex is the oracle for "is a quote still open" -- a ValueError means the
    chunk is incomplete, so the next line is appended and the parse retried.
    Nothing here re-implements shell lexing on purpose (Foundation 4).

    Returns a list of (text, tokens) pairs. `tokens` is None when the chunk
    never parsed (unterminated quote through the end of the command), leaving
    the fail-closed policy of the caller in charge.
    """
    chunks, buffer = [], None
    for line in lines:
        buffer = line if buffer is None else buffer + "\n" + line
        try:
            tokens = shlex.split(buffer)
        except ValueError:
            continue
        chunks.append((buffer, tokens))
        buffer = None
    if buffer is not None:
        chunks.append((buffer, None))
    return chunks


def _write_targets(command, root):
    """Return parsed write targets and whether write intent could not be parsed.

    A shell command is a single lexical unit even across physical lines; see
    `_lexical_chunks`. Order of operations: strip heredocs, chunk by quotable
    lines, tokenize each chunk. This detective tokenizer intentionally
    duplicates pre_exec_guard but fails closed on unparseable write intent;
    the preventive guard fails open to avoid blocking on uncertainty.
    """
    targets = []
    unparsed = False
    for text, tokens in _lexical_chunks(_strip_heredocs(command)):
        if tokens is None:
            if any(hint in text for hint in _WRITE_HINTS):
                unparsed = True
            continue
        for i, token in enumerate(tokens):
            if token in (">", ">>") and i + 1 < len(tokens):
                targets.append(tokens[i + 1])
        segments, segment = [], []
        for token in tokens:
            if token in _CONTROL_OPS:
                if segment:
                    segments.append(segment)
                segment = []
            else:
                segment.append(token)
        if segment:
            segments.append(segment)
        for segment in segments:
            verb = segment[0]
            args = segment[1:]
            if verb in _WRITE_ALL_ARGS:
                targets.extend(arg for arg in args if not arg.startswith("-"))
            elif verb in _WRITE_LAST_ARG and args:
                targets.append(args[-1])
            elif verb == "git" and args and args[0] == "rm":
                targets.extend(arg for arg in args[1:] if not arg.startswith("-"))
            elif verb == "sed" and any(arg == "-i" or arg.startswith("-i.") or arg == "--in-place" for arg in args):
                targets.extend(arg for arg in args if not arg.startswith("-"))
    return targets, unparsed


def _anomalous_mutant_commands(root, session_id, since, sanctioned=None, until=None):
    """Return shell commands in this session that wrote to a repo path outside
    the sanctioned set.

    Detective check, not a preventive guard (that is pre_exec_guard). Four
    classes are NOT anomalies, by design:
      * commands outside the audited [since, until] window -- events that cannot
        be attributed to the run in time must not be attributed to Smith;
      * read-only commands (no write token at all) -- reproduction is required
        of Smith by its own <rules>;
      * writes whose target resolves outside the Matrix root (/tmp, /dev/null):
        out of scope, this check protects repo integrity, not the filesystem;
      * writes to a path already in `sanctioned` -- the declared + pre-registered
        paths of this same run, which is how Smith's own eval artifact is
        created via shell redirection per its <boundaries>.
    A write to any other repo path is the mutant this check was written for
    (see brain/subsystems/logos/agents/niobe.md: never ad-hoc redirection).
    """
    sanctioned = set(sanctioned or ())
    anomalies = []
    if not session_id:
        return anomalies
    log_path = os.path.join(root, "brain", "state", "hook-audit.jsonl")
    if not os.path.isfile(log_path):
        return anomalies
    try:
        fh = open(log_path, encoding="utf-8")
    except OSError:
        return anomalies
    with fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if event.get("event") != "post_tool_use" or event.get("session_id") != session_id:
                continue
            if event.get("tool_name") not in MUTANT_TOOL_NAMES:
                continue
            if not _in_window(event.get("timestamp"), since, until):
                continue
            targets = event.get("tool_paths") or []
            unparsed = event.get("tool_command_unparsed") is True
            head = event.get("tool_command_head") or ""
            if unparsed:
                anomalies.append(head)
                continue
            offending = False
            for target in targets:
                norm = _normalize_path(root, target)
                if os.path.isabs(norm):
                    continue
                if norm not in sanctioned:
                    offending = True
                    break
            if offending:
                anomalies.append(head)
    return anomalies


def _parse_time(value):
    if not isinstance(value, str):
        raise ValueError("not a string")
    parsed = datetime.datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.datetime.now().astimezone().tzinfo)
    return parsed


def _in_window(timestamp, since, until):
    """Return True when `timestamp` falls inside the closed interval [since, until].

    Bounds are optional: a None bound is no bound on that side. The interval is
    inclusive on both ends. An event whose timestamp cannot be parsed is OUT of
    the window by construction -- an event that cannot be placed in time cannot
    be attributed to a run, and attributing it anyway is the false attribution
    this amendment exists to remove (Foundation 3).
    """
    if since is None and until is None:
        return True
    try:
        moment = _parse_time(timestamp)
    except ValueError:
        return False
    if since is not None and moment < since:
        return False
    if until is not None and moment > until:
        return False
    return True


def _normalize_path(root, path):
    absolute = os.path.abspath(path if os.path.isabs(path) else os.path.join(root, path))
    relative = os.path.normpath(os.path.relpath(absolute, root))
    return absolute if relative == ".." or relative.startswith(".." + os.sep) else relative


def _read_prereg(path):
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.readlines()
    except OSError:
        return None, "prereg_block_absent"
    starts = [i for i, line in enumerate(lines) if line.strip() == "<!-- MATRIX:EVAL-PREREG v1 -->"]
    if not starts:
        return None, "prereg_block_absent"
    if len(starts) > 1:
        return None, "prereg_block_duplicated"
    start = starts[0]
    end = next((i for i in range(start + 1, len(lines)) if lines[i].strip() == "<!-- MATRIX:EVAL-PREREG END -->"), None)
    if end is None:
        return None, "prereg_block_unterminated"
    payload = "\n".join(line.rstrip("\n") for line in lines[start + 1:end] if not line.strip().startswith("```"))
    try:
        return json.loads(payload), None
    except ValueError as exc:
        return None, "prereg_block_malformed: " + str(exc)


def _observed_edits(root, session_id, since, until=None):
    paths, unparseable, profile_scoped, any_events = set(), 0, False, False
    if not session_id:
        return paths, unparseable, profile_scoped, any_events
    log_path = os.path.join(root, "brain", "state", "hook-audit.jsonl")
    try:
        fh = open(log_path, encoding="utf-8")
    except OSError:
        return paths, unparseable, profile_scoped, any_events
    with fh:
        for line in fh:
            try:
                event = json.loads(line)
            except ValueError:
                unparseable += 1
                continue
            if event.get("event") != "post_tool_use" or event.get("session_id") != session_id or event.get("tool_name") not in EDIT_TOOLS:
                continue
            if not _in_window(event.get("timestamp"), since, until):
                continue
            event_profile = event.get("subagent_profile")
            if event_profile:
                if not _is_smith(event_profile):
                    continue
                profile_scoped = True
            any_events = True
            for path in event.get("tool_paths") or []:
                if isinstance(path, str):
                    paths.add(_normalize_path(root, path))
    return paths, unparseable, profile_scoped, any_events


def _finding_check(finding):
    fid = finding.get("id") if isinstance(finding, dict) else None
    label = str(fid) if isinstance(fid, str) and fid else "<missing>"
    reasons = []
    if not isinstance(finding, dict) or not isinstance(fid, str) or not fid:
        reasons.append("finding_id_invalid: " + label)
    tier = finding.get("tier") if isinstance(finding, dict) else None
    if not isinstance(tier, int) or tier not in (1, 2, 3):
        reasons.append("tier_invalid: " + label)
    elif tier == 3:
        reasons.append("tier3_self_fixed: " + label)
    fix = finding.get("one_sentence_fix") if isinstance(finding, dict) else None
    if not isinstance(fix, str) or not fix.strip() or "\n" in fix or "\r" in fix:
        reasons.append("fix_not_one_sentence: " + label)
    files = finding.get("files") if isinstance(finding, dict) else None
    if not isinstance(files, list) or not files or not all(isinstance(p, str) and p for p in files):
        reasons.append("files_invalid: " + label)
    before, after = finding.get("before"), finding.get("after")
    if not isinstance(before, dict) or not isinstance(after, dict):
        reasons.append("evidence_invalid: " + label)
        return {"id": fid, "tier": tier, "ok": False, "reasons": reasons}, reasons
    for evidence in (before, after):
        if not all(key in evidence for key in ("command", "recorded_at", "exit_code", "output")):
            reasons.append("evidence_invalid: " + label)
            break
    if before.get("command") != after.get("command") or not isinstance(before.get("command"), str) or not before.get("command"):
        reasons.append("check_command_mutated: " + label)
    if not isinstance(before.get("exit_code"), int) or before.get("exit_code") == 0:
        reasons.append("before_not_failing: " + label)
    if not isinstance(after.get("exit_code"), int) or after.get("exit_code") != 0:
        reasons.append("after_not_passing: " + label)
    if not isinstance(before.get("output"), str) or not before.get("output").strip() or not isinstance(after.get("output"), str) or not after.get("output").strip():
        reasons.append("output_empty: " + label)
    elif before.get("output") == after.get("output"):
        reasons.append("output_unchanged: " + label)
    try:
        before_time, after_time = _parse_time(before.get("recorded_at")), _parse_time(after.get("recorded_at"))
        if after_time <= before_time:
            reasons.append("evidence_out_of_order: " + label)
    except ValueError:
        reasons.append("recorded_at_unparseable: " + label)
        before_time = None
    review = finding.get("tier2_review")
    if tier == 2:
        if not isinstance(review, dict):
            reasons.append("tier2_review_missing: " + label)
        else:
            reviewer = review.get("reviewer")
            if not isinstance(reviewer, str) or reviewer.strip().lower() != "architect":
                reasons.append("tier2_review_wrong_reviewer: " + label + ": " + str(reviewer))
            try:
                if before_time is not None and _parse_time(review.get("reviewed_at")) < after_time:
                    reasons.append("tier2_review_predates_fix: " + label)
            except ValueError:
                reasons.append("tier2_review_predates_fix: " + label)
    return {"id": fid, "tier": tier, "ok": not reasons, "reasons": reasons}, reasons


def check_smith_remediation(root, data, session_id):
    profile = data.get("profile") or data.get("agent")
    if not _is_smith(profile):
        return True, {"checked": False, "ok": True, "verdict": "not-applicable", "reasons": [], "warnings": []}
    reasons, warnings = [], []
    since_raw = data.get("since")
    try:
        since = _parse_time(since_raw) if since_raw is not None else None
    except ValueError:
        since = None
        reasons.append("since_unparseable: " + str(since_raw))
    until_raw = data.get("until")
    try:
        until = _parse_time(until_raw) if until_raw is not None else None
    except ValueError:
        until = None
        reasons.append("until_unparseable: " + str(until_raw))
    # Resolve the eval-artifact candidate BEFORE _observed_edits / evaluated
    # (Architect P2 hoist): the eval artifact is the *report*, never a *fix*,
    # so it must never be what trips the pre-registration requirement no matter
    # how it was created. Excluding it from `evaluated` keeps a gate that only
    # wrote its artifact (and throwaway scripts) in the no-edits branch.
    artifact_input = data.get("eval_artifact")
    eval_candidates = (
        {os.path.abspath(artifact_input)}
        if artifact_input and os.path.isabs(artifact_input)
        else {os.path.join(root, artifact_input), os.path.join(os.getcwd(), artifact_input)}
        if artifact_input else set()
    )
    eval_paths = {_normalize_path(root, c) for c in eval_candidates}
    if since is not None and until is not None and until < since:
        reasons.append("until_before_since: " + str(until_raw) + " < " + str(since_raw))
    observed, bad_lines, profile_scoped, any_events = _observed_edits(root, session_id, since, until)
    observed_inside = {p for p in observed if not os.path.isabs(p)}
    observed_outside = observed - observed_inside
    observed_inside = observed_inside - eval_paths
    declared = {_normalize_path(root, p) for p in (data.get("edited_paths") or []) if isinstance(p, str)}
    declared = declared - eval_paths
    evaluated = declared | observed_inside
    if not evaluated:
        artifact = next((os.path.abspath(c) for c in eval_candidates if os.path.isfile(c)), None)
        return (not reasons), {"checked": True, "ok": (not reasons),
                               "verdict": "no-edits" if not reasons else "non-compliant",
                               "edit_signal": "none",
                               "attribution": "no-session-id" if not session_id else "self-report-only",
                               "eval_artifact": artifact, "declared_paths": sorted(declared),
                               "observed_paths": sorted(observed_inside), "evaluated_paths": [],
                               "observed_outside_root": sorted(observed_outside),
                               "since": since_raw, "until": until_raw, "findings": [],
                               "reasons": reasons, "warnings": warnings,
                               "audit_log_unparseable_lines": bad_lines}
    if declared and observed_inside:
        signal = "declared+observed"
    elif declared:
        signal = "declared"
    else:
        signal = "observed"
    attribution = "no-session-id" if not session_id else ("profile-scoped" if profile_scoped else ("session-scoped" if any_events else "self-report-only"))
    block = {"checked": True, "ok": False, "verdict": "non-compliant", "edit_signal": signal, "attribution": attribution, "eval_artifact": None, "declared_paths": sorted(declared), "observed_paths": sorted(observed_inside), "evaluated_paths": sorted(evaluated), "observed_outside_root": sorted(observed_outside), "since": since_raw, "until": until_raw, "findings": [], "reasons": reasons, "warnings": warnings, "audit_log_unparseable_lines": bad_lines}
    if not artifact_input:
        reasons.append("eval_artifact_missing")
        return False, block
    candidates = [artifact_input] if os.path.isabs(artifact_input) else [os.path.join(os.getcwd(), artifact_input), os.path.join(root, artifact_input)]
    artifact = next((path for path in candidates if os.path.isfile(path)), None)
    if not artifact:
        reasons.append("eval_artifact_not_found: " + str(artifact_input))
        return False, block
    block["eval_artifact"] = os.path.abspath(artifact)
    prereg, parse_reason = _read_prereg(artifact)
    if parse_reason:
        reasons.append(parse_reason)
        return False, block
    if not isinstance(prereg, dict):
        reasons.append("prereg_block_malformed: root is not an object")
        return False, block
    version = prereg.get("prereg_version")
    if version != 1:
        reasons.append("prereg_version_unsupported: " + str(version))
    if not _is_smith(prereg.get("agent")):
        reasons.append("prereg_agent_invalid")
    if session_id and prereg.get("session_id") != session_id:
        reasons.append("prereg_session_mismatch")
    findings = prereg.get("findings")
    if not isinstance(findings, list) or not findings:
        reasons.append("findings_empty")
        findings = []
    ids, declared_files, before_times, after_times = set(), set(), [], []
    for finding in findings:
        result, finding_reasons = _finding_check(finding)
        block["findings"].append(result)
        reasons.extend(finding_reasons)
        fid = finding.get("id") if isinstance(finding, dict) else None
        if isinstance(fid, str) and fid:
            if fid in ids:
                reasons.append("finding_id_duplicated: " + fid)
            ids.add(fid)
        if isinstance(finding, dict):
            for path in finding.get("files") or []:
                if isinstance(path, str):
                    declared_files.add(_normalize_path(root, path))
            try:
                before_times.append(_parse_time(finding.get("before", {}).get("recorded_at")))
            except ValueError:
                pass
            try:
                after_times.append(_parse_time(finding.get("after", {}).get("recorded_at")))
            except ValueError:
                pass
    if since is not None and before_times and since > min(before_times):
        reasons.append("since_after_prereg")
    if until is not None and after_times and until < max(after_times):
        reasons.append("until_before_prereg")
    eval_path = _normalize_path(root, block["eval_artifact"]) if block.get("eval_artifact") else None
    for path in sorted(evaluated - declared_files):
        if path == eval_path:
            continue
        reasons.append("file_containment_violated: " + path)
    for path in sorted(declared_files - evaluated):
        warnings.append("declared_file_untouched: " + path)
    block["ok"] = not reasons
    block["verdict"] = "compliant" if block["ok"] else "non-compliant"
    return block["ok"], block


def main():
    data = read_input()
    root = resolve_root()
    steps = [str(s) for s in (data.get("steps") or [])]
    agent = data.get("agent")
    profile = data.get("profile") or agent
    session_id = data.get("session_id") or current_session_id(root)
    required = [str(s) for s in data.get("required")] if data.get("required") else REQUIRED_STEPS
    missing = [s for s in required if s not in steps]
    bypass = bool(steps) and missing
    since_raw = data.get("since")
    try:
        since = _parse_time(since_raw) if since_raw is not None else None
    except ValueError:
        since = None
    until_raw = data.get("until")
    try:
        until = _parse_time(until_raw) if until_raw is not None else None
    except ValueError:
        until = None
    smith_ok, smith_block = check_smith_remediation(root, data, session_id)
    sanctioned = set(smith_block.get("evaluated_paths") or ())
    if smith_block.get("eval_artifact"):
        sanctioned.add(_normalize_path(root, smith_block["eval_artifact"]))
    mutant_anomalies = _anomalous_mutant_commands(root, session_id, since, sanctioned, until)
    compliant = (not missing) and smith_ok and not mutant_anomalies
    report = {"hook": "post_run_audit", "ok": compliant, "agent": agent, "profile": profile, "session_id": session_id, "timestamp": datetime.datetime.now().astimezone().isoformat(), "steps_seen": steps, "required": required, "missing": missing, "bypass_suspected": bool(bypass), "compliant": compliant, "smith_remediation": smith_block, "mutant_command_anomalies": mutant_anomalies}
    state_dir = os.path.join(root, "brain", "state")
    os.makedirs(state_dir, exist_ok=True)
    with open(os.path.join(state_dir, "validation-report.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    # D3: per-session authoritative report (same payload). Only written when a
    # reliable session_id exists; otherwise only the global slot is written and
    # the smith_remediation block already emits attribution: no-session-id.
    if session_id:
        sessions_dir = os.path.join(state_dir, "sessions")
        os.makedirs(sessions_dir, exist_ok=True)
        with open(
            os.path.join(sessions_dir, f"{session_id}-validation-report.json"),
            "w", encoding="utf-8",
        ) as fh:
            json.dump(report, fh, ensure_ascii=False, indent=2)
    emit(report)


if __name__ == "__main__":
    main()
