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


def main():
    assert REPO_ROOT != Path("/tmp").resolve(), "repo root must not be /tmp"
    case_no_smith_requires_gate()
    case_smith_with_check_conforme()
    print("C SMITH GATE ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
