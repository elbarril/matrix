#!/usr/bin/env python3
"""Seraph · post_run_audit — compliance, bypass, and Smith-remediation detection.

After a run, verifies the enforced steps were executed, writes
``brain/state/validation-report.json``, and flags non-compliant or bypassed
activations. Besides the existing input (``agent``, ``steps``, and optional
``required``), it accepts optional ``profile``, ``session_id``,
``eval_artifact``, ``edited_paths``, and ``since`` keys.

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
tier2_review_predates_fix, fix_not_one_sentence, since_unparseable,
since_after_prereg, and file_containment_violated.

Edited paths are the union of caller declaration and matching audit-log edit
events. When the host does not expose inner-subagent events, attribution is
self-report-only rather than an invented observation. Session-scoped observed
edits without profile metadata are conservatively attributed to Smith; a
``since`` window narrows that known false-positive mode.
"""

import datetime
import json
import os

from _common import current_session_id, emit, read_input, resolve_root

REQUIRED_STEPS = ["load_config", "resolve_context", "pre_activation_check"]
SMITH_ALIASES = {"smith", "agent smith", "agent_smith"}
EDIT_TOOLS = {"edit", "multi_edit", "write"}


def _is_smith(value):
    return str(value or "").strip().lower() in SMITH_ALIASES


def _parse_time(value):
    if not isinstance(value, str):
        raise ValueError("not a string")
    parsed = datetime.datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.datetime.now().astimezone().tzinfo)
    return parsed


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


def _observed_edits(root, session_id, since):
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
            if since is not None:
                try:
                    if _parse_time(event.get("timestamp")) < since:
                        continue
                except ValueError:
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
    declared = {_normalize_path(root, p) for p in (data.get("edited_paths") or []) if isinstance(p, str)}
    observed, bad_lines, profile_scoped, any_events = _observed_edits(root, session_id, since)
    evaluated = declared | observed
    if not evaluated:
        return True, {"checked": True, "ok": True, "verdict": "no-edits", "edit_signal": "none", "attribution": "no-session-id" if not session_id else "self-report-only", "eval_artifact": None, "declared_paths": sorted(declared), "observed_paths": sorted(observed), "evaluated_paths": [], "since": since_raw, "findings": [], "reasons": [], "warnings": [], "audit_log_unparseable_lines": bad_lines}
    if declared and observed:
        signal = "declared+observed"
    elif declared:
        signal = "declared"
    else:
        signal = "observed"
    attribution = "no-session-id" if not session_id else ("profile-scoped" if profile_scoped else ("session-scoped" if any_events else "self-report-only"))
    artifact_input = data.get("eval_artifact")
    block = {"checked": True, "ok": False, "verdict": "non-compliant", "edit_signal": signal, "attribution": attribution, "eval_artifact": None, "declared_paths": sorted(declared), "observed_paths": sorted(observed), "evaluated_paths": sorted(evaluated), "since": since_raw, "findings": [], "reasons": reasons, "warnings": warnings, "audit_log_unparseable_lines": bad_lines}
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
    ids, declared_files, before_times = set(), set(), []
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
    if since is not None and before_times and since > min(before_times):
        reasons.append("since_after_prereg")
    for path in sorted(evaluated - declared_files):
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
    smith_ok, smith_block = check_smith_remediation(root, data, session_id)
    compliant = (not missing) and smith_ok
    report = {"hook": "post_run_audit", "ok": compliant, "agent": agent, "profile": profile, "session_id": session_id, "timestamp": datetime.datetime.now().astimezone().isoformat(), "steps_seen": steps, "required": required, "missing": missing, "bypass_suspected": bool(bypass), "compliant": compliant, "smith_remediation": smith_block}
    state_dir = os.path.join(root, "brain", "state")
    os.makedirs(state_dir, exist_ok=True)
    with open(os.path.join(state_dir, "validation-report.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    emit(report)


if __name__ == "__main__":
    main()
