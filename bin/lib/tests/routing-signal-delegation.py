#!/usr/bin/env python3
"""C — validate_routing_signal delegation verification (Opción C).

(a) route/handoff naming Smith with a real check token -> resolved=delegated.
(b) route/handoff naming Smith without a check token -> triggered with
    unverified_delegation:true.
(c) no route/handoff -> triggered.
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


def run_hook(fixture_root, env, session_id):
    hook = fixture_root / "hooks" / "validate_routing_signal.py"
    return subprocess.run(
        ["python3", str(hook), json.dumps({"session_id": session_id})],
        cwd=str(fixture_root),
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
    )


def fixture_env(fixture_root):
    env = os.environ.copy()
    env["MATRIX_ROOT"] = str(fixture_root)
    env["SOURCE_DATE_EPOCH"] = "1704067200"
    env["TZ"] = "UTC"
    return env


def write_audit(fixture_root, session_id, project=None):
    log = fixture_root / "brain" / "state" / "hook-audit.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    start = {"event": "session_start", "session_id": session_id,
             "pre_activation_check_ok": True, "timestamp": "2026-01-01T00:00:00+00:00"}
    if project:
        start["project_active"] = project
    entries = [
        start,
        {"event": "post_tool_use", "session_id": session_id,
         "tool_name": "edit", "tool_paths": ["docs/a.md"],
         "timestamp": "2026-01-01T00:00:01+00:00"},
        {"event": "post_tool_use", "session_id": session_id,
         "tool_name": "edit", "tool_paths": ["docs/b.md"],
         "timestamp": "2026-01-01T00:00:02+00:00"},
    ]
    log.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")


def write_activity(fixture_root, line):
    log = fixture_root / "brain" / "state" / "activity.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(line + "\n", encoding="utf-8")


def case_delegated_with_check():
    with tempfile.TemporaryDirectory(prefix="rs-delegated-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        env = fixture_env(fixture_root)
        env["HOME"] = str(home_dir)
        write_audit(fixture_root, "rs-a")
        write_activity(
            fixture_root,
            '[2026-01-01T00:00:01+00:00] | route | cronicas | Trinity -> Smith corre fidelity_check',
        )
        proc = run_hook(fixture_root, env, "rs-a")
        result = json.loads(proc.stdout)
        assert proc.returncode == 0, f"expected exit 0, got {proc.returncode}: {proc.stderr}"
        assert result["ok"] is True, f"expected ok:true: {result}"
        assert result["triggered"] is False, f"expected triggered:false: {result}"
        assert result["resolved"] == "delegated", f"expected resolved=delegated: {result}"
        assert result["unverified_delegation"] is False, f"expected unverified:false: {result}"
        print("C DELEGATED WITH CHECK PASS")


def case_delegated_without_check():
    with tempfile.TemporaryDirectory(prefix="rs-unverified-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        env = fixture_env(fixture_root)
        env["HOME"] = str(home_dir)
        write_audit(fixture_root, "rs-b")
        write_activity(
            fixture_root,
            '[2026-01-01T00:00:01+00:00] | route | cronicas | Trinity -> Smith',
        )
        proc = run_hook(fixture_root, env, "rs-b")
        result = json.loads(proc.stdout)
        assert proc.returncode == 0, f"expected exit 0, got {proc.returncode}: {proc.stderr}"
        assert result["triggered"] is True, f"expected triggered:true: {result}"
        assert result["resolved"] == "triggered", f"expected resolved=triggered: {result}"
        assert result["unverified_delegation"] is True, f"expected unverified:true: {result}"
        assert "delegación sin check verificado" in result["message"], result["message"]
        print("C DELEGATED WITHOUT CHECK PASS")


def case_no_delegation():
    with tempfile.TemporaryDirectory(prefix="rs-nodeleg-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        env = fixture_env(fixture_root)
        env["HOME"] = str(home_dir)
        write_audit(fixture_root, "rs-c")
        proc = run_hook(fixture_root, env, "rs-c")
        result = json.loads(proc.stdout)
        assert proc.returncode == 0, f"expected exit 0, got {proc.returncode}: {proc.stderr}"
        assert result["triggered"] is True, f"expected triggered:true: {result}"
        assert result["resolved"] == "triggered", f"expected resolved=triggered: {result}"
        assert result["unverified_delegation"] is False, f"expected unverified:false: {result}"
        assert "no Link route/handoff" in result["message"], result["message"]
        print("C NO DELEGATION PASS")


def case_prefers_verified_route():
    with tempfile.TemporaryDirectory(prefix="rs-verified-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        env = fixture_env(fixture_root)
        env["HOME"] = str(home_dir)
        write_audit(fixture_root, "rs-verified")
        write_activity(
            fixture_root,
            '[2026-01-01T00:00:01+00:00] | route | cronicas | Trinity -> Smith\n'
            '[2026-01-01T00:00:02+00:00] | handoff | cronicas | Trinity -> Smith con fidelity_check',
        )
        proc = run_hook(fixture_root, env, "rs-verified")
        result = json.loads(proc.stdout)
        assert proc.returncode == 0, f"expected exit 0, got {proc.returncode}: {proc.stderr}"
        assert result["triggered"] is False, f"expected triggered:false: {result}"
        assert result["resolved"] == "delegated", f"expected resolved=delegated: {result}"
        assert result["unverified_delegation"] is False, f"expected unverified:false: {result}"
        assert "fidelity_check" in result["delegation_evidence"], result["delegation_evidence"]
        print("C PREFERS VERIFIED ROUTE PASS")


def case_history_transitions():
    with tempfile.TemporaryDirectory(prefix="rs-transitions-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        env = fixture_env(fixture_root)
        env["HOME"] = str(home_dir)
        write_audit(fixture_root, "rs-tx")
        hist_path = fixture_root / "brain" / "state" / "routing-signal-history.jsonl"

        def records_for(sid):
            if not hist_path.is_file():
                return []
            return [json.loads(l) for l in hist_path.read_text(encoding="utf-8").splitlines()
                    if l.strip() and json.loads(l).get("session_id") == sid]

        proc = run_hook(fixture_root, env, "rs-tx")
        result = json.loads(proc.stdout)
        assert result["triggered"] is True, f"expected triggered:true: {result}"
        assert len(records_for("rs-tx")) == 1, records_for("rs-tx")
        run_hook(fixture_root, env, "rs-tx")
        assert len(records_for("rs-tx")) == 1, f"same state must not duplicate: {records_for('rs-tx')}"
        write_activity(
            fixture_root,
            '[2026-01-01T00:00:01+00:00] | route | cronicas | Trinity -> Smith con fidelity_check',
        )
        proc = run_hook(fixture_root, env, "rs-tx")
        result = json.loads(proc.stdout)
        assert result["triggered"] is False, f"expected triggered:false: {result}"
        assert result["resolved"] == "delegated", result
        tx = records_for("rs-tx")
        assert len(tx) == 2, f"expected transition record: {tx}"
        assert tx[-1]["triggered"] is False and tx[-1]["resolved"] == "delegated", tx
        run_hook(fixture_root, env, "rs-tx")
        assert len(records_for("rs-tx")) == 2, f"no duplicate after resolved: {records_for('rs-tx')}"
        print("C HISTORY TRANSITIONS PASS")


def case_count_consecutive_unresolved_sessions():
    with tempfile.TemporaryDirectory(prefix="rs-count-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        env = fixture_env(fixture_root)
        env["HOME"] = str(home_dir)
        sys.path.insert(0, str(REPO_ROOT / "hooks"))
        from validate_routing_signal import count_consecutive_unresolved_sessions
        hist = fixture_root / "brain" / "state" / "routing-signal-history.jsonl"
        hist.parent.mkdir(parents=True, exist_ok=True)

        # (a) resolved tail -> streak 0.
        records = [
            {"session_id": "s0", "triggered": True, "resolved": "triggered",
             "timestamp": "2026-01-01T00:00:00+00:00"},
            {"session_id": "s0", "triggered": False, "resolved": "delegated",
             "timestamp": "2026-01-01T00:00:01+00:00"},
        ]
        hist.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
        streak, unresolved = count_consecutive_unresolved_sessions(str(hist))
        assert streak == 0, f"expected streak 0 (last s0 resolved): {unresolved}"

        # (b) two consecutive unresolved in the tail -> 2.
        records = [
            {"session_id": "s1", "triggered": True, "resolved": "triggered",
             "timestamp": "2026-01-01T00:00:00+00:00"},
            {"session_id": "s2", "triggered": True, "resolved": "triggered",
             "timestamp": "2026-01-01T00:00:01+00:00"},
        ]
        hist.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
        streak, unresolved = count_consecutive_unresolved_sessions(str(hist))
        assert streak == 2, f"expected streak 2: {unresolved}"

        # (c) last-state-wins: s1 triggered(01) then delegated(02), s2
        #     triggered(03) -> streak 1 (s2 only; s1's last state is resolved).
        records = [
            {"session_id": "s1", "triggered": True, "resolved": "triggered",
             "timestamp": "2026-01-01T00:00:01+00:00"},
            {"session_id": "s1", "triggered": False, "resolved": "delegated",
             "timestamp": "2026-01-01T00:00:02+00:00"},
            {"session_id": "s2", "triggered": True, "resolved": "triggered",
             "timestamp": "2026-01-01T00:00:03+00:00"},
        ]
        hist.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
        streak, unresolved = count_consecutive_unresolved_sessions(str(hist))
        assert streak == 1, f"expected streak 1 (s2 only): {unresolved}"
        assert unresolved == ["s2"], unresolved

        # (d) exclude_session_id excludes the current session.
        streak, unresolved = count_consecutive_unresolved_sessions(str(hist), exclude_session_id="s2")
        assert streak == 0, f"expected streak 0 after excluding s2: {unresolved}"
        print("C COUNT CONSECUTIVE UNRESOLVED SESSIONS PASS")


def case_foreign_project_handoff_does_not_resolve():
    with tempfile.TemporaryDirectory(prefix="rs-foreign-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        env = fixture_env(fixture_root)
        env["HOME"] = str(home_dir)
        write_audit(fixture_root, "rs-foreign", project="matrix")
        write_activity(
            fixture_root,
            '[2026-01-01T00:00:01+00:00] | handoff | cronicas | Trinity -> Smith con fidelity_check',
        )
        proc = run_hook(fixture_root, env, "rs-foreign")
        result = json.loads(proc.stdout)
        assert proc.returncode == 0, f"expected exit 0, got {proc.returncode}: {proc.stderr}"
        assert result["triggered"] is True, f"foreign handoff must not resolve: {result}"
        assert result["resolved"] == "triggered", result
        assert result["unverified_delegation"] is False, result
        print("C FOREIGN PROJECT HANDOFF NO-RESOLVE PASS")


def case_own_project_handoff_resolves():
    with tempfile.TemporaryDirectory(prefix="rs-own-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        env = fixture_env(fixture_root)
        env["HOME"] = str(home_dir)
        write_audit(fixture_root, "rs-own", project="matrix")
        write_activity(
            fixture_root,
            '[2026-01-01T00:00:01+00:00] | handoff | cronicas | Trinity -> Smith con fidelity_check\n'
            '[2026-01-01T00:00:02+00:00] | handoff | matrix | Trinity -> Smith con fidelity_check',
        )
        proc = run_hook(fixture_root, env, "rs-own")
        result = json.loads(proc.stdout)
        assert proc.returncode == 0, f"expected exit 0, got {proc.returncode}: {proc.stderr}"
        assert result["triggered"] is False, f"own-project handoff must resolve: {result}"
        assert result["resolved"] == "delegated", result
        assert "fidelity_check" in result["delegation_evidence"], result["delegation_evidence"]
        assert "cronicas" not in result["delegation_evidence"], result["delegation_evidence"]
        print("C OWN PROJECT HANDOFF RESOLVES PASS")


def case_path_decision_not_borrowed():
    with tempfile.TemporaryDirectory(prefix="rs-pathscope-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        env = fixture_env(fixture_root)
        env["HOME"] = str(home_dir)
        write_audit(fixture_root, "rs-path", project="matrix")
        write_activity(
            fixture_root,
            '2026-01-01T00:00:01+00:00 | phase:path-decision | A | [ref-path] | subject=cronicas | motivo=x | sin-prop=si',
        )
        proc = run_hook(fixture_root, env, "rs-path")
        result = json.loads(proc.stdout)
        assert proc.returncode == 0, f"expected exit 0, got {proc.returncode}: {proc.stderr}"
        assert result["triggered"] is True, f"foreign path-decision must not exempt: {result}"
        assert result["small_path"]["declared"] is False, result["small_path"]
        print("C PATH DECISION NOT BORROWED PASS")


def case_legacy_no_project_fallback():
    with tempfile.TemporaryDirectory(prefix="rs-legacy-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        env = fixture_env(fixture_root)
        env["HOME"] = str(home_dir)
        write_audit(fixture_root, "rs-legacy")
        write_activity(
            fixture_root,
            '[2026-01-01T00:00:01+00:00] | handoff | cronicas | Trinity -> Smith con fidelity_check',
        )
        proc = run_hook(fixture_root, env, "rs-legacy")
        result = json.loads(proc.stdout)
        assert proc.returncode == 0, f"expected exit 0, got {proc.returncode}: {proc.stderr}"
        assert result["triggered"] is False, f"legacy session must fall back to in-scope: {result}"
        assert result["resolved"] == "delegated", result
        print("C LEGACY NO-PROJECT FALLBACK PASS")


def case_scope_sid_attribution_rules():
    with tempfile.TemporaryDirectory(prefix="rs-scoperules-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        env = fixture_env(fixture_root)
        env["HOME"] = str(home_dir)
        sys.path.insert(0, str(REPO_ROOT / "hooks"))
        import validate_routing_signal as r
        # explicit foreign sid never falls back to the project
        assert r._activity_in_scope(
            "handoff | matrix | Smith smoke session_id=other-session", "this-session", "matrix"
        ) is False
        # own explicit sid resolves even with parens around it
        assert r._activity_in_scope(
            "handoff | matrix | Smith smoke (session_id=this-session)", "this-session", "matrix"
        ) is True
        assert r._activity_in_scope(
            "handoff | matrix | Smith smoke session_id=this-session", "this-session", "matrix"
        ) is True
        # no sid -> project match still applies
        assert r._activity_in_scope(
            "handoff | matrix | Smith smoke", "this-session", "matrix"
        ) is True
        # path decisions: explicit foreign sid excludes; own sid includes
        assert r._path_decision_in_scope(
            "phase:path-decision | A | [ref] | subject=matrix | session_id=other-session",
            "this-session", "matrix",
        ) is False
        assert r._path_decision_in_scope(
            "phase:path-decision | A | [ref] | subject=matrix | session_id=this-session",
            "this-session", "matrix",
        ) is True
        print("C SCOPE SID ATTRIBUTION RULES PASS")


def case_foreign_sid_same_project_no_resolve():
    with tempfile.TemporaryDirectory(prefix="rs-foreignsid-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        env = fixture_env(fixture_root)
        env["HOME"] = str(home_dir)
        write_audit(fixture_root, "S1", project="matrix")
        write_activity(
            fixture_root,
            '[2026-01-01T00:00:01+00:00] | handoff | matrix | Trinity -> Smith con fidelity_check session_id=S2',
        )
        proc = run_hook(fixture_root, env, "S1")
        result = json.loads(proc.stdout)
        assert proc.returncode == 0, f"expected exit 0, got {proc.returncode}: {proc.stderr}"
        assert result["triggered"] is True, f"S2-attributed handoff must not delegate S1: {result}"
        assert result["resolved"] == "triggered", result
        print("C FOREIGN SID SAME PROJECT NO-RESOLVE PASS")


def case_own_sid_same_project_resolves():
    with tempfile.TemporaryDirectory(prefix="rs-ownsid-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        env = fixture_env(fixture_root)
        env["HOME"] = str(home_dir)
        write_audit(fixture_root, "S1", project="matrix")
        write_activity(
            fixture_root,
            '[2026-01-01T00:00:01+00:00] | handoff | matrix | Trinity -> Smith con fidelity_check (session_id=S1)',
        )
        proc = run_hook(fixture_root, env, "S1")
        result = json.loads(proc.stdout)
        assert proc.returncode == 0, f"expected exit 0, got {proc.returncode}: {proc.stderr}"
        assert result["triggered"] is False, f"own-sid handoff must resolve S1: {result}"
        assert result["resolved"] == "delegated", result
        print("C OWN SID SAME PROJECT RESOLVES PASS")


def case_path_decision_foreign_sid_not_borrowed():
    with tempfile.TemporaryDirectory(prefix="rs-pathsid-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        env = fixture_env(fixture_root)
        env["HOME"] = str(home_dir)
        write_audit(fixture_root, "S1", project="matrix")
        write_activity(
            fixture_root,
            '2026-01-01T00:00:01+00:00 | phase:path-decision | A | [ref] | subject=matrix | session_id=S2 | motivo=x | sin-prop=si',
        )
        proc = run_hook(fixture_root, env, "S1")
        result = json.loads(proc.stdout)
        assert proc.returncode == 0, f"expected exit 0, got {proc.returncode}: {proc.stderr}"
        assert result["triggered"] is True, f"foreign-sid path-decision must not exempt S1: {result}"
        assert result["small_path"]["declared"] is False, result["small_path"]
        print("C PATH DECISION FOREIGN SID NOT BORROWED PASS")


def case_resumed_session_window_reaches_last_event():
    with tempfile.TemporaryDirectory(prefix="rs-resume-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        env = fixture_env(fixture_root)
        env["HOME"] = str(home_dir)
        sid = "rs-resume"
        audit = fixture_root / "brain" / "state" / "hook-audit.jsonl"
        audit.parent.mkdir(parents=True, exist_ok=True)
        # Custom audit (not write_audit): a session resumed on day 2, with a
        # stale session_end from day 1; last event is the day-2 exec.
        entries = [
            {"event": "session_start", "session_id": sid,
             "pre_activation_check_ok": True, "timestamp": "2026-01-01T00:00:00+00:00"},
            {"event": "session_end", "session_id": sid,
             "timestamp": "2026-01-01T00:05:00+00:00"},
            {"event": "session_start", "session_id": sid,
             "pre_activation_check_ok": True, "timestamp": "2026-01-02T10:00:00+00:00"},
            {"event": "post_tool_use", "session_id": sid,
             "tool_name": "edit", "tool_paths": ["docs/a.md"],
             "timestamp": "2026-01-02T10:00:01+00:00"},
            {"event": "post_tool_use", "session_id": sid,
             "tool_name": "edit", "tool_paths": ["docs/b.md"],
             "timestamp": "2026-01-02T10:00:02+00:00"},
            {"event": "post_tool_use", "session_id": sid,
             "tool_name": "exec", "tool_paths": [],
             "timestamp": "2026-01-02T10:00:03+00:00"},
        ]
        audit.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")
        # Bare handoff (no session_id=), verified token e2e, inside day 2 and
        # within the last audit event's ts.
        write_activity(
            fixture_root,
            '[2026-01-02T10:00:02+00:00] | handoff | matrix | Trinity -> Smith gate e2e',
        )
        proc = run_hook(fixture_root, env, sid)
        result = json.loads(proc.stdout)
        assert proc.returncode == 0, f"expected exit 0, got {proc.returncode}: {proc.stderr}"
        assert result["triggered"] is False, \
            f"resumed session must find day-2 delegation evidence: {result}"
        assert result["resolved"] == "delegated", result
        assert "e2e" in result["delegation_evidence"], result["delegation_evidence"]
        print("C RESUMED SESSION WINDOW REACHES LAST EVENT PASS")


def case_same_tool_call_line_after_last_event():
    with tempfile.TemporaryDirectory(prefix="rs-sametool-") as td:
        fixture_root = Path(td)
        home_dir = smoke.build_fixture(REPO_ROOT, fixture_root)
        env = fixture_env(fixture_root)
        env["HOME"] = str(home_dir)
        sid = "rs-sametool"
        audit = fixture_root / "brain" / "state" / "hook-audit.jsonl"
        audit.parent.mkdir(parents=True, exist_ok=True)
        # The last audit event is at 00:00:03 (exec); a bare handoff written in
        # the same tool call as the close is timestamped 00:00:05 (in the past).
        # With D the window reaches max(last_dt, now) so that line is in scope.
        entries = [
            {"event": "session_start", "session_id": sid,
             "pre_activation_check_ok": True, "timestamp": "2026-01-01T00:00:00+00:00"},
            {"event": "post_tool_use", "session_id": sid,
             "tool_name": "edit", "tool_paths": ["docs/a.md"],
             "timestamp": "2026-01-01T00:00:01+00:00"},
            {"event": "post_tool_use", "session_id": sid,
             "tool_name": "edit", "tool_paths": ["docs/b.md"],
             "timestamp": "2026-01-01T00:00:02+00:00"},
            {"event": "post_tool_use", "session_id": sid,
             "tool_name": "exec", "tool_paths": [],
             "timestamp": "2026-01-01T00:00:03+00:00"},
        ]
        audit.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")
        write_activity(
            fixture_root,
            '[2026-01-01T00:00:05+00:00] | handoff | matrix | Trinity -> Smith gate e2e',
        )
        proc = run_hook(fixture_root, env, sid)
        result = json.loads(proc.stdout)
        assert proc.returncode == 0, f"expected exit 0, got {proc.returncode}: {proc.stderr}"
        assert result["triggered"] is False, \
            f"handoff after last_dt (same tool call) must be in scope: {result}"
        assert result["resolved"] == "delegated", result
        assert "e2e" in result["delegation_evidence"], result["delegation_evidence"]
        print("C SAME-TOOL-CALL LINE AFTER LAST EVENT PASS")


def main():
    assert REPO_ROOT != Path("/tmp").resolve(), "repo root must not be /tmp"
    case_delegated_with_check()
    case_delegated_without_check()
    case_no_delegation()
    case_prefers_verified_route()
    case_history_transitions()
    case_count_consecutive_unresolved_sessions()
    case_foreign_project_handoff_does_not_resolve()
    case_own_project_handoff_resolves()
    case_path_decision_not_borrowed()
    case_legacy_no_project_fallback()
    case_scope_sid_attribution_rules()
    case_foreign_sid_same_project_no_resolve()
    case_own_sid_same_project_resolves()
    case_path_decision_foreign_sid_not_borrowed()
    case_resumed_session_window_reaches_last_event()
    case_same_tool_call_line_after_last_event()
    print("C DELEGATION ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
