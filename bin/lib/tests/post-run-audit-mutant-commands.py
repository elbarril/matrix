#!/usr/bin/env python3
"""C — write-target tokenizer + mutant-command detector (G3 ciclo A).

Covers the two sides of the mutant-command gate plus the tokenizer that feeds
it, on a temporary fixture root (never the real brain/state):

  * tokenizer unit: glued control operators are split (`clean;` -> `clean`,
    `;`), so `rm -rf temp clean; cd <root>` yields only `temp`, `clean`, and
    `cd /x` alone yields nothing; `dd`'s write target is the `of=` operand
    only (`if=` and loose operands are ignored);
  * detector false-positive side: `cd <root>` alone, an `rm` outside the root,
    and an unresolved `$FR/...` target must all stay compliant, with the
    unresolved target surfaced in `unresolved_shell_var_targets`;
  * detector negative side: the full battery of 10 in-root write commands
    (redirection, append, rm, rm -rf, cp, mv, tee, sed -i, truncate, dd of=)
    must all remain anomalies (compliant: false), and `dd of=/tmp/x` (outside
    the root) must NOT be an anomaly.
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
REQUIRED_STEPS = ["load_config", "resolve_context", "pre_activation_check"]

# Load the real tokenizer from the repo hooks (same code the adapter imports).
_tokenizer_spec = importlib.util.spec_from_file_location(
    "_tokenizer", REPO_ROOT / "hooks" / "_tokenizer.py"
)
_tokenizer = importlib.util.module_from_spec(_tokenizer_spec)
_tokenizer_spec.loader.exec_module(_tokenizer)


# The full negative battery: every command writes to a path that resolves
# inside the Matrix root and is not sanctioned, so each must be an anomaly.
NEGATIVE_BATTERY = [
    "echo x > brain/state/y",
    "echo x >> brain/state/y",
    "rm important_file",
    "rm -rf brain/state/old/",
    "cp a brain/state/b",
    "mv a brain/state/b",
    "tee brain/state/u",
    "sed -i s/x/y/ brain/state/z",
    "truncate -s 0 brain/state/w",
    "dd of=brain/state/v",
]


def run_hook(fixture_root, home_dir, payload):
    hook = fixture_root / "hooks" / "post_run_audit.py"
    env = os.environ.copy()
    env["MATRIX_ROOT"] = str(fixture_root)
    env["HOME"] = str(home_dir)
    env["SOURCE_DATE_EPOCH"] = "1704067200"
    env["TZ"] = "UTC"
    return subprocess.run(
        ["python3", str(hook), json.dumps(payload)],
        cwd=str(fixture_root),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


def write_audit(fixture_root, session_id, events):
    log = fixture_root / "brain" / "state" / "hook-audit.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")


def exec_event(session_id, command, fixture_root, ts):
    """Emulate what session_audit.py persists for a shell-like tool event."""
    targets, unparsed = _tokenizer.write_targets(command, str(fixture_root))
    return {
        "event": "post_tool_use",
        "session_id": session_id,
        "tool_name": "exec",
        "tool_paths": targets,
        "tool_command_head": " ".join(command.split()[:2]),
        "tool_command_unparsed": unparsed,
        "timestamp": ts,
    }


def neo_payload(session_id):
    return {
        "agent": "neo",
        "profile": "neo",
        "session_id": session_id,
        "steps": list(REQUIRED_STEPS),
    }


def case_tokenizer_units():
    root = "/home/emiliano/www/emisrepos/matrix"

    targets, unparsed = _tokenizer.write_targets(
        "rm -rf temp clean; cd /home/emiliano/www/emisrepos/matrix", root
    )
    assert targets == ["temp", "clean"], f"expected ['temp','clean'], got {targets}"
    assert unparsed is False, f"expected parsed, got unparsed"
    assert "cd" not in targets and "/home/emiliano/www/emisrepos/matrix" not in targets

    targets2, unparsed2 = _tokenizer.write_targets("cd /x", root)
    assert targets2 == [], f"expected [], got {targets2}"
    assert unparsed2 is False

    # dd: only `of=` is a write target; `if=` and loose operands are not.
    targets3, unparsed3 = _tokenizer.write_targets("dd of=brain/state/v", root)
    assert targets3 == ["brain/state/v"], f"expected ['brain/state/v'], got {targets3}"
    assert unparsed3 is False

    targets4, unparsed4 = _tokenizer.write_targets("dd of=/tmp/x", root)
    assert targets4 == ["/tmp/x"], f"expected ['/tmp/x'], got {targets4}"
    assert unparsed4 is False

    targets5, unparsed5 = _tokenizer.write_targets(
        "dd if=brain/state/a of=brain/state/v", root
    )
    assert targets5 == ["brain/state/v"], f"expected ['brain/state/v'], got {targets5}"
    assert unparsed5 is False

    targets6, unparsed6 = _tokenizer.write_targets("dd if=brain/state/a", root)
    assert targets6 == [], f"expected [] (if= is not a write target), got {targets6}"
    assert unparsed6 is False
    print("C TOKENIZER UNIT ASSERTS PASS")


def case_detector_false_positive_side_compliant():
    with tempfile.TemporaryDirectory(prefix="g3a-fp-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        session_id = "g3a-fp"
        root = str(fixture_root)
        events = [
            exec_event(session_id, f"cd {root}", fixture_root, "2026-01-01T00:00:01+00:00"),
            exec_event(session_id, f"rm -rf /tmp/temp /tmp/clean; cd {root}", fixture_root, "2026-01-01T00:00:02+00:00"),
            exec_event(session_id, "echo x > $FR/brain/state/x", fixture_root, "2026-01-01T00:00:03+00:00"),
        ]
        write_audit(fixture_root, session_id, events)
        proc = run_hook(fixture_root, home_dir, neo_payload(session_id))
        result = json.loads(proc.stdout)
        assert proc.returncode == 0, f"expected exit 0, got {proc.returncode}: {proc.stdout}"
        assert result["ok"] is True, f"expected ok:true: {result}"
        assert result["compliant"] is True, f"expected compliant:true: {result}"
        assert result["mutant_command_anomalies"] == [], result["mutant_command_anomalies"]
        unresolved = result["unresolved_shell_var_targets"]
        assert unresolved, f"expected unresolved bucket non-empty: {result}"
        assert any(
            entry.get("target") == "$FR/brain/state/x" and entry.get("head") == "echo x"
            for entry in unresolved
        ), f"expected $FR target in bucket, got {unresolved}"
        print("C DETECTOR FALSE-POSITIVE SIDE COMPLIANT PASS")


def case_detector_full_negative_battery():
    with tempfile.TemporaryDirectory(prefix="g3a-neg-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        session_id = "g3a-neg"
        events = [
            exec_event(session_id, command, fixture_root, f"2026-01-01T00:00:{i + 1:02d}+00:00")
            for i, command in enumerate(NEGATIVE_BATTERY)
        ]
        write_audit(fixture_root, session_id, events)
        proc = run_hook(fixture_root, home_dir, neo_payload(session_id))
        result = json.loads(proc.stdout)
        assert proc.returncode == 1, f"expected exit 1, got {proc.returncode}: {proc.stdout}"
        assert result["ok"] is False, f"expected ok:false: {result}"
        assert result["compliant"] is False, f"expected compliant:false: {result}"
        anomalies = result["mutant_command_anomalies"]
        assert len(anomalies) == len(NEGATIVE_BATTERY), (
            f"expected {len(NEGATIVE_BATTERY)} anomalies, got {len(anomalies)}: {anomalies}"
        )
        expected_heads = set(" ".join(c.split()[:2]) for c in NEGATIVE_BATTERY)
        seen_heads = set(anomalies)
        missing = sorted(expected_heads - seen_heads)
        assert not missing, f"missing anomaly heads: {missing}; got {anomalies}"
        assert result["unresolved_shell_var_targets"] == [], (
            f"expected empty bucket, got {result['unresolved_shell_var_targets']}"
        )
        print("C DETECTOR FULL NEGATIVE BATTERY (10/10) NON-COMPLIANT PASS")


def case_dd_absolute_outside_root_is_not_anomaly():
    with tempfile.TemporaryDirectory(prefix="g3a-ddabs-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        session_id = "g3a-ddabs"
        events = [
            exec_event(session_id, "dd of=/tmp/x", fixture_root, "2026-01-01T00:00:01+00:00"),
        ]
        write_audit(fixture_root, session_id, events)
        proc = run_hook(fixture_root, home_dir, neo_payload(session_id))
        result = json.loads(proc.stdout)
        assert proc.returncode == 0, f"expected exit 0, got {proc.returncode}: {proc.stdout}"
        assert result["ok"] is True, f"expected ok:true: {result}"
        assert result["compliant"] is True, f"expected compliant:true: {result}"
        assert result["mutant_command_anomalies"] == [], result["mutant_command_anomalies"]
        assert result["unresolved_shell_var_targets"] == [], result["unresolved_shell_var_targets"]
        print("C DD ABSOLUTE OUTSIDE ROOT STAYS COMPLIANT PASS")


def case_dd_in_root_target_anomaly():
    with tempfile.TemporaryDirectory(prefix="g3a-ddroot-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        session_id = "g3a-ddroot"
        command = "dd if=brain/state/a of=brain/state/v"
        events = [
            exec_event(session_id, command, fixture_root, "2026-01-01T00:00:01+00:00"),
        ]
        write_audit(fixture_root, session_id, events)
        proc = run_hook(fixture_root, home_dir, neo_payload(session_id))
        result = json.loads(proc.stdout)
        assert proc.returncode == 1, f"expected exit 1, got {proc.returncode}: {proc.stdout}"
        assert result["ok"] is False, f"expected ok:false: {result}"
        assert result["compliant"] is False, f"expected compliant:false: {result}"
        assert result["mutant_command_anomalies"] == ["dd if=brain/state/a"], (
            result["mutant_command_anomalies"]
        )
        print("C DD IN-ROOT TARGET IS ANOMALY PASS")


def main():
    assert REPO_ROOT != Path("/tmp").resolve(), "repo root must not be /tmp"
    case_tokenizer_units()
    case_detector_false_positive_side_compliant()
    case_detector_full_negative_battery()
    case_dd_absolute_outside_root_is_not_anomaly()
    case_dd_in_root_target_anomaly()
    print("C POST-RUN-AUDIT MUTANT-COMMANDS ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
