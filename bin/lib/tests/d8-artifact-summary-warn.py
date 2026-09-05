#!/usr/bin/env python3
"""D8 — phase_close emits an artifact_summary WARN when a referenced output
markdown file lacks the MATRIX:ARTIFACT-SUMMARY marker in its first 3 non-empty
lines, and records the count in the phase:close ledger detail.

Positive (warn): demo.md exists without the marker.
Negative (control): demo.md has the marker in line 1.
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
PAYLOAD_FMT = '{"phase":"eval","e2e":true,"evidence":"ver brain/output/demo.md","lesson":"N/A - nada nuevo"}'


def fixture_env(fixture_root, home_dir):
    env = os.environ.copy()
    env["HOME"] = str(home_dir)
    env["XDG_CONFIG_HOME"] = str(home_dir / ".config")
    env["SOURCE_DATE_EPOCH"] = "1704067200"
    env["TZ"] = "UTC"
    env["MATRIX_ROOT"] = str(fixture_root)
    env["PATH"] = f"{fixture_root / 'bin'}:{env.get('PATH', '')}"
    return env


def last_phase_close_detail(fixture_root):
    log = fixture_root / "brain" / "state" / "activity.log"
    if not log.exists():
        return ""
    lines = log.read_text(encoding="utf-8").splitlines()
    for line in reversed(lines):
        if "phase:close" in line:
            return line
    return ""


def run_phase_close(fixture_root, env):
    matrix = fixture_root / "bin" / "matrix"
    return smoke.run_cmd(
        matrix,
        ["phase", "close", PAYLOAD_FMT],
        fixture_root,
        env,
    )


def case_positive():
    with tempfile.TemporaryDirectory(prefix="d8-positive-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        env = fixture_env(fixture_root, home_dir)
        demo = fixture_root / "brain" / "output" / "demo.md"
        demo.parent.mkdir(parents=True, exist_ok=True)
        demo.write_text("# Demo\n\nbody\n", encoding="utf-8")

        proc = run_phase_close(fixture_root, env)
        result = json.loads(proc.stdout)
        assert proc.returncode == 0, f"expected exit 0, got {proc.returncode}: {proc.stderr}"
        assert result["ok"] is True, result
        assert result["verdict"] == "PASS", result
        assert len(result["warns"]) == 1, f"expected one warn: {result}"
        warn = result["warns"][0]
        assert warn["source"] == "artifact_summary", warn
        assert "brain/output/demo.md" in warn["detail"], warn
        detail = last_phase_close_detail(fixture_root)
        assert "artifact_summary_warns=1" in detail, detail
        print("D8 POSITIVE PASS")


def case_negative():
    with tempfile.TemporaryDirectory(prefix="d8-negative-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        env = fixture_env(fixture_root, home_dir)
        demo = fixture_root / "brain" / "output" / "demo.md"
        demo.parent.mkdir(parents=True, exist_ok=True)
        demo.write_text(
            "<!-- MATRIX:ARTIFACT-SUMMARY v1 -->\n# Demo\n\nbody\n", encoding="utf-8"
        )

        proc = run_phase_close(fixture_root, env)
        result = json.loads(proc.stdout)
        assert proc.returncode == 0, f"expected exit 0, got {proc.returncode}: {proc.stderr}"
        assert result["ok"] is True, result
        assert result["verdict"] == "PASS", result
        assert result["warns"] == [], f"expected empty warns: {result}"
        detail = last_phase_close_detail(fixture_root)
        assert "artifact_summary_warns=0" in detail, detail
        print("D8 NEGATIVE PASS")


def main():
    assert REPO_ROOT != Path("/tmp").resolve(), "repo root must not be /tmp"
    case_positive()
    case_negative()
    print("D8 ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
