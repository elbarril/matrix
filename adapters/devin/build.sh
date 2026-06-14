#!/bin/bash
# Trainman · Devin builder. Renders agnostic agents into native artifacts.
set -euo pipefail
ROOT="${MATRIX_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
MATRIX_ROOT="$ROOT" python3 "$ROOT/adapters/_build.py" --target=devin
