#!/bin/bash
# Trainman · Devin builder. Renders agnostic agents into native artifacts.
set -euo pipefail
ROOT="${MATRIX_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
TEMPLATE_ARG=""
for arg in "$@"; do
    case "$arg" in
        --template=*) TEMPLATE_ARG="$arg" ;;
    esac
done
if [[ -n "$TEMPLATE_ARG" ]]; then
    MATRIX_ROOT="$ROOT" python3 "$ROOT/adapters/_build.py" --target=devin "$TEMPLATE_ARG"
else
    MATRIX_ROOT="$ROOT" python3 "$ROOT/adapters/_build.py" --target=devin
fi
