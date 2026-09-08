#!/usr/bin/env python3
"""C3 — validate_layer2 denylist must not treat a path token like `.devin/...` as the CLI.

Positive: `the CLI Devin` still produces a CLI-name error.
Negative: `.devin/tools/fidelity_check.py` produces no CLI-name error.
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


def run_hook(fixture_root, env):
    hook = fixture_root / "hooks" / "validate_layer2.py"
    return subprocess.run(
        ["python3", str(hook)],
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


def write_probe(fixture_root, body):
    probe = fixture_root / "brain" / "data" / "lessons" / "devin-probe.md"
    probe.parent.mkdir(parents=True, exist_ok=True)
    probe.write_text(body, encoding="utf-8")


def case_path_no_error():
    with tempfile.TemporaryDirectory(prefix="layer2-devin-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        env = fixture_env(fixture_root)
        env["HOME"] = str(home_dir)
        write_probe(
            fixture_root,
            "# probe\n"
            "- usar `.devin/tools/fidelity_check.py` como check mecánico.\n"
            "- el artefacto vive bajo `path/.devin/tools/`.\n",
        )
        proc = run_hook(fixture_root, env)
        result = json.loads(proc.stdout)
        assert proc.returncode == 0, f"expected exit 0, got {proc.returncode}: {proc.stderr}"
        assert result["ok"] is True, f"expected ok:true: {result}"
        assert result["errors"] == [], f"expected no errors: {result}"
        print("C3 PATH NO-ERROR PASS")


def case_cli_devin_errors():
    with tempfile.TemporaryDirectory(prefix="layer2-devin-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        env = fixture_env(fixture_root)
        env["HOME"] = str(home_dir)
        write_probe(
            fixture_root,
            "# probe\n"
            "- The current adapter is the CLI Devin.\n",
        )
        proc = run_hook(fixture_root, env)
        result = json.loads(proc.stdout)
        assert proc.returncode == 1, f"expected exit 1, got {proc.returncode}: {proc.stdout}"
        assert result["ok"] is False, f"expected ok:false: {result}"
        devin_errors = [e for e in result["errors"] if "names the CLI 'Devin'" in e]
        assert len(devin_errors) == 1, f"expected one Devin error: {result}"
        assert "devin-probe.md" in devin_errors[0], devin_errors
        print("C3 CLI DEVIN ERRORS PASS")


def main():
    assert REPO_ROOT != Path("/tmp").resolve(), "repo root must not be /tmp"
    case_path_no_error()
    case_cli_devin_errors()
    print("C3 ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
