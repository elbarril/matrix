#!/usr/bin/env python3
"""The Trainman — permissions.deny hardener.

Reconciles the host CLI's permissions.deny list against a declarative
secret-deny configuration (adapters/<target>/config.yaml). For Devin, this
writes ~/.config/devin/config.json and a sidecar managed-deny file. It never
touches permissions.allow and never overwrites the whole permissions object.
"""
import datetime
import json
import os
import shutil
import subprocess
import sys

ROOT = os.environ.get("MATRIX_ROOT") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

COVERAGE_NOTE = (
    "Nota de cobertura: este control bloquea el tool `read` sobre las rutas listadas.\n"
    "NO bloquea `grep`/`glob` (pueden devolver contenido de esas rutas igual) ni `exec`\n"
    "(ej. `cat`). Es una mitigación parcial contra lectura incidental, no un sandbox."
)


def _say(msg):
    print(f"[trainman:harden] {msg}")


def _default_config_path(target):
    if target == "devin":
        return os.path.join(os.path.expanduser("~"), ".config", "devin", "config.json")
    return os.path.join(os.path.expanduser("~"), ".config", target, "config.json")


def _sidecar_path(config_path):
    return os.path.join(os.path.dirname(config_path), ".matrix-managed-deny.json")


def _now():
    return datetime.datetime.now().astimezone().isoformat()


def _load_yaml(path):
    try:
        import yaml
        with open(path, encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
    except Exception as exc:
        print(f"[trainman:harden] error reading {path}: {exc}", file=sys.stderr)
        return {}


def _load_json(path, default=None):
    if not os.path.isfile(path):
        return default if default is not None else {}
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read().strip()
            return json.loads(text) if text else {}
    except Exception as exc:
        print(f"[trainman:harden] warning: could not read {path}: {exc}", file=sys.stderr)
        return {}


def _to_deny_pattern(p):
    """Normalize a config entry into a Read(...) deny pattern."""
    if not isinstance(p, str) or not p:
        return None
    p = p.strip()
    if p.startswith("Read(") and p.endswith(")"):
        return p
    return f"Read({p})"


def _scan_root(root_path, root_name, max_depth):
    """Walk one top-level hidden dir under $HOME up to max_depth.

    Returns a set of Read(...) patterns for:
      - a direct child named 'credentials' (Read(~/.<name>/credentials/**))
      - any .env file under the root (Read(~/.<name>/**/*.env))

    Symlinks are never followed. No specific credential file/directory names
    other than the generic 'credentials' and '.env' are emitted.
    """
    patterns = set()
    root_prefix = f"~/{root_name}"
    env_seen = False

    def scan(path, depth):
        nonlocal env_seen
        if depth >= max_depth:
            return
        try:
            entries = list(os.scandir(path))
        except OSError:
            return
        for entry in entries:
            if entry.is_symlink():
                continue
            if depth < max_depth and entry.is_dir(follow_symlinks=False):
                # Direct child 'credentials' under the hidden root.
                if depth == 1 and entry.name == "credentials":
                    patterns.add(f"Read({root_prefix}/credentials/**)")
                scan(entry.path, depth + 1)
            elif entry.is_file(follow_symlinks=False) and entry.name.endswith(".env"):
                env_seen = True

    scan(root_path, 1)
    if env_seen:
        patterns.add(f"Read({root_prefix}/**/*.env)")
    return patterns


def _discover(home, max_depth):
    patterns = set()
    try:
        entries = list(os.scandir(home))
    except OSError as exc:
        _say(f"could not scan $HOME: {exc}")
        return patterns
    for entry in entries:
        if entry.is_symlink():
            continue
        if not (entry.is_dir(follow_symlinks=False) and entry.name.startswith(".")):
            continue
        patterns.update(_scan_root(entry.path, entry.name, max_depth))
    return patterns


def _desired_patterns(secret_deny, home):
    desired = set()

    # Static list from config.
    for p in secret_deny.get("static", []):
        pat = _to_deny_pattern(p)
        if pat:
            desired.add(pat)

    # Optional repo-scoped secret globs (disabled by default).
    repo = secret_deny.get("class_b_repo_secrets", {})
    if repo and repo.get("enabled"):
        for p in repo.get("patterns", []):
            pat = _to_deny_pattern(p)
            if pat:
                desired.add(pat)

    # Auto-discovery within $HOME, bounded by max_depth.
    discover = secret_deny.get("discover", {})
    if discover.get("enabled", True):
        max_depth = discover.get("max_depth", 3)
        if not isinstance(max_depth, int) or max_depth < 1:
            max_depth = 3
        desired.update(_discover(home, max_depth))

    return desired


def _normalize_excludes(secret_deny):
    excludes = set()
    for e in secret_deny.get("exclude", []):
        pat = _to_deny_pattern(e)
        if pat:
            excludes.add(pat)
    return excludes


def _reconcile(deny_actual, sidecar_managed, sidecar_auto_exclude, desired_config, excludes):
    desired_effective = desired_config - excludes - sidecar_auto_exclude
    revertido = (sidecar_managed & desired_effective) - deny_actual
    new_auto_exclude = sidecar_auto_exclude | revertido
    desired_final = desired_effective - revertido
    deny_final = (deny_actual - sidecar_managed) | desired_final
    return deny_final, desired_final, new_auto_exclude, revertido


def _atomic_write_json(path, data):
    tmp = f"{path}.tmp.{os.getpid()}"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    # Validate with the same json.tool check used by install-hooks.sh.
    try:
        subprocess.run(
            [sys.executable, "-m", "json.tool", tmp],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as exc:
        os.remove(tmp)
        raise RuntimeError(f"JSON validation failed for {path}: {exc}") from exc
    os.replace(tmp, path)


def _backup_file(path):
    if not os.path.isfile(path):
        return
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = f"{path}.bak-{stamp}"
    shutil.copy2(path, backup)
    _say(f"backup created: {backup}")


def _print_diff(old, new):
    added = sorted(new - old)
    removed = sorted(old - new)
    if not added and not removed:
        print("  (sin cambios)")
    for p in added:
        print(f"  + {p}")
    for p in removed:
        print(f"  - {p}")


def main():
    target = ""
    apply = False
    revert = False
    reset_auto_exclude = False
    config_path = os.environ.get("DEVIN_CONFIG") or ""

    i = 1
    while i < len(sys.argv):
        a = sys.argv[i]
        if a.startswith("--target="):
            target = a.split("=", 1)[1]
        elif a == "--target":
            i += 1
            target = sys.argv[i]
        elif a == "--apply":
            apply = True
        elif a == "--revert":
            revert = True
        elif a == "--reset-auto-exclude":
            reset_auto_exclude = True
        elif a == "--config":
            i += 1
            config_path = sys.argv[i]
        elif a.startswith("--config="):
            config_path = a.split("=", 1)[1]
        else:
            print(f"[trainman:harden] unknown argument: {a}", file=sys.stderr)
            sys.exit(1)
        i += 1

    if not target:
        print("[trainman:harden] Usage: _harden.py --target=<cli> [--apply] [--revert] [--config PATH]", file=sys.stderr)
        sys.exit(1)

    if not config_path:
        config_path = _default_config_path(target)

    # Resolve and load adapter config.
    adapter_config = _load_yaml(os.path.join(ROOT, "adapters", target, "config.yaml"))
    secret_deny = adapter_config.get("secret_deny", {})

    home = os.path.expanduser("~")
    desired_config = _desired_patterns(secret_deny, home)
    excludes = _normalize_excludes(secret_deny)

    # Load real Devin config and sidecar.
    cfg = _load_json(config_path, default={})
    permissions = cfg.get("permissions", {})
    if not isinstance(permissions, dict):
        permissions = {}
        cfg["permissions"] = permissions
    deny_actual = set(permissions.get("deny", []))

    sidecar_path = _sidecar_path(config_path)
    sidecar = _load_json(sidecar_path)
    if not isinstance(sidecar, dict):
        sidecar = {}
    sidecar_managed = set(_to_deny_pattern(p) for p in sidecar.get("managed", []) if _to_deny_pattern(p))
    sidecar_auto_exclude = set(_to_deny_pattern(p) for p in sidecar.get("auto_exclude", []) if _to_deny_pattern(p))

    if reset_auto_exclude:
        sidecar_auto_exclude = set()

    if revert:
        new_deny = deny_actual - sidecar_managed
        new_managed = set()
        new_auto_exclude = sidecar_auto_exclude
        revertido = set()
        new_desired_final = set()
        mode_label = "revert"
    else:
        new_deny, new_desired_final, new_auto_exclude, revertido = _reconcile(
            deny_actual, sidecar_managed, sidecar_auto_exclude, desired_config, excludes
        )
        new_managed = new_desired_final
        mode_label = "apply" if apply else "dry-run"

    print(COVERAGE_NOTE)
    print()
    print(f"[trainman:harden] mode: {mode_label}")
    print(f"[trainman:harden] config: {config_path}")
    print(f"[trainman:harden] sidecar: {sidecar_path}")
    print("[trainman:harden] diff (permissions.deny):")
    _print_diff(deny_actual, new_deny)

    if revertido:
        print()
        print("[trainman:harden] entradas revertidas manualmente (se agregan a auto_exclude):")
        for p in sorted(revertido):
            print(f"  - {p}")

    if not apply and not revert:
        print("\n[trainman:harden] dry-run: no se escribió nada. Usa --apply para aplicar.")
        sys.exit(0)

    # Apply changes.
    _backup_file(config_path)

    permissions["deny"] = sorted(new_deny)
    cfg.setdefault("permissions", permissions)
    _atomic_write_json(config_path, cfg)
    _say(f"updated {config_path}")

    # Write sidecar only after the real config write succeeded and validated.
    new_sidecar = {
        "schema_version": 1,
        "managed": sorted(new_managed),
        "auto_exclude": sorted(new_auto_exclude),
        "updated_at": _now(),
    }
    _atomic_write_json(sidecar_path, new_sidecar)
    _say(f"updated {sidecar_path}")

    if revert:
        _say("revert completed")
    else:
        _say("harden completed")


if __name__ == "__main__":
    main()
