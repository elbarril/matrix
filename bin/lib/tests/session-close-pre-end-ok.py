#!/usr/bin/env python3
"""C2 — session_close mid-session must not report a false bypass for `session_end`.

A session with session_start + pre_activation_check + mutation + phase_close but
NO session_end (session still open when closed) must close ok:true with
bypass_suspected:false and session_end_seen:false.
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
SESSION_ID = "c2-pre-end"


def run_hook(fixture_root, env):
    hook = fixture_root / "hooks" / "session_close.py"
    return subprocess.run(
        ["python3", str(hook), json.dumps({"session_id": SESSION_ID})],
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


def write_audit(fixture_root):
    log = fixture_root / "brain" / "state" / "hook-audit.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    entries = [
        {"event": "session_start", "session_id": SESSION_ID,
         "pre_activation_check_ok": True, "timestamp": "2026-01-01T00:00:00+00:00"},
        {"event": "post_tool_use", "session_id": SESSION_ID,
         "tool_name": "edit", "tool_paths": ["docs/foo.md"],
         "timestamp": "2026-01-01T00:00:01+00:00"},
        {"event": "phase_close", "session_id": SESSION_ID,
         "timestamp": "2026-01-01T00:00:02+00:00"},
    ]
    log.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")


def case_pre_end_ok():
    with tempfile.TemporaryDirectory(prefix="c2-pre-end-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        env = fixture_env(fixture_root)
        env["HOME"] = str(home_dir)
        write_audit(fixture_root)
        proc = run_hook(fixture_root, env)
        result = json.loads(proc.stdout)
        assert proc.returncode == 0, f"expected exit 0, got {proc.returncode}: {proc.stderr}"
        assert result["ok"] is True, f"expected ok:true: {result}"
        assert result["session_end_seen"] is False, f"expected session_end_seen:false: {result}"
        validation = result["validation"]
        assert validation["bypass_suspected"] is False, f"expected bypass_suspected:false: {result}"
        assert validation["compliant"] is True, f"expected compliant:true: {result}"
        assert "session_end" not in validation["missing"], f"session_end must not be missing: {result}"
        print("C2 PRE-END OK PASS")


def main():
    assert REPO_ROOT != Path("/tmp").resolve(), "repo root must not be /tmp"
    case_pre_end_ok()
    print("C2 ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
