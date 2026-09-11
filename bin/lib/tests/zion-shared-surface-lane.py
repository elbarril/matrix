#!/usr/bin/env python3
"""Q2-D — shared-surface gate + writer lane (done-criteria D2-D8).

Builds a fixture tree with its own brain/state/ and MATRIX_ROOT (never the
real repo), then runs the real Devin adapter guard
(adapters/devin/hooks/pre_tool_use_guard.py) with simulated PreToolUse
payloads and verifies the exit code + JSON decision + produced lane / audit /
activity.log files of the fixture.

Cases (spec 4.a / 4.b):
  (i)     project + edit AGENTS.md                → exit 2, audit shared_surface_block:AGENTS.md
  (ii)    project + write lessons.md (promotion)  → exit 0, lane held by sid
  release-1  PostToolUse of the same tool+paths   → lane released
  (iii)   workspace + edit brain/agents/neo.md    → exit 0, lane held by sid
  release-2  SessionEnd of that session           → all lanes of sid released
  (iv)    project + write normal project file     → exit 0, no lane file, no scope subprocess
  (v)     lane held by another sid (fresh)        → exit 2, writer_lane_busy, exactly 1 incident
  (vi)    stale lane (> TTL)                      → exit 0, lane reclaimed by new holder
"""
import importlib.util
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path


smoke_path = Path(__file__).resolve().parent / "smoke-matrix-help.py"
spec = importlib.util.spec_from_file_location("smoke_matrix_help", smoke_path)
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)

REPO_ROOT = smoke.repo_root_from_script()
GUARD = REPO_ROOT / "adapters" / "devin" / "hooks" / "pre_tool_use_guard.py"
SESSION_AUDIT = REPO_ROOT / "adapters" / "devin" / "hooks" / "session_audit.py"

MATRIX_BEGIN = "<!-- MATRIX:BEGIN"
MATRIX_END = "<!-- MATRIX:END -->"


# --- fixture helpers --------------------------------------------------------

def lane_for(fixture_root, rel_path):
    digest = hashlib.sha1(rel_path.encode("utf-8")).hexdigest()[:16]
    return fixture_root / "brain" / "state" / "lanes" / f"{digest}.json"


def write_lane_file(fixture_root, rel_path, holder, age_s=0):
    path = lane_for(fixture_root, rel_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "session_id": holder,
        "timestamp": (datetime.now(timezone.utc) - timedelta(seconds=age_s)).isoformat(),
        "rel_path": rel_path,
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def clear_lanes(fixture_root):
    lanes_dir = fixture_root / "brain" / "state" / "lanes"
    if not lanes_dir.is_dir():
        return
    for f in lanes_dir.iterdir():
        if f.suffix == ".json":
            f.unlink()


def build_fixture(root):
    """Build a Q2-D fixture tree rooted at `root` (a Path). Returns home_dir."""
    home_dir = smoke.build_fixture(REPO_ROOT, root)
    # Register one real project "demo" (local). No filesystem binding
    # (_brain/AGENTS.local.md) exists anymore — scope resolves by registry path.
    registry = {
        "projects": [
            {
                "name": "demo",
                "path": str(root / "projects" / "demo"),
                "type": "local",
            }
        ],
        "created": "2024-01-01T00:00:00+00:00",
        "version": "2.0.0",
    }
    (root / ".registry.json").write_text(json.dumps(registry), encoding="utf-8")
    demo = root / "projects" / "demo"
    demo.mkdir(parents=True, exist_ok=True)
    (demo / "src").mkdir(parents=True, exist_ok=True)
    (demo / "src" / "app.py").write_text("print('x')\n", encoding="utf-8")
    return home_dir


def env_for(fixture_root, home_dir, extra=None):
    env = os.environ.copy()
    env.update({"MATRIX_GATE_SHARED_SURFACE": "1", "MATRIX_GATE_WRITER_LANE": "1", "MATRIX_GATE_PRE_EXEC_GUARD": "1"})
    env["MATRIX_ROOT"] = str(fixture_root)
    env["HOME"] = str(home_dir)
    env["XDG_CONFIG_HOME"] = str(home_dir / ".config")
    env["SOURCE_DATE_EPOCH"] = "1704067200"
    env["TZ"] = "UTC"
    env["DEVIN_BIN"] = str(fixture_root / "bin" / "fake-devin")
    env["PATH"] = f"{fixture_root / 'bin'}:{env.get('PATH', '')}"
    if extra:
        env.update(extra)
    return env


def run_guard(fixture_root, home_dir, cwd, payload, env_extra=None):
    env = env_for(fixture_root, home_dir, env_extra)
    return subprocess.run(
        ["python3", str(GUARD)],
        cwd=str(cwd),
        env=env,
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=120,
    )


def run_audit(fixture_root, home_dir, cwd, payload):
    env = env_for(fixture_root, home_dir)
    return subprocess.run(
        ["python3", str(SESSION_AUDIT)],
        cwd=str(cwd),
        env=env,
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=180,
    )


def audit_entries(fixture_root):
    path = fixture_root / "brain" / "state" / "hook-audit.jsonl"
    if not path.is_file():
        return []
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except ValueError:
            continue
    return entries


def activity_lines(fixture_root):
    path = fixture_root / "brain" / "state" / "activity.log"
    if not path.is_file():
        return []
    return path.read_text(encoding="utf-8").splitlines()


def incident_count(fixture_root):
    return sum(1 for line in activity_lines(fixture_root) if "incident:writer-collision" in line)


# --- cases ------------------------------------------------------------------

def case_bound_block_agents(fixture_root, home_dir):
    cwd = fixture_root / "projects" / "demo"
    payload = {
        "tool_name": "edit",
        "tool_input": {
            "file_path": str(fixture_root / "AGENTS.md"),
            "old_string": "x",
            "new_string": "y",
        },
        "session_id": "sid-i",
    }
    proc = run_guard(fixture_root, home_dir, cwd, payload)
    result = json.loads(proc.stdout)
    assert proc.returncode == 2, f"(i) expected exit 2, got {proc.returncode}: {proc.stdout} {proc.stderr}"
    assert result["decision"] == "block", result
    assert "AGENTS.md" in result["reason"], result
    entries = audit_entries(fixture_root)
    last = entries[-1]
    assert last["event"] == "pre_tool_use_guard_decision", last
    assert last["session_id"] == "sid-i", last
    assert last["guard_decision"] == "block", last
    assert last["guard_reason"] == "shared_surface_block:AGENTS.md", last
    print("(i) PASS project edit AGENTS.md → exit 2, shared_surface_block:AGENTS.md")


def case_bound_promote_lessons(fixture_root, home_dir):
    cwd = fixture_root / "projects" / "demo"
    payload = {
        "tool_name": "write",
        "tool_input": {
            "file_path": str(fixture_root / "brain" / "data" / "lessons.md"),
            "content": "x",
        },
        "session_id": "sid-ii",
    }
    proc = run_guard(fixture_root, home_dir, cwd, payload)
    assert proc.returncode == 0, f"(ii) expected exit 0: {proc.stdout} {proc.stderr}"
    result = json.loads(proc.stdout)
    assert result["decision"] == "allow", result
    lp = lane_for(fixture_root, "brain/data/lessons.md")
    assert lp.is_file(), f"(ii) lane file missing: {lp}"
    data = json.loads(lp.read_text(encoding="utf-8"))
    assert data["session_id"] == "sid-ii", data
    print("(ii) PASS project promote lessons.md → allow + lane held by sid-ii")


def case_release_post_tool_use(fixture_root, home_dir):
    cwd = fixture_root / "projects" / "demo"
    lp = lane_for(fixture_root, "brain/data/lessons.md")
    assert lp.is_file(), "release-1 pre: lane missing"
    payload = {
        "hook_event_name": "PostToolUse",
        "tool_name": "write",
        "tool_input": {
            "file_path": str(fixture_root / "brain" / "data" / "lessons.md"),
            "content": "x",
        },
        "session_id": "sid-ii",
    }
    proc = run_audit(fixture_root, home_dir, cwd, payload)
    assert proc.returncode == 0, f"release-1 failed: {proc.stdout} {proc.stderr}"
    assert not lp.is_file(), "release-1: lane not released"
    print("release-1 PASS PostToolUse releases lane (holder == sid)")


def case_workspace_edit_surface(fixture_root, home_dir):
    cwd = fixture_root
    payload = {
        "tool_name": "edit",
        "tool_input": {
            "file_path": str(fixture_root / "brain" / "agents" / "neo.md"),
            "old_string": "a",
            "new_string": "b",
        },
        "session_id": "sid-iii",
    }
    proc = run_guard(fixture_root, home_dir, cwd, payload)
    assert proc.returncode == 0, f"(iii) expected exit 0: {proc.stdout} {proc.stderr}"
    result = json.loads(proc.stdout)
    assert result["decision"] == "allow", result
    lp = lane_for(fixture_root, "brain/agents/neo.md")
    assert lp.is_file(), "(iii) lane file missing"
    data = json.loads(lp.read_text(encoding="utf-8"))
    assert data["session_id"] == "sid-iii", data
    print("(iii) PASS workspace edit surface → allow + lane held by sid-iii")


def case_release_session_end(fixture_root, home_dir):
    cwd = fixture_root
    lp = lane_for(fixture_root, "brain/agents/neo.md")
    assert lp.is_file(), "release-2 pre: lane missing"
    payload = {
        "hook_event_name": "SessionEnd",
        "session_id": "sid-iii",
    }
    proc = run_audit(fixture_root, home_dir, cwd, payload)
    assert proc.returncode == 0, f"release-2 failed: {proc.stdout} {proc.stderr}"
    assert not lp.is_file(), "release-2: lane not released"
    print("release-2 PASS SessionEnd releases all lanes of sid-iii")


def case_bound_edit_non_surface(fixture_root, home_dir):
    cwd = fixture_root / "projects" / "demo"
    matrix_bin = fixture_root / "bin" / "matrix"
    marker = fixture_root / "brain" / "state" / "scope-stub-invoked"
    backup = fixture_root / "bin" / "matrix.real"
    shutil.copy2(matrix_bin, backup)
    stub = ("#!/bin/bash\n"
            "echo \"$(date +%s) $*\" >> \"$MATRIX_ROOT/brain/state/scope-stub-invoked\"\n"
            "exit 1\n")
    matrix_bin.write_text(stub, encoding="utf-8")
    matrix_bin.chmod(0o755)
    try:
        payload = {
            "tool_name": "write",
            "tool_input": {
                "file_path": str(fixture_root / "projects" / "demo" / "src" / "app.py"),
                "content": "x",
            },
            "session_id": "sid-iv",
        }
        proc = run_guard(fixture_root, home_dir, cwd, payload)
        assert proc.returncode == 0, f"(iv) expected exit 0: {proc.stdout} {proc.stderr}"
        result = json.loads(proc.stdout)
        assert result["decision"] == "allow", result
        assert not marker.is_file(), "(iv) bin/matrix scope was invoked"
        lanes_dir = fixture_root / "brain" / "state" / "lanes"
        leftovers = [p for p in lanes_dir.iterdir() if p.suffix == ".json"] if lanes_dir.is_dir() else []
        assert not leftovers, f"(iv) unexpected lane files: {leftovers}"
        print("(iv) PASS project non-surface write → allow, no lane, no scope subprocess")
    finally:
        shutil.copy2(backup, matrix_bin)
        matrix_bin.chmod(0o755)
        backup.unlink()
        if marker.exists():
            marker.unlink()


def case_lane_busy(fixture_root, home_dir):
    cwd = fixture_root / "projects" / "demo"
    clear_lanes(fixture_root)
    rel = "brain/data/lessons.md"
    write_lane_file(fixture_root, rel, "other-sid", age_s=0)
    payload = {
        "tool_name": "write",
        "tool_input": {
            "file_path": str(fixture_root / "brain" / "data" / "lessons.md"),
            "content": "x",
        },
        "session_id": "sid-v",
    }
    proc = run_guard(fixture_root, home_dir, cwd, payload)
    assert proc.returncode == 2, f"(v) expected exit 2: {proc.stdout} {proc.stderr}"
    result = json.loads(proc.stdout)
    assert result["decision"] == "block", result
    assert "writer lane busy" in result["reason"], result
    assert "other-sid" in result["reason"], result
    assert "since" in result["reason"], result
    entries = audit_entries(fixture_root)
    last = entries[-1]
    assert last["guard_reason"] == "writer_lane_busy:brain/data/lessons.md", last
    assert "other-sid" not in last["guard_reason"], "sid must never leak to the audit log"
    assert incident_count(fixture_root) == 1, f"(v) expected exactly 1 incident"
    print("(v) PASS lane busy → exit 2, writer_lane_busy, 1 incident")


def case_lane_stale(fixture_root, home_dir):
    cwd = fixture_root / "projects" / "demo"
    clear_lanes(fixture_root)
    rel = "brain/data/lessons.md"
    write_lane_file(fixture_root, rel, "other-sid", age_s=10000)
    payload = {
        "tool_name": "write",
        "tool_input": {
            "file_path": str(fixture_root / "brain" / "data" / "lessons.md"),
            "content": "x",
        },
        "session_id": "sid-vi",
    }
    proc = run_guard(fixture_root, home_dir, cwd, payload)
    assert proc.returncode == 0, f"(vi) expected exit 0: {proc.stdout} {proc.stderr}"
    result = json.loads(proc.stdout)
    assert result["decision"] == "allow", result
    lp = lane_for(fixture_root, rel)
    assert lp.is_file(), "(vi) lane file missing"
    data = json.loads(lp.read_text(encoding="utf-8"))
    assert data["session_id"] == "sid-vi", data
    assert not (lp.parent / (lp.name + ".stale")).exists(), "(vi) stale marker not cleaned"
    print("(vi) PASS stale lane reclaimed → allow + lane held by sid-vi")


def case_extras(fixture_root, home_dir):
    """Extra checks beyond the spec 4.a cases (spec 1.d/1.e + kill-switch)."""
    cwd = fixture_root / "projects" / "demo"

    # x1: project edit its own project lesson file → allow + lane.
    clear_lanes(fixture_root)
    payload = {
        "tool_name": "write",
        "tool_input": {"file_path": str(fixture_root / "brain" / "data" / "lessons" / "demo.md"), "content": "x"},
        "session_id": "sid-x1",
    }
    proc = run_guard(fixture_root, home_dir, cwd, payload)
    assert proc.returncode == 0, f"(x1) expected allow: {proc.stdout} {proc.stderr}"
    assert lane_for(fixture_root, "brain/data/lessons/demo.md").is_file(), "(x1) lane missing"
    print("x1 PASS project edit own project lesson → allow + lane")

    # x2: project edit ANOTHER project lesson → block.
    clear_lanes(fixture_root)
    payload2 = {
        "tool_name": "write",
        "tool_input": {"file_path": str(fixture_root / "brain" / "data" / "lessons" / "other.md"), "content": "x"},
        "session_id": "sid-x2",
    }
    proc2 = run_guard(fixture_root, home_dir, cwd, payload2)
    assert proc2.returncode == 2, f"(x2) expected block: {proc2.stdout} {proc2.stderr}"
    r2 = json.loads(proc2.stdout)
    assert "brain/data/lessons/other.md" in r2["reason"], r2
    assert audit_entries(fixture_root)[-1]["guard_reason"] == "shared_surface_block:brain/data/lessons/other.md"
    print("x2 PASS project edit other project lesson → block")

    # x3: kill-switch bypasses the project block but NOT the lane.
    clear_lanes(fixture_root)
    write_lane_file(fixture_root, "AGENTS.md", "holder-kill", age_s=0)
    payload3 = {
        "tool_name": "edit",
        "tool_input": {"file_path": str(fixture_root / "AGENTS.md"), "old_string": "x", "new_string": "y"},
        "session_id": "sid-x3",
    }
    proc3 = run_guard(fixture_root, home_dir, cwd, payload3, env_extra={"MATRIX_SHARED_SURFACE_ALLOW": "1"})
    assert proc3.returncode == 2, f"(x3) kill-switch must NOT bypass the lane: {proc3.stdout} {proc3.stderr}"
    r3 = json.loads(proc3.stdout)
    assert "writer lane busy" in r3["reason"], r3
    assert audit_entries(fixture_root)[-1]["guard_reason"] == "writer_lane_busy:AGENTS.md"
    print("x3 PASS kill-switch bypasses project block but NOT the lane")

    # x4: kill-switch allows a blocked project write when the lane is free.
    clear_lanes(fixture_root)
    payload4 = {
        "tool_name": "edit",
        "tool_input": {"file_path": str(fixture_root / "AGENTS.md"), "old_string": "x", "new_string": "y"},
        "session_id": "sid-x4",
    }
    proc4 = run_guard(fixture_root, home_dir, cwd, payload4, env_extra={"MATRIX_SHARED_SURFACE_ALLOW": "true"})
    assert proc4.returncode == 0, f"(x4) kill-switch should allow: {proc4.stdout} {proc4.stderr}"
    assert lane_for(fixture_root, "AGENTS.md").is_file(), "(x4) lane missing"
    print("x4 PASS kill-switch allows blocked project write under lane")

    # x5: an unregistered cwd inside a registered ancestor falls back to the
    # ancestor as subject — it is still a `project` session, so core surface
    # stays blocked (the old bound-unregistered mode is gone).
    clear_lanes(fixture_root)
    sub = fixture_root / "projects" / "demo" / "sub"
    sub.mkdir(parents=True, exist_ok=True)
    payload5 = {
        "tool_name": "write",
        "tool_input": {"file_path": str(fixture_root / "brain" / "data" / "lessons" / "whatever.md"), "content": "x"},
        "session_id": "sid-x5",
    }
    proc5 = run_guard(fixture_root, home_dir, sub, payload5)
    assert proc5.returncode == 2, f"(x5) unregistered-subdir project lesson should block: {proc5.stdout} {proc5.stderr}"
    r5 = json.loads(proc5.stdout)
    assert "brain/data/lessons/whatever.md" in r5["reason"], r5
    print("x5 PASS unregistered-subdir edit project lesson → block (ancestor subject)")

    # x5b: unregistered-subdir promote core lessons.md → allow (still project mode).
    clear_lanes(fixture_root)
    payload5b = {
        "tool_name": "write",
        "tool_input": {"file_path": str(fixture_root / "brain" / "data" / "lessons.md"), "content": "x"},
        "session_id": "sid-x5b",
    }
    proc5b = run_guard(fixture_root, home_dir, sub, payload5b)
    assert proc5b.returncode == 0, f"(x5b) unregistered-subdir core lessons.md should allow: {proc5b.stdout} {proc5b.stderr}"
    print("x5b PASS unregistered-subdir promote core lessons.md → allow")


def case_latency(fixture_root, home_dir):
    """D14: measure guard latency on the fast and slow paths (spec 4.d)."""
    import time as _time

    cwd = fixture_root / "projects" / "demo"
    fast = {
        "tool_name": "write",
        "tool_input": {"file_path": str(fixture_root / "projects" / "demo" / "src" / "app.py"), "content": "x"},
        "session_id": "lat-fast",
    }
    slow = {
        "tool_name": "edit",
        "tool_input": {"file_path": str(fixture_root / "AGENTS.md"), "old_string": "a", "new_string": "b"},
        "session_id": "lat-slow",
    }
    results = {}
    for label, cwd_target, payload in (("fast", cwd, fast), ("slow", fixture_root, slow)):
        times = []
        for _ in range(7):
            t0 = _time.perf_counter()
            proc = run_guard(fixture_root, home_dir, cwd_target, payload)
            times.append((_time.perf_counter() - t0) * 1000)
            assert proc.returncode in (0, 2), proc.stdout
        times.sort()
        results[label] = times[len(times) // 2]
    # Generous bounds: both paths are far below the hook timeout (10s). The
    # spec's ~10ms fast-path estimate is dominated by python interpreter
    # startup; the guard itself adds no subprocess on the fast path.
    assert results["fast"] < 500, f"fast path too slow: {results['fast']:.1f} ms"
    assert results["slow"] < 5000, f"slow path too slow: {results['slow']:.1f} ms"
    print(f"latency PASS fast={results['fast']:.1f} ms slow={results['slow']:.1f} ms")


# --- main -------------------------------------------------------------------

def main():
    assert REPO_ROOT != Path("/tmp").resolve(), "repo root must not be /tmp"
    with tempfile.TemporaryDirectory(prefix="q2d-lane-") as td:
        fixture_root = Path(td)
        home_dir = build_fixture(fixture_root)

        case_bound_block_agents(fixture_root, home_dir)
        case_bound_promote_lessons(fixture_root, home_dir)
        case_release_post_tool_use(fixture_root, home_dir)
        case_workspace_edit_surface(fixture_root, home_dir)
        case_release_session_end(fixture_root, home_dir)
        case_bound_edit_non_surface(fixture_root, home_dir)
        case_lane_busy(fixture_root, home_dir)
        case_lane_stale(fixture_root, home_dir)

        # After (vi)'s normal acquisition, the incident count must still be 1
        # (collisions are only logged on real overlap, spec 2.c).
        assert incident_count(fixture_root) == 1, "incident count changed after normal acquisition"

        case_extras(fixture_root, home_dir)
        case_latency(fixture_root, home_dir)

        print("Q2-D ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
