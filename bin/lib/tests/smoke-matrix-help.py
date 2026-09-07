#!/usr/bin/env python3
"""Matrix CLI E2E smoke test — captures a normalized golden baseline."""
import argparse, difflib, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def repo_root_from_script():
    # bin/lib/tests/<script>  -> parents[3] is repo root
    return Path(__file__).resolve().parents[3]


def build_fixture(repo_root, fixture_root):
    fixture_root.mkdir(parents=True, exist_ok=True)
    (fixture_root / "bin").mkdir(exist_ok=True)
    shutil.copy2(repo_root / "bin" / "matrix", fixture_root / "bin" / "matrix")
    (fixture_root / "bin" / "matrix").chmod(0o755)
    lib_src = repo_root / "bin" / "lib"
    if lib_src.exists():
        shutil.copytree(lib_src, fixture_root / "bin" / "lib", dirs_exist_ok=True)
    shutil.copytree(repo_root / "adapters", fixture_root / "adapters", dirs_exist_ok=True)
    # remove stale generated dir so build produces fresh fixture-scoped artifacts
    stale_gen = fixture_root / "adapters" / "devin" / "generated"
    if stale_gen.exists():
        shutil.rmtree(stale_gen)
    shutil.copytree(repo_root / "hooks", fixture_root / "hooks", dirs_exist_ok=True)
    (fixture_root / "brain").mkdir(exist_ok=True)
    shutil.copytree(repo_root / "brain" / "agents", fixture_root / "brain" / "agents", dirs_exist_ok=True)
    shutil.copytree(repo_root / "brain" / "data", fixture_root / "brain" / "data", dirs_exist_ok=True)
    shutil.copytree(repo_root / "brain" / "subsystems", fixture_root / "brain" / "subsystems", dirs_exist_ok=True)
    shutil.copy2(repo_root / "brain" / "config.yaml", fixture_root / "brain" / "config.yaml")
    (fixture_root / "brain" / "state").mkdir(exist_ok=True)
    (fixture_root / "brain" / "output" / "plans").mkdir(parents=True, exist_ok=True)
    (fixture_root / "brain" / "output" / "plans" / "smoke.md").write_text(
        "## 3.2 Smoke develop\n\n**Dueño:** Trinity\n\nFase: develop\n"
    )
    for name in ["AGENTS.md", "onboarding.html", "DEVIN.md", "README.md"]:
        src = repo_root / name
        if src.exists():
            shutil.copy2(src, fixture_root / name)
    docs = repo_root / "docs"
    if docs.exists():
        (fixture_root / "docs").mkdir(exist_ok=True)
        if (docs / "SYSTEM_TRUTH.md").exists():
            shutil.copy2(docs / "SYSTEM_TRUTH.md", fixture_root / "docs" / "SYSTEM_TRUTH.md")
    (fixture_root / ".registry.json").write_text('{"projects":[],"created":"2024-01-01T00:00:00+00:00","version":"2.0.0"}')
    home_dir = fixture_root / "home"
    (home_dir / ".config").mkdir(parents=True, exist_ok=True)
    for pname in ["alpha", "beta"]:
        pdir = fixture_root / "projects" / pname
        pdir.mkdir(parents=True, exist_ok=True)
        (pdir / "README.md").write_text(f"# {pname}\n")
        subprocess.run(["git", "init"], cwd=pdir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=pdir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=pdir, check=True, capture_output=True)
        subprocess.run(["git", "add", "."], cwd=pdir, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=pdir, check=True, capture_output=True)
    fake = fixture_root / "bin" / "fake-devin"
    fake.write_text('#!/bin/bash\nif [[ "$1" == "list" && "$2" == "--format" && "$3" == "json" ]]; then echo "[]"; exit 0; fi\necho "Hardline completed"\nexit 0\n')
    fake.chmod(0o755)
    (fixture_root / "brain" / "state" / ".current-hook-session").write_text("test-session-001")
    return home_dir


def collect_dir(snapshot, root_dir, prefix, fixture_root):
    if not root_dir.is_dir():
        return
    for dirpath, dirnames, filenames in os.walk(root_dir):
        dirnames[:] = [d for d in dirnames if not d.endswith(".lock")]
        for fn in filenames:
            if fn.endswith(".lock"):
                continue
            abs_path = Path(dirpath) / fn
            rel = abs_path.relative_to(root_dir)
            key = f"{prefix}/{rel}"
            if abs_path.is_symlink():
                target = os.readlink(abs_path)
                snapshot[key] = [f"-> {target}"]
            elif abs_path.is_file():
                try:
                    snapshot[key] = abs_path.read_text(encoding="utf-8", errors="replace").splitlines()
                except Exception:
                    snapshot[key] = ["<binary file skipped>"]


def state_snapshot(fixture_root, home_dir, projects):
    snapshot = {}
    files = [
        ".registry.json",
        "workspace.yaml",
        "brain/state/activity.log",
        "brain/state/checkpoints.jsonl",
        "brain/state/hardline/queue.jsonl",
        "brain/state/validation-report.json",
        "brain/state/.current-hook-session",
        "docs/SYSTEM_TRUTH.md",
        "onboarding.html",
        "DEVIN.md",
        ".devin/config.json",
    ]
    for rel in files:
        path = fixture_root / rel
        if path.is_file():
            try:
                snapshot[f"FIXTURE_ROOT/{rel}"] = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except Exception:
                snapshot[f"FIXTURE_ROOT/{rel}"] = ["<binary file skipped>"]
    sessions_dir = fixture_root / "brain" / "state" / "sessions"
    if sessions_dir.is_dir():
        for f in sorted(sessions_dir.iterdir()):
            key = f"FIXTURE_ROOT/brain/state/sessions/{f.name}"
            if f.is_file():
                snapshot[key] = f.read_text(encoding="utf-8", errors="replace").splitlines()
    collect_dir(snapshot, fixture_root / "brain" / "state" / "hardline" / "events", "FIXTURE_ROOT/brain/state/hardline/events", fixture_root)
    collect_dir(snapshot, fixture_root / "adapters" / "devin" / "generated", "FIXTURE_ROOT/adapters/devin/generated", fixture_root)
    collect_dir(snapshot, home_dir / ".config" / "devin", "FIXTURE_HOME/.config/devin", fixture_root)
    for proj in projects:
        for rel in [f"projects/{proj}/AGENTS.local.md", f"projects/{proj}/.git/info/exclude"]:
            path = fixture_root / rel
            if path.is_file():
                snapshot[f"FIXTURE_ROOT/{rel}"] = path.read_text(encoding="utf-8", errors="replace").splitlines()
        link = fixture_root / "projects" / proj / "_brain"
        if link.is_symlink():
            snapshot[f"FIXTURE_ROOT/projects/{proj}/_brain"] = [f"-> {os.readlink(link)}"]
    return snapshot


def state_diff(before, after):
    lines = []
    for key in sorted(set(before) | set(after)):
        a = before.get(key, [])
        b = after.get(key, [])
        if a == b:
            continue
        diff = list(difflib.unified_diff(a, b, fromfile=key, tofile=key, fromfiledate="", tofiledate="", lineterm=""))
        lines.extend(diff)
        lines.append("")
    return "\n".join(lines)


def normalize_text(text, fixture_root, home_dir):
    text = re.sub(r"\x1B\[[0-9;]*m", "", text)
    text = re.sub(re.escape(str(home_dir)), "FIXTURE_HOME", text)
    text = re.sub(re.escape(str(fixture_root)), "FIXTURE_ROOT", text)
    text = re.sub(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[+-]\d{2}:\d{2}|Z)", "TIMESTAMP", text)
    text = re.sub(r"\[hardline\] \d+\.\d+", "[hardline] TIMESTAMP", text)
    text = re.sub(r"\bhardline-[a-z0-9]+-\d+-\d+\b", "hardline-EVENT_ID", text)
    text = re.sub(r"\b[a-f0-9]{64}\b", "SHA256", text)
    text = re.sub(r"\btest-event-[a-z0-9]+\b", "test-event-REF", text)
    text = re.sub(r"\.bak-\d{8}-\d{6}", ".bak-DATETIME", text)
    return text


def run_cmd(matrix_bin, cmd, cwd, env, stdin=None, timeout=120):
    return subprocess.run(
        ["bash", "-c", 'export RANDOM=12345; exec "$@"', "--", str(matrix_bin)] + cmd,
        cwd=str(cwd), env=env, input=stdin, capture_output=True, text=True, timeout=timeout,
    )


def run_smoke(repo_root, matrix_rel="bin/matrix"):
    with tempfile.TemporaryDirectory(prefix="matrix-smoke-") as td:
        fixture_root = Path(td)
        home_dir = build_fixture(repo_root, fixture_root)
        matrix_bin = fixture_root / "bin" / "matrix"
        env = os.environ.copy()
        env["HOME"] = str(home_dir)
        env["XDG_CONFIG_HOME"] = str(home_dir / ".config")
        env["SOURCE_DATE_EPOCH"] = "1704067200"
        env["TZ"] = "UTC"
        env["DEVIN_BIN"] = str(fixture_root / "bin" / "fake-devin")
        env["PATH"] = f"{fixture_root / 'bin'}:{env.get('PATH', '')}"
        projects = ["alpha", "beta"]
        commands = [
            ("help", ["help"], fixture_root, None),
            ("list", ["list"], fixture_root, None),
            ("add alpha", ["add", "alpha", str(fixture_root / "projects" / "alpha")], fixture_root, None),
            ("add beta", ["add", "beta", str(fixture_root / "projects" / "beta")], fixture_root, None),
            ("list after add", ["list"], fixture_root, None),
            ("work alpha", ["work", "alpha"], fixture_root, None),
            ("work beta", ["work", "beta"], fixture_root, None),
            ("status", ["status"], fixture_root, None),
            ("status --all", ["status", "--all"], fixture_root, None),
            ("bindings", ["bindings"], fixture_root, None),
            ("scope workspace", ["scope"], fixture_root, None),
            ("select alpha", ["select", "alpha"], fixture_root, None),
            ("status after select", ["status"], fixture_root, None),
            ("bindings after select", ["bindings"], fixture_root, None),
            ("scope bound", ["scope"], fixture_root / "projects" / "alpha", None),
            ("focus beta", ["focus", "beta"], fixture_root, None),
            ("status after focus", ["status"], fixture_root, None),
            ("adapter-doc-path", ["adapter-doc-path"], fixture_root, None),
            ("hardline dispatch", ["hardline", "dispatch", "matrix", "test event"], fixture_root, None),
            ("hardline status", ["hardline", "status"], fixture_root, None),
            ("hardline queue", ["hardline", "queue"], fixture_root, None),
            ("hardline reject", ["hardline", "reject", "matrix", "bad line", "bad"], fixture_root, None),
            ("hardline resume", ["hardline", "resume", "EVENT_ID_PLACEHOLDER"], fixture_root, None),
            ("hardline status after reject", ["hardline", "status"], fixture_root, None),
            ("hardline queue after reject", ["hardline", "queue"], fixture_root, None),
            ("checkpoint", ["checkpoint", "smoke checkpoint"], fixture_root, None),
            ("activity 5", ["activity", "5"], fixture_root, None),
            ("activity --all 3", ["activity", "--all", "3"], fixture_root, None),
            ("link", ["link", "test:event", "fixture-subject", "--ref=ref123", "detail1", "detail2"], fixture_root, None),
            ("link route bare", ["link", "route", "primary-retirement", "--ref=refroute123", "Oracle? no - plan+execute: Morpheus -> Architect -> Trinity -> Smith"], fixture_root, None),
            ("ship list", ["ship", "list"], fixture_root, None),
            ("corpus-ingest", ["corpus-ingest", "--topic=test", "--slug=demo"], fixture_root, "corpus content line 1\n"),
            ("build", ["build", "--target=devin"], fixture_root, None),
            ("install", ["install", "--target=devin"], fixture_root, None),
            ("harden", ["harden", "--target=devin"], fixture_root, None),
            ("exclude audit", ["exclude", "audit", "beta"], fixture_root, None),
            ("exclude fix", ["exclude", "fix", "beta", "--fix"], fixture_root, None),
            ("phase precheck pass", ["phase", "precheck", '{"phase":"develop","e2e":true,"evidence":"smoke-test-evidence","plan":"brain/output/plans/smoke.md","step":"3.2"}'], fixture_root, None),
            ("phase precheck block", ["phase", "precheck", '{"phase":"unknown","e2e":true,"evidence":"smoke-test-evidence"}'], fixture_root, None),
            ("phase precheck warn", ["phase", "precheck", '{"phase":"develop","e2e":true,"evidence":"brain/output/eval/missing-smoke.md","plan":"brain/output/plans/smoke.md","step":"3.2"}'], fixture_root, None),
            ("phase close", ["phase", "close", '{"phase":"spec","evidence":"smoke-test-evidence"}'], fixture_root, None),
            ("session close", ["session", "close", '{"session_id":"test-session-001"}'], fixture_root, None),
            ("hooks the_source", ["hooks", "the_source"], fixture_root, None),
            ("hooks validate_layer2", ["hooks", "validate_layer2"], fixture_root, None),
            ("session-find", ["session-find", "projects"], fixture_root, None),
            ("session-dump", ["session-dump", "test-session-001"], fixture_root, None),
            ("session-cost", ["session-cost", "projects"], fixture_root, None),
            ("session-subagents", ["session-subagents", "test-session-001"], fixture_root, None),
            ("session-report", ["session-report", "projects"], fixture_root, None),
            ("deselect alpha", ["deselect", "alpha"], fixture_root, None),
            ("unwork alpha", ["unwork", "alpha"], fixture_root, None),
            ("unwork --all --dry-run", ["unwork", "--all", "--dry-run"], fixture_root, None),
            ("unwork --all", ["unwork", "--all"], fixture_root, None),
            ("remove alpha", ["remove", "alpha"], fixture_root, None),
            ("list final", ["list"], fixture_root, None),
            ("help final", ["help"], fixture_root, None),
        ]
        transcript = []
        event_id = None
        for desc, cmd, cwd, stdin in commands:
            # inject captured hardline event id into resume command
            if cmd[0:2] == ["hardline", "resume"] and event_id:
                cmd = ["hardline", "resume", event_id]
            before = state_snapshot(fixture_root, home_dir, projects)
            proc = run_cmd(matrix_bin, cmd, cwd, env, stdin)
            after = state_snapshot(fixture_root, home_dir, projects)
            diff = state_diff(before, after)
            if desc.startswith("phase precheck"):
                ledger_key = "FIXTURE_ROOT/brain/state/activity.log"
                before_closes = sum("phase:close" in line for line in before.get(ledger_key, []))
                after_closes = sum("phase:close" in line for line in after.get(ledger_key, []))
                if before_closes != after_closes:
                    raise AssertionError(f"{desc} persisted a phase:close ledger entry")
                expected = {"phase precheck pass": (0, '"verdict": "PASS"'),
                            "phase precheck block": (1, '"verdict": "BLOCK"'),
                            "phase precheck warn": (0, '"verdict": "WARN"')}[desc]
                if proc.returncode != expected[0] or expected[1] not in proc.stdout:
                    raise AssertionError(
                        f"{desc}: expected rc={expected[0]} and {expected[1]}, "
                        f"got rc={proc.returncode}, stdout={proc.stdout!r}"
                    )
            if desc == "hardline dispatch":
                m = re.search(r"event=(hardline-[a-z0-9]+-\d+-\d+)", proc.stdout)
                if m:
                    event_id = m.group(1)
            out_norm = normalize_text(proc.stdout, fixture_root, home_dir)
            err_norm = normalize_text(proc.stderr, fixture_root, home_dir)
            diff_norm = normalize_text(diff, fixture_root, home_dir)
            transcript.append(f"### {desc}")
            transcript.append(f"exit: {proc.returncode}")
            transcript.append("--- stdout ---")
            transcript.append(out_norm)
            transcript.append("--- stderr ---")
            transcript.append(err_norm)
            transcript.append("--- state diff ---")
            transcript.append(diff_norm)
            transcript.append("")
        return "\n".join(transcript)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, help="write baseline to this path")
    parser.add_argument("--compare", type=Path, help="compare run against baseline and exit non-zero if different")
    args = parser.parse_args()
    repo_root = repo_root_from_script()
    if args.baseline:
        out = run_smoke(repo_root)
        args.baseline.parent.mkdir(parents=True, exist_ok=True)
        args.baseline.write_text(out, encoding="utf-8")
        print(f"Baseline written: {args.baseline}")
        return 0
    if args.compare:
        baseline = args.compare.read_text(encoding="utf-8")
        current = run_smoke(repo_root)
        if baseline == current:
            print("SMOKE PASS: current output matches baseline")
            return 0
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False, encoding="utf-8") as f:
            f.write(current)
            current_path = f.name
        eprint(f"SMOKE FAIL: current output saved to {current_path}")
        diff = list(difflib.unified_diff(baseline.splitlines(), current.splitlines(), fromfile="baseline", tofile="current", lineterm=""))
        for line in diff[:200]:
            eprint(line)
        return 1
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
