#!/usr/bin/env python3
"""Seraph · prune_session_artifacts — explicit pruning surface for brain/state/sessions/.

The hot path already prunes automatically via _common.prune_session_artifacts
at session_start / sid resolution. This hook is the pre-flight and manual
maintenance surface OUTSIDE that path: by default it lists what the TTL pruning
would remove (dry-run) without deleting anything; {"apply": true} performs the
prune and logs every removed path to the Link ledger.

TTL per type and the "alive" rule live in _common (the single owner); see
SESSION_ARTIFACT_TTL_DAYS and prune_session_artifacts.

Usage:
  bin/matrix hooks prune_session_artifacts                      # dry-run (default)
  bin/matrix hooks prune_session_artifacts '{"apply":true}'     # perform the prune
  bin/matrix hooks prune_session_artifacts '{"apply":true,"root":"/tmp/fx"}'  # fixture root
"""

from _common import emit, prune_session_artifacts, read_input, resolve_root


def main():
    data = read_input()
    root = data.get("root") or resolve_root()
    apply_mode = bool(data.get("apply"))
    removed = prune_session_artifacts(
        root,
        current_sid=data.get("current_sid") or None,
        dry_run=not apply_mode,
    )
    result = {
        "hook": "prune_session_artifacts",
        "ok": True,
        "root": root,
        "mode": "apply" if apply_mode else "dry-run",
        "count": len(removed),
        "removed": [
            {"path": r["path"], "kind": r["kind"], "sid": r["sid"], "age_days": r["age_days"]}
            for r in removed
        ],
        "note": (
            "apply: removed the listed artifacts and logged each path to the Link ledger"
            if apply_mode
            else "dry-run: nothing was deleted; the hot path still prunes at session_start / sid resolution"
        ),
    }
    emit(result)


if __name__ == "__main__":
    main()
