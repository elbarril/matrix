#!/usr/bin/env python3
"""A — link_append annotates session_id=<sid> in the Link ledger.

(a) `matrix link route` writes the session_id from the ambient resolution
    (fixture marker test-session-001).
(b) `matrix link handoff` whose detail already carries session_id=custom-sid
    keeps EXACTLY ONE session_id (the guard must not duplicate).
(c) `matrix phase close` with payload session_id=sid-B writes session_id=sid-B
    on the phase:close line (the payload sid wins over the ambient marker).
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
MARKER_SID = "test-session-001"


def run_cli(fixture_root, home_dir, cmd, cwd=None, env_overrides=None):
    matrix_bin = fixture_root / "bin" / "matrix"
    env = os.environ.copy()
    env["MATRIX_ROOT"] = str(fixture_root)
    env["HOME"] = str(home_dir)
    env["XDG_CONFIG_HOME"] = str(home_dir / ".config")
    env["SOURCE_DATE_EPOCH"] = "1704067200"
    env["TZ"] = "UTC"
    env.update(env_overrides or {})
    return subprocess.run(
        [str(matrix_bin)] + cmd,
        cwd=str(cwd or fixture_root),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


def lines_for_event(fixture_root, event):
    log = fixture_root / "brain" / "state" / "activity.log"
    if not log.is_file():
        return []
    out = []
    for line in log.read_text(encoding="utf-8").splitlines():
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 3 and parts[1] == event:
            out.append(line)
    return out


def case_link_route_annotates_sid():
    with tempfile.TemporaryDirectory(prefix="lsid-route-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        marker = fixture_root / "brain" / "state" / ".current-hook-session"
        assert marker.read_text(encoding="utf-8").strip() == MARKER_SID, \
            f"fixture marker changed: {marker.read_text()!r}"
        proc = run_cli(
            fixture_root, home_dir,
            ["link", "route", "primary-retirement", "--ref=refroute123",
             "Morpheus -> Architect -> Trinity -> Smith"],
        )
        assert proc.returncode == 0, f"{proc.stdout} {proc.stderr}"
        routes = lines_for_event(fixture_root, "route")
        assert routes, "no route line in ledger"
        assert any(f"session_id={MARKER_SID}" in line for line in routes), routes
        print("A LINK ROUTE ANNOTATES SID PASS")


def case_link_handoff_existing_sid_not_duplicated():
    with tempfile.TemporaryDirectory(prefix="lsid-handoff-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        proc = run_cli(
            fixture_root, home_dir,
            ["link", "handoff", "matrix", "--ref=refhandoff123",
             "Trinity -> Smith con e2e session_id=custom-sid"],
        )
        assert proc.returncode == 0, f"{proc.stdout} {proc.stderr}"
        handoffs = lines_for_event(fixture_root, "handoff")
        assert handoffs, "no handoff line in ledger"
        line = handoffs[-1]
        assert line.count("session_id=") == 1, line
        assert "session_id=custom-sid" in line, line
        assert f"session_id={MARKER_SID}" not in line, line
        print("A LINK HANDOFF EXISTING SID NOT DUPLICATED PASS")


def case_link_decision_prose_sid_still_annotates():
    with tempfile.TemporaryDirectory(prefix="lsid-prose-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        proc = run_cli(
            fixture_root, home_dir,
            ["link", "decision", "matrix", "--ref=refprose123",
             "nota que menciona session_id=otro-valor en prosa"],
        )
        assert proc.returncode == 0, f"{proc.stdout} {proc.stderr}"
        decisions = lines_for_event(fixture_root, "decision")
        assert decisions, "no decision line in ledger"
        line = decisions[-1]
        assert "session_id=otro-valor" in line, line
        assert line.rstrip().split()[-1] == f"session_id={MARKER_SID}", line
        print("A LINK DECISION PROSE SID STILL ANNOTATES PASS")


def case_phase_close_payload_sid_wins():
    with tempfile.TemporaryDirectory(prefix="lsid-close-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        payload = '{"phase":"develop","e2e":true,"evidence":"ran link-session-id close; 3/3 passed","session_id":"sid-B"}'
        proc = run_cli(fixture_root, home_dir, ["phase", "close", payload])
        assert proc.returncode == 0, f"{proc.stdout} {proc.stderr}"
        assert '"verdict": "PASS"' in proc.stdout, proc.stdout
        closes = lines_for_event(fixture_root, "phase:close")
        assert closes, "no phase:close line in ledger"
        line = closes[-1]
        assert "session_id=sid-B" in line, line
        assert f"session_id={MARKER_SID}" not in line, line
        print("A PHASE CLOSE PAYLOAD SID WINS PASS")


def configure_alpha(fixture_root):
    registry = fixture_root / ".registry.json"
    registry.write_text(json.dumps({"projects": [{"name": "alpha", "path": str(fixture_root / "projects" / "alpha"), "type": "local"}]}))


def case_focus_mints_fallback_without_marker():
    with tempfile.TemporaryDirectory(prefix="lsid-focus-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        marker = fixture_root / "brain" / "state" / ".current-hook-session"
        marker.unlink()
        configure_alpha(fixture_root)
        proc = run_cli(fixture_root, home_dir, ["focus", "alpha"])
        assert proc.returncode == 0, f"{proc.stdout} {proc.stderr}"
        sid = marker.read_text(encoding="utf-8")
        assert sid.startswith("manual-") and len(sid) == 19, sid
        focus_file = fixture_root / "brain" / "state" / "sessions" / f"{sid}.json"
        focus = json.loads(focus_file.read_text(encoding="utf-8"))
        assert focus["session_id"] == sid and focus["focused_project"] == "alpha"
        scope = run_cli(fixture_root, home_dir, ["scope", "--tree", "--json"])
        assert json.loads(scope.stdout)["subject"] == "alpha", scope.stdout
        again = run_cli(fixture_root, home_dir, ["focus", "alpha"])
        assert again.returncode == 0 and marker.read_text(encoding="utf-8") == sid
        print("A FOCUS FALLBACK SESSION PASS")


def case_focus_preserves_explicit_session_sources():
    with tempfile.TemporaryDirectory(prefix="lsid-focus-explicit-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        configure_alpha(fixture_root)
        marker = fixture_root / "brain" / "state" / ".current-hook-session"
        proc = run_cli(fixture_root, home_dir, ["focus", "alpha"])
        assert proc.returncode == 0
        assert marker.read_text(encoding="utf-8") == MARKER_SID
        assert (fixture_root / "brain" / "state" / "sessions" / f"{MARKER_SID}.json").is_file()
        marker.unlink()
        proc = run_cli(fixture_root, home_dir, ["focus", "alpha"], env_overrides={"MATRIX_SESSION_ID": "explicit-sid"})
        assert proc.returncode == 0 and not marker.exists()
        assert (fixture_root / "brain" / "state" / "sessions" / "explicit-sid.json").is_file()
        print("A FOCUS EXPLICIT SESSION SOURCES PASS")


def case_focus_blocks_ambiguous_bindings():
    with tempfile.TemporaryDirectory(prefix="lsid-focus-ambiguous-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        configure_alpha(fixture_root)
        marker = fixture_root / "brain" / "state" / ".current-hook-session"
        marker.unlink()
        sessions = fixture_root / "brain" / "state" / "sessions"
        sessions.mkdir(exist_ok=True)
        now = "2099-01-01T00:00:00+00:00"
        for sid in ("one", "two"):
            (sessions / f"{sid}-binding.json").write_text(json.dumps({"session_id": sid, "last_seen_at": now}))
        proc = run_cli(fixture_root, home_dir, ["focus", "alpha"])
        assert proc.returncode != 0 and "ambiguous" in proc.stdout
        assert not marker.exists() and not list(sessions.glob("manual-*.json"))
        print("A FOCUS AMBIGUOUS BINDINGS BLOCK PASS")


def main():
    assert REPO_ROOT != Path("/tmp").resolve(), "repo root must not be /tmp"
    case_link_route_annotates_sid()
    case_link_handoff_existing_sid_not_duplicated()
    case_link_decision_prose_sid_still_annotates()
    case_phase_close_payload_sid_wins()
    case_focus_mints_fallback_without_marker()
    case_focus_preserves_explicit_session_sources()
    case_focus_blocks_ambiguous_bindings()
    print("A LINK SESSION-ID ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
