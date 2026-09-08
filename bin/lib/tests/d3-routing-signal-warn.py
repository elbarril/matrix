#!/usr/bin/env python3
"""D3 — validate_phase_close escalates routing-signal history to a WARN.

Positive: three triggered:true records (current + 2 prior) produce a warn.
Negative: missing routing-signal-history.jsonl produces an empty warns list.
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
PAYLOAD = '{"phase":"develop","e2e":true,"evidence":"ran d3 positive"}'


def run_hook(fixture_root, env):
    hook = fixture_root / "hooks" / "validate_phase_close.py"
    return subprocess.run(
        ["python3", str(hook), PAYLOAD],
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


def write_history(fixture_root):
    hist = fixture_root / "brain" / "state" / "routing-signal-history.jsonl"
    hist.parent.mkdir(parents=True, exist_ok=True)
    hist.write_text(
        json.dumps({"session_id": "s1", "triggered": True}) + "\n"
        + json.dumps({"session_id": "s2", "triggered": True}) + "\n"
        + json.dumps({"session_id": "s3", "triggered": True}) + "\n",
        encoding="utf-8",
    )


def case_positive():
    with tempfile.TemporaryDirectory(prefix="d3-positive-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        env = fixture_env(fixture_root)
        env["HOME"] = str(home_dir)
        write_history(fixture_root)
        proc = run_hook(fixture_root, env)
        result = json.loads(proc.stdout)
        assert proc.returncode == 0, f"expected exit 0, got {proc.returncode}: {proc.stderr}"
        assert result["ok"] is True, f"expected ok:true: {result}"
        assert result["verdict"] == "PASS", f"expected PASS: {result}"
        assert len(result["warns"]) == 1, f"expected one warn: {result}"
        warn = result["warns"][0]
        assert warn["source"] == "routing_signal_escalation", warn
        assert "s3" in warn["detail"], warn
        assert "prior=2" in warn["detail"], warn
        print("D3 POSITIVE PASS")


def case_negative():
    with tempfile.TemporaryDirectory(prefix="d3-negative-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        env = fixture_env(fixture_root)
        env["HOME"] = str(home_dir)
        proc = run_hook(fixture_root, env)
        result = json.loads(proc.stdout)
        assert proc.returncode == 0, f"expected exit 0, got {proc.returncode}: {proc.stderr}"
        assert result["ok"] is True, f"expected ok:true: {result}"
        assert result["warns"] == [], f"expected empty warns: {result}"
        print("D3 NEGATIVE PASS")


def main():
    assert REPO_ROOT != Path("/tmp").resolve(), "repo root must not be /tmp"
    case_positive()
    case_negative()
    print("D3 ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
