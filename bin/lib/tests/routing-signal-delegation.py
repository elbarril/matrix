#!/usr/bin/env python3
"""C — validate_routing_signal delegation verification (Opción C).

(a) route/handoff naming Smith with a real check token -> resolved=delegated.
(b) route/handoff naming Smith without a check token -> triggered with
    unverified_delegation:true.
(c) no route/handoff -> triggered.
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
    hook = fixture_root / "hooks" / "validate_routing_signal.py"
    return subprocess.run(
        ["python3", str(hook), json.dumps({"session_id": session_id})],
        cwd=str(fixture_root),
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
    )


def fixture_env(fixture_root):
    env = os.environ.copy()
    env["MATRIX_ROOT"] = str(fixture_root)
    env["SOURCE_DATE_EPOCH"] = "1704067200"
    env["TZ"] = "UTC"
    return env


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


def case_delegated_with_check():
    with tempfile.TemporaryDirectory(prefix="rs-delegated-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        env = fixture_env(fixture_root)
        env["HOME"] = str(home_dir)
        write_audit(fixture_root, "rs-a")
        write_activity(
            fixture_root,
            '[2026-01-01T00:00:01+00:00] | route | cronicas | Trinity -> Smith corre fidelity_check',
        )
        proc = run_hook(fixture_root, env, "rs-a")
        result = json.loads(proc.stdout)
        assert proc.returncode == 0, f"expected exit 0, got {proc.returncode}: {proc.stderr}"
        assert result["ok"] is True, f"expected ok:true: {result}"
        assert result["triggered"] is False, f"expected triggered:false: {result}"
        assert result["resolved"] == "delegated", f"expected resolved=delegated: {result}"
        assert result["unverified_delegation"] is False, f"expected unverified:false: {result}"
        print("C DELEGATED WITH CHECK PASS")


def case_delegated_without_check():
    with tempfile.TemporaryDirectory(prefix="rs-unverified-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        env = fixture_env(fixture_root)
        env["HOME"] = str(home_dir)
        write_audit(fixture_root, "rs-b")
        write_activity(
            fixture_root,
            '[2026-01-01T00:00:01+00:00] | route | cronicas | Trinity -> Smith',
        )
        proc = run_hook(fixture_root, env, "rs-b")
        result = json.loads(proc.stdout)
        assert proc.returncode == 0, f"expected exit 0, got {proc.returncode}: {proc.stderr}"
        assert result["triggered"] is True, f"expected triggered:true: {result}"
        assert result["resolved"] == "triggered", f"expected resolved=triggered: {result}"
        assert result["unverified_delegation"] is True, f"expected unverified:true: {result}"
        assert "delegación sin check verificado" in result["message"], result["message"]
        print("C DELEGATED WITHOUT CHECK PASS")


def case_no_delegation():
    with tempfile.TemporaryDirectory(prefix="rs-nodeleg-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        env = fixture_env(fixture_root)
        env["HOME"] = str(home_dir)
        write_audit(fixture_root, "rs-c")
        proc = run_hook(fixture_root, env, "rs-c")
        result = json.loads(proc.stdout)
        assert proc.returncode == 0, f"expected exit 0, got {proc.returncode}: {proc.stderr}"
        assert result["triggered"] is True, f"expected triggered:true: {result}"
        assert result["resolved"] == "triggered", f"expected resolved=triggered: {result}"
        assert result["unverified_delegation"] is False, f"expected unverified:false: {result}"
        assert "no Link route/handoff" in result["message"], result["message"]
        print("C NO DELEGATION PASS")


def main():
    assert REPO_ROOT != Path("/tmp").resolve(), "repo root must not be /tmp"
    case_delegated_with_check()
    case_delegated_without_check()
    case_no_delegation()
    print("C DELEGATION ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
