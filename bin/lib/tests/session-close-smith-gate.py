#!/usr/bin/env python3
"""C — session_close enforces the Smith gate on a G2 mutant (Opción C).

(a) prosa-bound session with skill+check but no Smith delegation -> the routing
    signal stays triggered and session_close requires `smith_gate` (ok:false).
(b) same work with a route/handoff to Smith naming the real check -> the signal
    resolves delegated, `smith_gate` is not required and close is conformant.
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


def run_hook(fixture_root, env, session_id):
    hook = fixture_root / "hooks" / "session_close.py"
    return subprocess.run(
        ["python3", str(hook), json.dumps({"session_id": session_id})],
        cwd=str(fixture_root),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


def fixture_env(fixture_root):
    env = os.environ.copy()
    env["MATRIX_ROOT"] = str(fixture_root)
    env["SOURCE_DATE_EPOCH"] = "1704067200"
    env["TZ"] = "UTC"
    return env


def write_audit(fixture_root, session_id, start_status="ok", mutating=True):
    log = fixture_root / "brain" / "state" / "hook-audit.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    start = {"event": "session_start", "session_id": session_id,
             "timestamp": "2026-01-01T00:00:00+00:00"}
    if start_status == "ok":
        start["pre_activation_check_ok"] = True
        start["pre_activation_check_status"] = "ok"
    elif start_status == "disabled":
        start["pre_activation_check_status"] = "disabled"
    elif start_status == "failed":
        start["pre_activation_check_ok"] = False
        start["pre_activation_check_status"] = "failed"
    entries = [start]
    if mutating:
        entries += [
            {"event": "post_tool_use", "session_id": session_id,
             "tool_name": "edit", "tool_paths": ["docs/a.md"],
             "timestamp": "2026-01-01T00:00:01+00:00"},
            {"event": "post_tool_use", "session_id": session_id,
             "tool_name": "edit", "tool_paths": ["docs/b.md"],
             "timestamp": "2026-01-01T00:00:02+00:00"},
            {"event": "phase_close", "session_id": session_id,
             "timestamp": "2026-01-01T00:00:03+00:00"},
        ]
    log.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")


def write_activity(fixture_root, line):
    log = fixture_root / "brain" / "state" / "activity.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(line + "\n", encoding="utf-8")


def case_no_smith_requires_gate():
    with tempfile.TemporaryDirectory(prefix="sg-nosmith-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        env = fixture_env(fixture_root)
        env["HOME"] = str(home_dir)
        write_audit(fixture_root, "sg-a")
        proc = run_hook(fixture_root, env, "sg-a")
        result = json.loads(proc.stdout)
        assert proc.returncode == 1, f"expected exit 1 (BLOCK), got {proc.returncode}: {proc.stdout}"
        assert result["ok"] is False, f"expected ok:false: {result}"
        assert result["smith_gate_required"] is True, f"expected smith_gate_required:true: {result}"
        validation = result["validation"]
        assert "smith_gate" in validation["missing"], f"expected smith_gate in missing: {result}"
        assert validation["bypass_suspected"] is True, f"expected bypass_suspected:true: {result}"
        print("C NO-SMITH REQUIRES GATE PASS")


def case_smith_with_check_conforme():
    with tempfile.TemporaryDirectory(prefix="sg-smith-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        env = fixture_env(fixture_root)
        env["HOME"] = str(home_dir)
        write_audit(fixture_root, "sg-b")
        write_activity(
            fixture_root,
            '[2026-01-01T00:00:01+00:00] | handoff | cronicas | Trinity -> Smith con fidelity_check',
        )
        proc = run_hook(fixture_root, env, "sg-b")
        result = json.loads(proc.stdout)
        assert proc.returncode == 0, f"expected exit 0, got {proc.returncode}: {proc.stderr}"
        assert result["ok"] is True, f"expected ok:true: {result}"
        assert result["smith_gate_required"] is False, f"expected smith_gate_required:false: {result}"
        validation = result["validation"]
        assert "smith_gate" not in validation["missing"], f"smith_gate must not be missing: {result}"
        assert validation["compliant"] is True, f"expected compliant:true: {result}"
        print("C SMITH WITH CHECK CONFORME PASS")


def case_double_close_no_history_dup():
    with tempfile.TemporaryDirectory(prefix="sg-double-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        env = fixture_env(fixture_root)
        env["HOME"] = str(home_dir)
        write_audit(fixture_root, "sg-c")
        proc1 = run_hook(fixture_root, env, "sg-c")
        result1 = json.loads(proc1.stdout)
        assert proc1.returncode == 1, f"expected exit 1, got {proc1.returncode}: {proc1.stdout}"
        assert result1["smith_gate_required"] is True, result1
        hist_path = fixture_root / "brain" / "state" / "routing-signal-history.jsonl"
        assert hist_path.is_file(), "expected routing-signal history after close"

        def records_for(sid):
            return [json.loads(l) for l in hist_path.read_text(encoding="utf-8").splitlines()
                    if l.strip() and json.loads(l).get("session_id") == sid]

        assert len(records_for("sg-c")) == 1, records_for("sg-c")
        proc2 = run_hook(fixture_root, env, "sg-c")
        result2 = json.loads(proc2.stdout)
        assert proc2.returncode == 1, f"expected exit 1, got {proc2.returncode}: {proc2.stdout}"
        assert result2["smith_gate_required"] is True, result2
        assert len(records_for("sg-c")) == 1, f"second close must not duplicate: {records_for('sg-c')}"
        print("C DOUBLE-CLOSE NO-DUP PASS")


def case_pre_activation_disabled_conformant():
    with tempfile.TemporaryDirectory(prefix="sg-disabled-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        env = fixture_env(fixture_root)
        env["HOME"] = str(home_dir)
        write_audit(fixture_root, "sg-dis", start_status="disabled", mutating=False)
        proc = run_hook(fixture_root, env, "sg-dis")
        result = json.loads(proc.stdout)
        assert proc.returncode == 0, f"expected exit 0, got {proc.returncode}: {proc.stdout}"
        assert result["ok"] is True, f"expected ok:true: {result}"
        validation = result["validation"]
        assert validation["compliant"] is True, validation
        assert "pre_activation_check" not in validation["missing"], validation
        print("C PRE-ACTIVATION DISABLED CONFORMANT PASS")


def case_pre_activation_failed_still_blocks():
    with tempfile.TemporaryDirectory(prefix="sg-prefail-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        env = fixture_env(fixture_root)
        env["HOME"] = str(home_dir)
        write_audit(fixture_root, "sg-prefail", start_status="failed", mutating=False)
        proc = run_hook(fixture_root, env, "sg-prefail")
        result = json.loads(proc.stdout)
        assert proc.returncode == 1, f"expected exit 1, got {proc.returncode}: {proc.stdout}"
        assert result["ok"] is False, result
        assert "pre_activation_check" in result["validation"]["missing"], result["validation"]
        print("C PRE-ACTIVATION FAILED STILL BLOCKS PASS")


def case_pre_activation_legacy_missing_still_blocks():
    with tempfile.TemporaryDirectory(prefix="sg-prelegacy-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        env = fixture_env(fixture_root)
        env["HOME"] = str(home_dir)
        write_audit(fixture_root, "sg-prelegacy", start_status="legacy", mutating=False)
        proc = run_hook(fixture_root, env, "sg-prelegacy")
        result = json.loads(proc.stdout)
        assert proc.returncode == 1, f"expected exit 1, got {proc.returncode}: {proc.stdout}"
        assert result["ok"] is False, result
        assert "pre_activation_check" in result["validation"]["missing"], result["validation"]
        print("C PRE-ACTIVATION LEGACY MISSING STILL BLOCKS PASS")


def case_flags_today_do_not_change_past():
    with tempfile.TemporaryDirectory(prefix="sg-flagpast-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        env = fixture_env(fixture_root)
        env["HOME"] = str(home_dir)
        env["MATRIX_HOOKS_PRE_ACTIVATION_CHECK"] = "1"
        write_audit(fixture_root, "sg-past", start_status="disabled", mutating=False)
        proc = run_hook(fixture_root, env, "sg-past")
        result = json.loads(proc.stdout)
        assert proc.returncode == 0, f"past disabled must stay conformant with flag on: {proc.stdout}"
        write_audit(fixture_root, "sg-past2", start_status="failed", mutating=False)
        proc2 = run_hook(fixture_root, env, "sg-past2")
        result2 = json.loads(proc2.stdout)
        assert proc2.returncode == 1, f"past failed must stay blocking with flag on: {proc2.stdout}"
        assert result2["ok"] is False, result2
        print("C FLAGS TODAY DO NOT CHANGE PAST PASS")


def case_adapter_start_off_audits_disabled_and_close_conformant():
    with tempfile.TemporaryDirectory(prefix="sg-e2e-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        env = fixture_env(fixture_root)
        env["HOME"] = str(home_dir)
        audit_script = REPO_ROOT / "adapters" / "devin" / "hooks" / "session_audit.py"
        proc = subprocess.run(
            ["python3", str(audit_script)],
            cwd=str(fixture_root), env=env, input=json.dumps({"hook_event_name": "SessionStart"}),
            capture_output=True, text=True, timeout=120,
        )
        assert proc.returncode == 0, f"session_audit start failed: {proc.stdout} {proc.stderr}"
        log = fixture_root / "brain" / "state" / "hook-audit.jsonl"
        assert log.is_file(), "no audit log written"
        entries = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines() if l.strip()]
        start = next((e for e in entries if e.get("event") == "session_start"), None)
        assert start is not None, entries
        assert start.get("pre_activation_check_status") == "disabled", start
        assert start.get("pre_activation_check_ok") is not True, start
        sid = start["session_id"]
        close = subprocess.run(
            [str(fixture_root / "bin" / "matrix"), "session", "close", json.dumps({"session_id": sid})],
            cwd=str(fixture_root), env=env, capture_output=True, text=True, timeout=120,
        )
        result = json.loads(close.stdout)
        assert close.returncode == 0, f"expected conformant close: {close.stdout} {close.stderr}"
        assert result["ok"] is True, result
        assert result["validation"]["compliant"] is True, result["validation"]
        print("C E2E ADAPTER START-DISABLED CLOSE CONFORMANT PASS")


def main():
    assert REPO_ROOT != Path("/tmp").resolve(), "repo root must not be /tmp"
    case_no_smith_requires_gate()
    case_smith_with_check_conforme()
    case_double_close_no_history_dup()
    case_pre_activation_disabled_conformant()
    case_pre_activation_failed_still_blocks()
    case_pre_activation_legacy_missing_still_blocks()
    case_flags_today_do_not_change_past()
    case_adapter_start_off_audits_disabled_and_close_conformant()
    print("C SMITH GATE ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
