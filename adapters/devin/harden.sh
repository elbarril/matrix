#!/usr/bin/env bash
# Trainman · Devin permissions.deny hardener.
#
# Reconciles ~/.config/devin/config.json permissions.deny against the
# declarative secret_deny block in adapters/devin/config.yaml. Dry-run by
# default; use --apply to write, --revert to remove Matrix-managed entries.
set -euo pipefail

ROOT="${MATRIX_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"

MATRIX_ROOT="$ROOT" python3 "$ROOT/adapters/_harden.py" --target=devin "$@"
