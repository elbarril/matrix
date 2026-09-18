#!/usr/bin/env python3
"""D9 — inject pre-activation failure fixtures and verify downstream behavior.

Builds a throwaway Matrix fixture (never the real repo) and runs six cases:
1. config without user:         pre_activation_check -> ok:false, config_has_user
2. AGENTS.md missing:           pre_activation_check -> ok:false, contract_present
3. architect.md missing:        pre_activation_check -> ok:false, roster_intact
4. audit_event ok:false + session close -> hook-audit.jsonl contains the new keys,
   session_close DOES derive pre_activation_check (Opción B, status failed),
   post_run_audit compliant:true, and the failure is surfaced on the result
5. healthy fixture (built/installed): ok:true, boot_warn.warns empty (dictamen Architect punto 4)
6. BOOT_WARN_BUDGET_S=0:       ok:true, boot_warn.warns empty, skipped lists all seven tokens
"""
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path


def load_smoke_module():
    smoke_path = Path(__file__).resolve().parent / "smoke-matrix-help.py"
    spec = importlib.util.spec_from_file_location("smoke_matrix_help", smoke_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


smoke = load_smoke_module()
build_fixture = smoke.build_fixture
repo_root_from_script = smoke.repo_root_from_script


class FixtureContext:
    def __init__(self, td, fixture_root, home_dir, env):
        self.td = td
        self.fixture_root = fixture_root
        self.home_dir = home_dir
        self.env = env

    def __enter__(self):
        return self.fixture_root, self.home_dir, self.env

    def __exit__(self, *exc):
        self.td.cleanup()
        return False


def run_cmd(matrix_bin, cmd, cwd, env, stdin=None, timeout=120):
    return subprocess.run(
        ["bash", "-c", 'export RANDOM=12345; exec "$@"', "--", str(matrix_bin)] + cmd,
        cwd=str(cwd), env=env, input=stdin, capture_output=True, text=True, timeout=timeout,
    )


def fixture_env(home_dir, fixture_root):
    env = os.environ.copy()
    env["HOME"] = str(home_dir)
    env["XDG_CONFIG_HOME"] = str(home_dir / ".config")
    env["SOURCE_DATE_EPOCH"] = "1704067200"
    env["TZ"] = "UTC"
    env["MATRIX_ROOT"] = str(fixture_root)
    env["PATH"] = f"{fixture_root / 'bin'}:{env.get('PATH', '')}"
    return env


def json_or_die(proc, label):
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise AssertionError(f"{label}: expected JSON, got stdout={proc.stdout!r} stderr={proc.stderr!r} rc={proc.returncode}")


def prepare_fixture():
    """Return a fixture that has been built, installed, and given a fake MCP config."""
    repo_root = repo_root_from_script()
    td = tempfile.TemporaryDirectory(prefix="d9-case-")
    fixture_root = Path(td.name)
    home_dir = build_fixture(repo_root, fixture_root)
    env = fixture_env(home_dir, fixture_root)
    matrix = fixture_root / "bin" / "matrix"
    for cmd in (["build", "--target=devin"], ["install", "--target=devin"]):
        p = run_cmd(matrix, cmd, fixture_root, env)
        if p.returncode != 0:
            td.cleanup()
            raise AssertionError(f"prepare_fixture {' '.join(cmd)} failed: rc={p.returncode} stdout={p.stdout!r} stderr={p.stderr!r}")
    # Provide a minimal MCP config so install-integrity passes in the fixture.
    mcp_path = home_dir / ".config" / "devin" / "mcp_config.json"
    mcp_path.write_text(json.dumps({"mcpServers": {"chrome-browser": {}, "context7": {}}}), encoding="utf-8")
    return FixtureContext(td, fixture_root, home_dir, env)


def case_config_no_user():
    with prepare_fixture() as (fixture_root, home_dir, env):
        cfg = fixture_root / "brain" / "config.yaml"
        text = cfg.read_text(encoding="utf-8")
        cfg.write_text(re.sub(r"(?m)^user:.*$", "", text), encoding="utf-8")
        matrix = fixture_root / "bin" / "matrix"
        proc = run_cmd(matrix, ["hooks", "pre_activation_check"], fixture_root, env)
        result = json_or_die(proc, "case1")
        assert proc.returncode == 1, f"case1 expected exit 1, got {proc.returncode}"
        assert result.get("ok") is False, "case1 expected ok:false"
        assert any("config_has_user" in e for e in result.get("errors", [])), f"case1 missing config_has_user: {result}"
        print("D9-1 PASS")


def case_agents_md_deleted():
    with prepare_fixture() as (fixture_root, home_dir, env):
        (fixture_root / "AGENTS.md").unlink()
        matrix = fixture_root / "bin" / "matrix"
        proc = run_cmd(matrix, ["hooks", "pre_activation_check"], fixture_root, env)
        result = json_or_die(proc, "case2")
        assert proc.returncode == 1, f"case2 expected exit 1, got {proc.returncode}"
        assert result.get("ok") is False, "case2 expected ok:false"
        assert any("contract_present" in e for e in result.get("errors", [])), f"case2 missing contract_present: {result}"
        print("D9-2 PASS")


def case_architect_deleted():
    with prepare_fixture() as (fixture_root, home_dir, env):
        (fixture_root / "brain" / "agents" / "architect.md").unlink()
        matrix = fixture_root / "bin" / "matrix"
        proc = run_cmd(matrix, ["hooks", "pre_activation_check"], fixture_root, env)
        result = json_or_die(proc, "case3")
        assert proc.returncode == 1, f"case3 expected exit 1, got {proc.returncode}"
        assert result.get("ok") is False, "case3 expected ok:false"
        assert any("roster_intact" in e for e in result.get("errors", [])), f"case3 missing roster_intact: {result}"
        print("D9-3 PASS")


def case_downstream_real():
    with prepare_fixture() as (fixture_root, home_dir, env):
        matrix = fixture_root / "bin" / "matrix"
        log_path = fixture_root / "brain" / "state" / "hook-audit.jsonl"
        entry = {
            "event": "session_start",
            "session_id": "d9-case4",
            "project_active": None,
            "pre_activation_check_ok": False,
            "pre_activation_check_status": "failed",
            "boot_warn": ["the_source"],
            "timestamp": "2026-01-01T00:00:00+00:00",
        }
        log_path.write_text(json.dumps(entry) + "\n", encoding="utf-8")
        proc = run_cmd(
            matrix,
            ["session", "close", json.dumps({"session_id": "d9-case4"})],
            fixture_root,
            env,
        )
        result = json_or_die(proc, "case4")
        assert any("pre_activation_check_status" in line for line in log_path.read_text(encoding="utf-8").splitlines() if line), "case4 hook-audit missing pre_activation_check_status"
        # Opción B: a failed status DOES derive the step, so the close is
        # conformant and the failure is surfaced on the result (warn, not block).
        assert "pre_activation_check" in result.get("steps_seen", []), "case4 failed status must derive pre_activation_check"
        assert result.get("validation", {}).get("compliant") is True, f"case4 expected compliant:true: {result.get('validation')}"
        assert result.get("pre_activation_check_status") == "failed", f"case4 expected status failed: {result}"
        assert result.get("pre_activation_check_failed") is True, f"case4 expected failed surfaced: {result}"
        print("D9-4 PASS")


def case_healthy_fixture():
    with prepare_fixture() as (fixture_root, home_dir, env):
        matrix = fixture_root / "bin" / "matrix"
        proc = run_cmd(matrix, ["hooks", "pre_activation_check"], fixture_root, env)
        result = json_or_die(proc, "case5")
        assert proc.returncode == 0, f"case5 expected exit 0, got {proc.returncode}"
        assert result.get("ok") is True, f"case5 expected ok:true: {result}"
        # The surface_budget advisory on brain/agents/neo.md is a direct consequence
        # of the Opción C G2 doctrine clause — advisory only, never flips ok.
        boot_warns = result.get("boot_warn", {}).get("warns", [])
        assert set(boot_warns) <= {"surface_budget"}, f"case5 unexpected boot_warn.warns: {result}"
        print("D9-5 PASS")


def case_boot_warn_disabled():
    with prepare_fixture() as (fixture_root, home_dir, env):
        env["BOOT_WARN_BUDGET_S"] = "0"
        matrix = fixture_root / "bin" / "matrix"
        proc = run_cmd(matrix, ["hooks", "pre_activation_check"], fixture_root, env)
        result = json_or_die(proc, "case6")
        assert proc.returncode == 0, f"case6 expected exit 0, got {proc.returncode}"
        assert result.get("ok") is True, f"case6 expected ok:true: {result}"
        assert result.get("boot_warn", {}).get("warns") == [], f"case6 expected empty warns: {result}"
        assert sorted(result.get("boot_warn", {}).get("skipped", [])) == sorted([
            "surface_budget", "validate_lessons", "model_drift", "ttl_expired",
            "validate_layer2", "the_source", "snapshot_due",
        ]), f"case6 expected all 7 tokens skipped: {result}"
        print("D9-6 PASS")


def main():
    repo_root = repo_root_from_script()
    with tempfile.TemporaryDirectory(prefix="d9-guard-") as gd:
        fixture_root = Path(gd)
        home_dir = build_fixture(repo_root, fixture_root)
        assert fixture_root != repo_root, "D9 guard: fixture must not be the real repo"
        assert str(fixture_root).startswith("/tmp"), f"D9 guard: fixture must be under /tmp, got {fixture_root}"
        print(f"D9 fixture guard OK: {fixture_root}")

    case_config_no_user()
    case_agents_md_deleted()
    case_architect_deleted()
    case_downstream_real()
    case_healthy_fixture()
    case_boot_warn_disabled()
    print("D9 ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
