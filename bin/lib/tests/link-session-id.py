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


def main():
    assert REPO_ROOT != Path("/tmp").resolve(), "repo root must not be /tmp"
    case_link_route_annotates_sid()
    case_link_handoff_existing_sid_not_duplicated()
    case_phase_close_payload_sid_wins()
    print("A LINK SESSION-ID ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
