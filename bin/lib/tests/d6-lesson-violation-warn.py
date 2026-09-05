#!/usr/bin/env python3
"""D6 — validate_phase_close warns when lesson:violation reaches 2 for a lesson.

Positive: two ledger lines lesson=42 produce a warn naming lesson 42.
Negative: a single violation produces an empty warns list.
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
PAYLOAD = '{"phase":"develop","e2e":true,"evidence":"ran d6 positive"}'


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


def write_violations(fixture_root, lesson, count):
    log = fixture_root / "brain" / "state" / "activity.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for i in range(count):
        ts = f"2026-01-01T00:00:0{i}+00:00"
        lines.append(f"[{ts}] | lesson:violation |  | lesson={lesson}")
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")


def case_positive():
    with tempfile.TemporaryDirectory(prefix="d6-positive-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        env = fixture_env(fixture_root)
        env["HOME"] = str(home_dir)
        write_violations(fixture_root, "42", 2)
        proc = run_hook(fixture_root, env)
        result = json.loads(proc.stdout)
        assert proc.returncode == 0, f"expected exit 0, got {proc.returncode}: {proc.stderr}"
        assert result["ok"] is True
        assert result["verdict"] == "PASS"
        assert len(result["warns"]) == 1, f"expected one warn: {result}"
        warn = result["warns"][0]
        assert warn["source"] == "lesson_violation", warn
        assert warn["lesson"] == "42", warn
        assert "×2" in warn["detail"], warn
        print("D6 POSITIVE PASS")


def case_negative():
    with tempfile.TemporaryDirectory(prefix="d6-negative-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        env = fixture_env(fixture_root)
        env["HOME"] = str(home_dir)
        write_violations(fixture_root, "42", 1)
        proc = run_hook(fixture_root, env)
        result = json.loads(proc.stdout)
        assert proc.returncode == 0, f"expected exit 0, got {proc.returncode}: {proc.stderr}"
        assert result["ok"] is True
        assert result["warns"] == [], f"expected empty warns: {result}"
        print("D6 NEGATIVE PASS")


def main():
    assert REPO_ROOT != Path("/tmp").resolve(), "repo root must not be /tmp"
    case_positive()
    case_negative()
    print("D6 ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
