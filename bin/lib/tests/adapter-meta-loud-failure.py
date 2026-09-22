#!/usr/bin/env python3
"""A — adapter metadata fail-loud contract (P1).

`adapters/_adapter_meta.py` must distinguish "metadata unreadable" (exit 2,
real diagnosis on stderr) from "no binding" (exit 1, silent) and "binding ok"
(exit 0, JSON on stdout). Exit-code contract: 0 = binding printed;
1 = no binding declared (file missing, no binding block, malformed block);
2 = metadata unreadable (import/open/YAMLError).

Cases:
1. adapter.yaml with invalid YAML -> rc=2, stderr contains YAMLError/ScannerError
   + sys.executable + sys.path[0:5].
2. valid adapter.yaml without a binding block -> rc=1, stderr empty.
3. missing adapter.yaml -> rc=1, stderr empty.
4. valid adapter.yaml with a complete binding -> rc=0, JSON on stdout.
5. (integration) `matrix adapter-doc-path` against a corrupt adapter.yaml ->
   rc!=0 and the CLI surfaces the real diagnosis via log_warning, not just
   "no adapter binding".
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
INVALID_YAML = 'binding: "unclosed\n'


def run_meta(fixture_root, target):
    env = os.environ.copy()
    env["MATRIX_ROOT"] = str(fixture_root)
    return subprocess.run(
        ["python3", str(fixture_root / "adapters" / "_adapter_meta.py"),
         "binding", f"--target={target}"],
        cwd=str(fixture_root),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


def run_cli(fixture_root, home_dir, cmd, cwd=None):
    matrix_bin = fixture_root / "bin" / "matrix"
    env = os.environ.copy()
    env["MATRIX_ROOT"] = str(fixture_root)
    env["HOME"] = str(home_dir)
    env["XDG_CONFIG_HOME"] = str(home_dir / ".config")
    env["SOURCE_DATE_EPOCH"] = "1704067200"
    env["TZ"] = "UTC"
    return subprocess.run(
        [str(matrix_bin)] + cmd,
        cwd=str(cwd or fixture_root),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


def case_invalid_yaml_exits_2_with_diagnosis():
    with tempfile.TemporaryDirectory(prefix="aml-invalid-") as td:
        fixture_root = Path(td)
        smoke.build_fixture(REPO_ROOT, fixture_root)
        target_dir = fixture_root / "adapters" / "broken"
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "adapter.yaml").write_text(INVALID_YAML, encoding="utf-8")
        proc = run_meta(fixture_root, "broken")
        assert proc.returncode == 2, \
            f"expected rc=2, got {proc.returncode}: {proc.stdout} {proc.stderr}"
        assert "YAMLError" in proc.stderr or "ScannerError" in proc.stderr, \
            f"expected YAMLError/ScannerError in stderr: {proc.stderr!r}"
        assert "sys.executable=" in proc.stderr, proc.stderr
        assert "sys.path[0:5]=" in proc.stderr, proc.stderr
        print("A INVALID YAML EXITS 2 WITH DIAGNOSIS PASS")


def case_valid_yaml_without_binding_exits_1_silent():
    with tempfile.TemporaryDirectory(prefix="aml-nobind-") as td:
        fixture_root = Path(td)
        smoke.build_fixture(REPO_ROOT, fixture_root)
        target_dir = fixture_root / "adapters" / "nobinding"
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "adapter.yaml").write_text(
            "target: fakecli\ncapabilities:\n  read: read\n", encoding="utf-8"
        )
        proc = run_meta(fixture_root, "nobinding")
        assert proc.returncode == 1, \
            f"expected rc=1, got {proc.returncode}: {proc.stdout} {proc.stderr}"
        assert proc.stderr.strip() == "", f"expected empty stderr, got {proc.stderr!r}"
        print("A VALID YAML WITHOUT BINDING EXITS 1 SILENT PASS")


def case_missing_adapter_yaml_exits_1_silent():
    with tempfile.TemporaryDirectory(prefix="aml-missing-") as td:
        fixture_root = Path(td)
        smoke.build_fixture(REPO_ROOT, fixture_root)
        target_dir = fixture_root / "adapters" / "missing"
        target_dir.mkdir(parents=True, exist_ok=True)
        proc = run_meta(fixture_root, "missing")
        assert proc.returncode == 1, \
            f"expected rc=1, got {proc.returncode}: {proc.stdout} {proc.stderr}"
        assert proc.stderr.strip() == "", f"expected empty stderr, got {proc.stderr!r}"
        print("A MISSING ADAPTER YAML EXITS 1 SILENT PASS")


def case_valid_binding_exits_0_json():
    with tempfile.TemporaryDirectory(prefix="aml-ok-") as td:
        fixture_root = Path(td)
        smoke.build_fixture(REPO_ROOT, fixture_root)
        proc = run_meta(fixture_root, "devin")
        assert proc.returncode == 0, \
            f"expected rc=0, got {proc.returncode}: {proc.stdout} {proc.stderr}"
        value = json.loads(proc.stdout)
        assert value.get("file") == "AGENTS.local.md", value
        assert value.get("begin_marker"), value
        assert value.get("end_marker"), value
        assert proc.stderr.strip() == "", f"expected empty stderr, got {proc.stderr!r}"
        print("A VALID BINDING EXITS 0 JSON PASS")


def case_integration_adapter_doc_path_surfaces_diagnosis():
    with tempfile.TemporaryDirectory(prefix="aml-cli-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        # Corrupt the fixture's own devin adapter.yaml (never the real repo).
        (fixture_root / "adapters" / "devin" / "adapter.yaml").write_text(
            INVALID_YAML, encoding="utf-8"
        )
        proc = run_cli(fixture_root, home_dir, ["adapter-doc-path"])
        assert proc.returncode != 0, \
            f"expected rc!=0, got {proc.returncode}: {proc.stdout} {proc.stderr}"
        combined = proc.stdout + proc.stderr
        assert "metadata ilegible" in combined, combined
        assert "YAMLError" in combined or "ScannerError" in combined, combined
        assert "no adapter binding" not in combined, combined
        print("A INTEGRATION ADAPTER-DOC-PATH SURFACES DIAGNOSIS PASS")


def main():
    assert REPO_ROOT != Path("/tmp").resolve(), "repo root must not be /tmp"
    case_invalid_yaml_exits_2_with_diagnosis()
    case_valid_yaml_without_binding_exits_1_silent()
    case_missing_adapter_yaml_exits_1_silent()
    case_valid_binding_exits_0_json()
    case_integration_adapter_doc_path_surfaces_diagnosis()
    print("A ADAPTER-META LOUD-FAILURE ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
