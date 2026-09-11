#!/usr/bin/env python3
"""Integration — phase close CLI: help without side effects, strict JSON
rejection before the ledger, session_id audit attribution, and project-scoped
ledger subjects.
"""
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path


smoke_path = Path(__file__).resolve().parent / "smoke-matrix-help.py"
spec = importlib.util.spec_from_file_location("smoke_matrix_help", smoke_path)
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


REPO_ROOT = smoke.repo_root_from_script()


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


def state_signature(fixture_root):
    sig = {}
    state_dir = fixture_root / "brain" / "state"
    if state_dir.is_dir():
        for dirpath, dirnames, filenames in os.walk(state_dir):
            dirnames[:] = [d for d in dirnames if not d.endswith(".lock")]
            for fn in filenames:
                if fn.endswith(".lock"):
                    continue
                p = Path(dirpath) / fn
                rel = p.relative_to(state_dir)
                sig[str(rel)] = p.read_bytes()
    return sig


def ledger_subjects(fixture_root, event):
    log = fixture_root / "brain" / "state" / "activity.log"
    if not log.is_file():
        return []
    out = []
    for line in log.read_text(encoding="utf-8").splitlines():
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 3 and parts[1] == event:
            out.append(parts[2])
    return out


def case_help_no_state_change():
    with tempfile.TemporaryDirectory(prefix="pc-help-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        commands = [
            ["phase", "--help"],
            ["phase", "close", "--help"],
            ["phase", "precheck", "--help"],
            ["session", "close", "--help"],
            ["hooks", "--help"],
            ["hooks", "validate_phase_close", "--help"],
            ["hooks", "validate_routing_signal", "--help"],
            ["hooks", "audit_event", "--help"],
            ["hooks", "the_source", "--help"],
        ]
        for cmd in commands:
            before = state_signature(fixture_root)
            proc = run_cli(fixture_root, home_dir, cmd)
            after = state_signature(fixture_root)
            assert proc.returncode == 0, f"{cmd}: expected rc 0, got {proc.returncode}: {proc.stdout} {proc.stderr}"
            assert before == after, f"{cmd}: help changed state:\n{before}\n{after}"
            assert "Usage:" in proc.stdout, f"{cmd}: no usage shown: {proc.stdout}"
        print("PC HELP NO-STATE-CHANGE PASS")


def case_phase_close_empty_payload():
    with tempfile.TemporaryDirectory(prefix="pc-empty-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        proc = run_cli(fixture_root, home_dir, ["phase", "close"])
        assert proc.returncode == 1, f"expected rc 1, got {proc.returncode}: {proc.stdout}"
        assert "Usage: matrix phase close" in proc.stdout, proc.stdout
        assert ledger_subjects(fixture_root, "phase:close") == [], "empty payload must not write ledger"
        print("PC PHASE-CLOSE EMPTY PASS")


def case_phase_close_non_object_rejected_before_ledger():
    with tempfile.TemporaryDirectory(prefix="pc-array-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        for payload in ['[1,2]', '"just-a-string"', '42']:
            proc = run_cli(fixture_root, home_dir, ["phase", "close", payload])
            assert proc.returncode == 1, f"{payload}: expected rc 1, got {proc.returncode}: {proc.stdout}"
            assert "object" in (proc.stdout + proc.stderr), f"{payload}: no object error: {proc.stdout} {proc.stderr}"
            assert ledger_subjects(fixture_root, "phase:close") == [], f"{payload}: rejected before ledger"
        print("PC PHASE-CLOSE NON-OBJECT PASS")


def case_phase_close_sid_audit():
    with tempfile.TemporaryDirectory(prefix="pc-sid-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        (fixture_root / "brain" / "state" / ".current-hook-session").write_text("marker-A")
        payload = '{"phase":"develop","e2e":true,"evidence":"ran sid audit suite; 9/9 passed","session_id":"sid-B"}'
        proc = run_cli(fixture_root, home_dir, ["phase", "close", payload])
        assert proc.returncode == 0, f"expected rc 0, got {proc.returncode}: {proc.stdout} {proc.stderr}"
        assert '"verdict": "PASS"' in proc.stdout, proc.stdout
        audit = fixture_root / "brain" / "state" / "hook-audit.jsonl"
        events = [json.loads(l) for l in audit.read_text(encoding="utf-8").splitlines() if l.strip()]
        close_events = [e for e in events if e.get("event") == "phase_close"]
        assert len(close_events) == 1, events
        assert close_events[0]["session_id"] == "sid-B", close_events
        assert not any(e.get("session_id") == "marker-A" for e in close_events), close_events
        print("PC SID AUDIT PASS")


def case_external_project_ledger_subject():
    with tempfile.TemporaryDirectory(prefix="pc-project-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        add = run_cli(fixture_root, home_dir, ["add", "alpha", str(fixture_root / "projects" / "alpha")])
        assert add.returncode == 0, f"add alpha failed: {add.stdout} {add.stderr}"
        payload = '{"phase":"spec","evidence":"brain/output/plans/smoke.md"}'
        proc = run_cli(fixture_root, home_dir, ["phase", "close", payload], cwd=fixture_root / "projects" / "alpha")
        assert proc.returncode == 0, f"expected rc 0, got {proc.returncode}: {proc.stdout} {proc.stderr}"
        subjects = ledger_subjects(fixture_root, "phase:close")
        assert "alpha" in subjects, f"expected subject alpha in ledger: {subjects}"
        assert "matrix" not in subjects, f"expected no matrix subject: {subjects}"
        print("PC EXTERNAL PROJECT SUBJECT PASS")


def case_phase_close_strict_cli():
    with tempfile.TemporaryDirectory(prefix="pc-strict-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        blocked = [
            '{"phase":"develop","e2e":"false","evidence":"ran strict cli a"}',
            '{"phase":"develop","e2e":1,"evidence":"ran strict cli b"}',
            '{"phase":"develop","e2e":true}',
            '{"phase":"develop"}',
            '{"phase":"nonsense","e2e":true,"evidence":"ran strict cli c"}',
            '{"phase":"develop","e2e":true,"evidence":"short"}',
        ]
        for payload in blocked:
            proc = run_cli(fixture_root, home_dir, ["phase", "close", payload])
            assert proc.returncode == 1, f"{payload}: expected rc 1, got {proc.returncode}: {proc.stdout}"
            assert '"verdict": "BLOCK"' in proc.stdout, f"{payload}: {proc.stdout}"
            assert "Traceback" not in proc.stdout and "Traceback" not in proc.stderr, f"{payload}: traceback"
        ok = '{"phase":"develop","e2e":true,"evidence":"ran strict cli ok; 11/11"}'
        proc = run_cli(fixture_root, home_dir, ["phase", "close", ok])
        assert proc.returncode == 0, f"expected rc 0, got {proc.returncode}: {proc.stdout} {proc.stderr}"
        print("PC STRICT CLI PASS")


def extract_example_payloads(help_text):
    return [m.group(1) for m in re.finditer(r"matrix phase (?:close|precheck) '(\{[^']+)'", help_text)]


def case_help_examples_pass_gates():
    with tempfile.TemporaryDirectory(prefix="pc-examples-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        for sub in ("close", "precheck"):
            hp = run_cli(fixture_root, home_dir, ["phase", sub, "--help"])
            assert hp.returncode == 0, (sub, hp.stdout, hp.stderr)
            payloads = extract_example_payloads(hp.stdout)
            assert payloads, f"{sub} help has no example payloads"
            for payload in payloads:
                json.loads(payload)
                pc = run_cli(fixture_root, home_dir, ["phase", sub, payload])
                assert pc.returncode == 0, f"{sub} example {payload} failed: {pc.stdout} {pc.stderr}"
        close_help = run_cli(fixture_root, home_dir, ["phase", "close", "--help"]).stdout
        close_payloads = extract_example_payloads(close_help)
        eval_payload = next((p for p in close_payloads if '"eval"' in p), None)
        assert eval_payload is not None, "close help must include an eval example"
        assert '"e2e":true' in eval_payload, f"eval example must include e2e:true: {eval_payload}"
        for payload in close_payloads:
            pc = run_cli(fixture_root, home_dir, ["phase", "close", payload])
            assert '"verdict": "PASS"' in pc.stdout, f"close example {payload}: {pc.stdout}"
        print("PC HELP EXAMPLES PASS GATES")


def case_phase_close_sid_invalid_and_quoting():
    with tempfile.TemporaryDirectory(prefix="pc-sidq-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        (fixture_root / "brain" / "state" / ".current-hook-session").write_text("marker-Q")
        audit = fixture_root / "brain" / "state" / "hook-audit.jsonl"
        payload = '{"phase":"develop","e2e":true,"evidence":"ran sid type probe","session_id":123}'
        proc = run_cli(fixture_root, home_dir, ["phase", "close", payload])
        assert proc.returncode == 1, f"expected BLOCK for non-string session_id: {proc.stdout}"
        assert '"verdict": "BLOCK"' in proc.stdout, proc.stdout
        events = [json.loads(l) for l in audit.read_text(encoding="utf-8").splitlines() if l.strip()] if audit.is_file() else []
        close_events = [e for e in events if e.get("event") in ("phase_close", "phase_close_blocked")]
        assert not any(e.get("session_id") == "marker-Q" for e in close_events), \
            f"invalid sid must not attribute to marker: {close_events}"
        special = '{"phase":"spec","evidence":"brain/output/plans/smoke.md","session_id":"sid with \\"quote\\" and \\\\backslash"}'
        proc2 = run_cli(fixture_root, home_dir, ["phase", "close", special])
        assert proc2.returncode == 0, f"special sid close failed: {proc2.stdout} {proc2.stderr}"
        events2 = [json.loads(l) for l in audit.read_text(encoding="utf-8").splitlines() if l.strip()]
        close2 = [e for e in events2 if e.get("event") == "phase_close"]
        assert close2 and close2[-1]["session_id"] == 'sid with "quote" and \\backslash', close2
        print("PC SID INVALID/QUOTING PASS")


def case_audit_event_payload_validation():
    with tempfile.TemporaryDirectory(prefix="pc-audit-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        audit = fixture_root / "brain" / "state" / "hook-audit.jsonl"
        invalid = [[], ['{"event":""}'], ['{"event":123}'], ['[1,2]']]
        for args in invalid:
            before = audit.read_bytes() if audit.is_file() else None
            proc = run_cli(fixture_root, home_dir, ["hooks", "audit_event"] + args)
            assert proc.returncode == 1, f"{args}: expected rc 1, got {proc.returncode}: {proc.stdout}"
            assert '"ok": false' in proc.stdout or '"ok":false' in proc.stdout, proc.stdout
            after = audit.read_bytes() if audit.is_file() else None
            assert before == after, f"{args}: invalid audit payload wrote state"
        valid = '{"event":"session_start","session_id":"test-valid"}'
        proc = run_cli(fixture_root, home_dir, ["hooks", "audit_event", valid])
        assert proc.returncode == 0, f"valid audit payload failed: {proc.stdout} {proc.stderr}"
        events = [json.loads(l) for l in audit.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert any(e.get("event") == "session_start" and e.get("session_id") == "test-valid" for e in events), events
        print("PC AUDIT EVENT PAYLOAD VALIDATION PASS")


def case_the_source_check_true_read_only():
    with tempfile.TemporaryDirectory(prefix="pc-tsource-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        truth = fixture_root / "docs" / "SYSTEM_TRUTH.md"
        before = truth.read_bytes() if truth.is_file() else None
        proc = run_cli(fixture_root, home_dir, ["hooks", "the_source", '{"check":true}'])
        assert proc.returncode == 0, f"check:true expected rc 0 after DEVIN flag enumeration, got {proc.returncode}: {proc.stdout}"
        out = json.loads(proc.stdout)
        assert out.get("in_sync") is True, out
        assert out.get("config_flags_missing") == [], out
        after = truth.read_bytes() if truth.is_file() else None
        assert before == after, "the_source check:true must not regenerate docs/SYSTEM_TRUTH.md"
        hp = run_cli(fixture_root, home_dir, ["hooks", "the_source", "--help"])
        assert hp.returncode == 0, hp.stdout
        assert "check" in hp.stdout and "GENERATE" in hp.stdout, hp.stdout
        print("PC THE_SOURCE CHECK TRUE READ-ONLY PASS")


def main():
    assert REPO_ROOT != Path("/tmp").resolve(), "repo root must not be /tmp"
    case_help_no_state_change()
    case_phase_close_empty_payload()
    case_phase_close_non_object_rejected_before_ledger()
    case_phase_close_sid_audit()
    case_external_project_ledger_subject()
    case_phase_close_strict_cli()
    case_help_examples_pass_gates()
    case_phase_close_sid_invalid_and_quoting()
    case_audit_event_payload_validation()
    case_the_source_check_true_read_only()
    print("PC CLI ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
