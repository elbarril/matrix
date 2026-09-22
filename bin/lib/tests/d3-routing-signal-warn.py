#!/usr/bin/env python3
"""D3 — validate_phase_close strict validation + routing-signal escalation warn.

Positive: a CURRENT session that is actually triggered (recomputed) with >=2
prior unresolved sessions in history produces one routing_signal_escalation warn.
Negatives: no history, history from other sessions, a resolved current session,
and a missing session_id never warn; validator/precheck never write history.
Strict gate: e2e must be JSON true; non-object/type-invalid payloads BLOCK with
a controlled JSON error (no traceback).
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


def run_hook(fixture_root, env, payload):
    hook = fixture_root / "hooks" / "validate_phase_close.py"
    return subprocess.run(
        ["python3", str(hook), payload],
        cwd=str(fixture_root),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def fixture_env(fixture_root):
    env = os.environ.copy()
    env["MATRIX_ROOT"] = str(fixture_root)
    env["SOURCE_DATE_EPOCH"] = "1704067200"
    env["TZ"] = "UTC"
    return env


def write_history(fixture_root, records):
    hist = fixture_root / "brain" / "state" / "routing-signal-history.jsonl"
    hist.parent.mkdir(parents=True, exist_ok=True)
    hist.write_text(
        "".join(json.dumps(r) + "\n" for r in records),
        encoding="utf-8",
    )


def write_audit(fixture_root, session_id):
    log = fixture_root / "brain" / "state" / "hook-audit.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    entries = [
        {"event": "session_start", "session_id": session_id,
         "pre_activation_check_ok": True, "timestamp": "2026-01-01T00:00:00+00:00"},
        {"event": "post_tool_use", "session_id": session_id,
         "tool_name": "edit", "tool_paths": ["docs/a.md"],
         "timestamp": "2026-01-01T00:00:01+00:00"},
        {"event": "post_tool_use", "session_id": session_id,
         "tool_name": "edit", "tool_paths": ["docs/b.md"],
         "timestamp": "2026-01-01T00:00:02+00:00"},
    ]
    log.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")


def write_activity(fixture_root, line):
    log = fixture_root / "brain" / "state" / "activity.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(line + "\n", encoding="utf-8")


def history_text(fixture_root):
    hist = fixture_root / "brain" / "state" / "routing-signal-history.jsonl"
    return hist.read_text(encoding="utf-8") if hist.is_file() else None


def case_positive():
    with tempfile.TemporaryDirectory(prefix="d3-positive-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        env = fixture_env(fixture_root)
        env["HOME"] = str(home_dir)
        write_audit(fixture_root, "s3")
        write_history(fixture_root, [
            {"session_id": "s1", "triggered": True, "resolved": "triggered",
             "timestamp": "2026-01-01T00:00:00+00:00"},
            {"session_id": "s2", "triggered": True, "resolved": "triggered",
             "timestamp": "2026-01-01T00:00:01+00:00"},
        ])
        payload = '{"phase":"develop","e2e":true,"evidence":"ran d3 positive","session_id":"s3"}'
        proc = run_hook(fixture_root, env, payload)
        result = json.loads(proc.stdout)
        assert proc.returncode == 0, f"expected exit 0, got {proc.returncode}: {proc.stderr}"
        assert result["ok"] is True, f"expected ok:true: {result}"
        assert result["verdict"] == "PASS", f"expected PASS: {result}"
        assert len(result["warns"]) == 1, f"expected one warn: {result}"
        warn = result["warns"][0]
        assert warn["source"] == "routing_signal_escalation", warn
        assert "s3" in warn["detail"], warn
        assert "racha=2" in warn["detail"], warn
        print("D3 POSITIVE PASS")


def case_no_history_no_warn():
    with tempfile.TemporaryDirectory(prefix="d3-nohistory-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        env = fixture_env(fixture_root)
        env["HOME"] = str(home_dir)
        write_audit(fixture_root, "s3")
        payload = '{"phase":"develop","e2e":true,"evidence":"ran d3 no history","session_id":"s3"}'
        proc = run_hook(fixture_root, env, payload)
        result = json.loads(proc.stdout)
        assert proc.returncode == 0, f"expected exit 0, got {proc.returncode}: {proc.stderr}"
        assert result["ok"] is True, f"expected ok:true: {result}"
        assert result["verdict"] == "PASS", f"expected PASS: {result}"
        assert result["warns"] == [], f"expected empty warns: {result}"
        print("D3 NO-HISTORY PASS")


def case_other_sessions_history_no_warn():
    with tempfile.TemporaryDirectory(prefix="d3-others-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        env = fixture_env(fixture_root)
        env["HOME"] = str(home_dir)
        write_history(fixture_root, [
            {"session_id": "s1", "triggered": True, "resolved": "triggered"},
            {"session_id": "s2", "triggered": True, "resolved": "triggered"},
        ])
        payload = '{"phase":"develop","e2e":true,"evidence":"ran d3 others","session_id":"s3"}'
        proc = run_hook(fixture_root, env, payload)
        result = json.loads(proc.stdout)
        assert proc.returncode == 0, f"expected exit 0, got {proc.returncode}: {proc.stderr}"
        assert result["ok"] is True, f"expected ok:true: {result}"
        assert result["warns"] == [], f"expected empty warns: {result}"
        print("D3 OTHER-SESSIONS-HISTORY PASS")


def case_current_resolved_no_warn():
    with tempfile.TemporaryDirectory(prefix="d3-resolved-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        env = fixture_env(fixture_root)
        env["HOME"] = str(home_dir)
        write_audit(fixture_root, "s3")
        write_activity(
            fixture_root,
            '[2026-01-01T00:00:01+00:00] | route | cronicas | Trinity -> Smith con fidelity_check',
        )
        write_history(fixture_root, [
            {"session_id": "s1", "triggered": True, "resolved": "triggered"},
            {"session_id": "s2", "triggered": True, "resolved": "triggered"},
        ])
        payload = '{"phase":"develop","e2e":true,"evidence":"ran d3 resolved","session_id":"s3"}'
        proc = run_hook(fixture_root, env, payload)
        result = json.loads(proc.stdout)
        assert proc.returncode == 0, f"expected exit 0, got {proc.returncode}: {proc.stderr}"
        assert result["ok"] is True, f"expected ok:true: {result}"
        assert result["warns"] == [], f"expected empty warns: {result}"
        print("D3 CURRENT-RESOLVED PASS")


def case_no_sid_no_warn():
    with tempfile.TemporaryDirectory(prefix="d3-nosid-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        env = fixture_env(fixture_root)
        env["HOME"] = str(home_dir)
        write_history(fixture_root, [
            {"session_id": "s1", "triggered": True, "resolved": "triggered"},
            {"session_id": "s2", "triggered": True, "resolved": "triggered"},
        ])
        payload = '{"phase":"develop","e2e":true,"evidence":"ran d3 no sid"}'
        proc = run_hook(fixture_root, env, payload)
        result = json.loads(proc.stdout)
        assert proc.returncode == 0, f"expected exit 0, got {proc.returncode}: {proc.stderr}"
        assert result["ok"] is True, f"expected ok:true: {result}"
        assert result["warns"] == [], f"expected empty warns: {result}"
        print("D3 NO-SID PASS")


def case_validator_precheck_no_history_write():
    with tempfile.TemporaryDirectory(prefix="d3-nohistwrite-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        env = fixture_env(fixture_root)
        env["HOME"] = str(home_dir)
        write_audit(fixture_root, "s3")
        write_history(fixture_root, [
            {"session_id": "s1", "triggered": True, "resolved": "triggered"},
        ])
        payload = '{"phase":"develop","e2e":true,"evidence":"ran d3 no histwrite","session_id":"s3"}'
        before = history_text(fixture_root)
        proc = run_hook(fixture_root, env, payload)
        assert proc.returncode == 0, f"expected exit 0, got {proc.returncode}: {proc.stderr}"
        assert history_text(fixture_root) == before, "validate_phase_close wrote history"
        precheck = fixture_root / "hooks" / "precheck_phase_close.py"
        subprocess.run(
            ["python3", str(precheck), payload],
            cwd=str(fixture_root), env=env, capture_output=True, text=True, timeout=60,
        )
        assert history_text(fixture_root) == before, "precheck wrote history"
        print("D3 NO-HISTORY-WRITE PASS")


def case_strict_e2e_and_types():
    with tempfile.TemporaryDirectory(prefix="d3-strict-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        env = fixture_env(fixture_root)
        env["HOME"] = str(home_dir)
        cases = [
            ('{"phase":"develop","e2e":"false","evidence":"ran strict a"}', 1, "JSON boolean"),
            ('{"phase":"develop","e2e":1,"evidence":"ran strict b"}', 1, "JSON boolean"),
            ('{"phase":"develop","e2e":true}', 1, "evidence"),
            ('{"phase":"develop"}', 1, "no end-to-end"),
            ('{"phase":"develop","e2e_passed":true,"evidence":"ran strict c"}', 1, "e2e"),
            ('{"phase":"develop","e2e":true,"evidence":"ran strict ok"}', 0, '"verdict": "PASS"'),
            ('[1,2]', 1, "JSON object"),
            ('{"phase":123,"e2e":true,"evidence":"ran strict d"}', 1, "'phase' must be a string"),
            ('{"phase":"eval","e2e":true,"evidence":"ran strict e","lesson":"N/A - no new lesson"}', 0, '"verdict": "PASS"'),
        ]
        for payload, expected_rc, needle in cases:
            proc = run_hook(fixture_root, env, payload)
            assert proc.returncode == expected_rc, (
                f"payload {payload}: expected rc {expected_rc}, got {proc.returncode}: {proc.stdout} {proc.stderr}"
            )
            assert needle in proc.stdout, f"payload {payload}: expected {needle!r} in stdout: {proc.stdout}"
            if expected_rc == 1:
                assert "Traceback" not in proc.stdout and "Traceback" not in proc.stderr, \
                    f"payload {payload} produced a traceback: {proc.stderr}"
        print("D3 STRICT-E2E-TYPES PASS")


def main():
    assert REPO_ROOT != Path("/tmp").resolve(), "repo root must not be /tmp"
    case_positive()
    case_no_history_no_warn()
    case_other_sessions_history_no_warn()
    case_current_resolved_no_warn()
    case_no_sid_no_warn()
    case_validator_precheck_no_history_write()
    case_strict_e2e_and_types()
    print("D3 ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
