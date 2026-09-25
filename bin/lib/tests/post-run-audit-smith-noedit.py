#!/usr/bin/env python3
"""B — Smith remediation gate without repo edits is no-edits/compliant (P2).

A Smith gate that only wrote its eval artifact (and throwaway scripts in /tmp)
must fall into the no-edits branch and stay compliant; an actual in-root edit
without a valid prereg block must stay non-compliant; an in-root edit WITH a
valid MATRIX:EVAL-PREREG v1 block must be compliant.

Cases:
(a) audit log: write -> /tmp/repro.py, write -> brain/output/eval/<x>.md,
    payload agent:smith + eval_artifact -> smith_remediation.verdict ==
    "no-edits", edit_signal == "none", ok == true, /tmp/... in
    observed_outside_root and NOT in observed_paths/evaluated_paths.
(b) audit log: edit -> hooks/post_run_audit.py (inside root), eval artifact
    WITHOUT a prereg block -> verdict == "non-compliant", ok == false, reason
    prereg_block_absent / file_containment_violated. (the gate is NOT relaxed)
(c) audit log: edit inside root + eval artifact with a valid
    MATRIX:EVAL-PREREG v1 block (matching session_id, findings with
    before-fail/after-pass, increasing timestamps) -> verdict == "compliant",
    ok == true. (schema: docstring of hooks/post_run_audit.py lines 10-17)
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


smoke_path = Path(__file__).resolve().parent / "smoke-matrix-help.py"
spec = importlib.util.spec_from_file_location("smoke_matrix_help", smoke_path)
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


REPO_ROOT = smoke.repo_root_from_script()
REQUIRED_STEPS = ["load_config", "resolve_context", "pre_activation_check"]


def run_hook(fixture_root, home_dir, payload):
    hook = fixture_root / "hooks" / "post_run_audit.py"
    env = os.environ.copy()
    env["MATRIX_ROOT"] = str(fixture_root)
    env["HOME"] = str(home_dir)
    env["SOURCE_DATE_EPOCH"] = "1704067200"
    env["TZ"] = "UTC"
    return subprocess.run(
        ["python3", str(hook), json.dumps(payload)],
        cwd=str(fixture_root),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


def write_audit(fixture_root, session_id, events):
    log = fixture_root / "brain" / "state" / "hook-audit.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")


def write_eval_artifact(fixture_root, rel_path, body):
    path = fixture_root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def smith_payload(session_id, artifact_rel):
    return {
        "agent": "smith",
        "profile": "smith",
        "session_id": session_id,
        "steps": list(REQUIRED_STEPS),
        "eval_artifact": artifact_rel,
    }


def case_no_edits_is_no_edits_compliant():
    with tempfile.TemporaryDirectory(prefix="p2a-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        session_id = "p2a"
        artifact_rel = "brain/output/eval/p2a.md"
        write_eval_artifact(fixture_root, artifact_rel, "# p2a eval\n")
        write_audit(fixture_root, session_id, [
            {"event": "post_tool_use", "session_id": session_id,
             "tool_name": "write", "tool_paths": ["/tmp/repro.py"],
             "timestamp": "2026-01-01T00:00:01+00:00"},
            {"event": "post_tool_use", "session_id": session_id,
             "tool_name": "write", "tool_paths": [artifact_rel],
             "timestamp": "2026-01-01T00:00:02+00:00"},
        ])
        proc = run_hook(fixture_root, home_dir, smith_payload(session_id, artifact_rel))
        result = json.loads(proc.stdout)
        smith = result["smith_remediation"]
        assert proc.returncode == 0, f"expected exit 0, got {proc.returncode}: {proc.stdout}"
        assert result["ok"] is True, f"expected ok:true: {result}"
        assert smith["verdict"] == "no-edits", smith
        assert smith["edit_signal"] == "none", smith
        assert smith["evaluated_paths"] == [], smith
        assert "/tmp/repro.py" in smith["observed_outside_root"], smith
        assert "/tmp/repro.py" not in smith["observed_paths"], smith
        assert smith["eval_artifact"] is not None and str(smith["eval_artifact"]).endswith(artifact_rel), smith
        print("B NO-EDITS IS NO-EDITS COMPLIANT PASS")


def case_in_root_edit_without_prereg_stays_non_compliant():
    with tempfile.TemporaryDirectory(prefix="p2b-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        session_id = "p2b"
        artifact_rel = "brain/output/eval/p2b.md"
        write_eval_artifact(fixture_root, artifact_rel, "# p2b eval\nNo prereg block.\n")
        write_audit(fixture_root, session_id, [
            {"event": "post_tool_use", "session_id": session_id,
             "tool_name": "edit", "tool_paths": ["hooks/post_run_audit.py"],
             "timestamp": "2026-01-01T00:00:01+00:00"},
        ])
        proc = run_hook(fixture_root, home_dir, smith_payload(session_id, artifact_rel))
        result = json.loads(proc.stdout)
        smith = result["smith_remediation"]
        assert proc.returncode == 1, f"expected exit 1, got {proc.returncode}: {proc.stdout}"
        assert result["ok"] is False, f"expected ok:false: {result}"
        assert smith["verdict"] == "non-compliant", smith
        reasons = " ".join(smith["reasons"])
        assert "prereg_block_absent" in reasons or "file_containment_violated" in reasons, smith
        assert "hooks/post_run_audit.py" in smith["evaluated_paths"], smith
        print("B IN-ROOT EDIT WITHOUT PREREG STAYS NON-COMPLIANT PASS")


def _valid_prereg_block(session_id, edited_rel):
    finding = {
        "id": "P2C-1",
        "tier": 1,
        "one_sentence_fix": "Fix the false non-compliant Smith gate.",
        "files": [edited_rel],
        "before": {
            "command": "python3 bin/lib/tests/post-run-audit-smith-noedit.py",
            "recorded_at": "2026-01-01T00:00:01+00:00",
            "exit_code": 1,
            "output": "FAIL: prereg_block_absent",
        },
        "after": {
            "command": "python3 bin/lib/tests/post-run-audit-smith-noedit.py",
            "recorded_at": "2026-01-01T00:00:02+00:00",
            "exit_code": 0,
            "output": "PASS: compliant",
        },
    }
    payload = {
        "prereg_version": 1,
        "agent": "smith",
        "session_id": session_id,
        "findings": [finding],
    }
    return (
        "<!-- MATRIX:EVAL-PREREG v1 -->\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
        + "\n<!-- MATRIX:EVAL-PREREG END -->\n"
    )


def case_in_root_edit_with_valid_prereg_compliant():
    with tempfile.TemporaryDirectory(prefix="p2c-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        session_id = "p2c"
        edited_rel = "hooks/post_run_audit.py"
        artifact_rel = "brain/output/eval/p2c.md"
        write_eval_artifact(
            fixture_root, artifact_rel, _valid_prereg_block(session_id, edited_rel)
        )
        write_audit(fixture_root, session_id, [
            {"event": "post_tool_use", "session_id": session_id,
             "tool_name": "edit", "tool_paths": [edited_rel],
             "timestamp": "2026-01-01T00:00:01+00:00"},
        ])
        proc = run_hook(fixture_root, home_dir, smith_payload(session_id, artifact_rel))
        result = json.loads(proc.stdout)
        smith = result["smith_remediation"]
        assert proc.returncode == 0, f"expected exit 0, got {proc.returncode}: {proc.stdout}"
        assert result["ok"] is True, f"expected ok:true: {result}"
        assert smith["verdict"] == "compliant", smith
        assert smith["reasons"] == [], smith
        assert smith["warnings"] == [], smith
        print("B IN-ROOT EDIT WITH VALID PREREG COMPLIANT PASS")


def main():
    assert REPO_ROOT != Path("/tmp").resolve(), "repo root must not be /tmp"
    case_no_edits_is_no_edits_compliant()
    case_in_root_edit_without_prereg_stays_non_compliant()
    case_in_root_edit_with_valid_prereg_compliant()
    print("B POST-RUN-AUDIT SMITH-NOEDIT ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
