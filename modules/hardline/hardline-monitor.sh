#!/bin/bash
# The Hardline — persistent event monitor. Blocks on tail -F (zero tokens idle),
# wakes on each external event, validates it, logs it to the Link ledger, and
# prints the dispatch the host CLI should run. One poller, no busy-loop.
set -uo pipefail

ROOT="${MATRIX_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
MODULE_DIR="$ROOT/modules/hardline"
INBOX="$MODULE_DIR/inbox.log"
MATRIX="$ROOT/bin/matrix"

mkdir -p "$MODULE_DIR"
[[ -f "$INBOX" ]] || : > "$INBOX"

echo "[hardline] monitoring $INBOX (Ctrl-C to stop). Zero tokens while idle."

# Follow new lines only; block until they arrive.
tail -n0 -F "$INBOX" | while IFS= read -r line; do
    line="$(echo "$line" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
    [[ -z "$line" ]] && continue
    # Minimal validation: reject lines that look like they carry secrets.
    if echo "$line" | grep -qiE 'token|password|secret|api[_-]?key'; then
        echo "[hardline] SKIP (possible secret in event): redacted"
        "$MATRIX" activity >/dev/null 2>&1 || true
        continue
    fi
    echo "[hardline] event → dispatch: $line"
    # Record to the Link ledger via the CLI (never hand-edit state).
    "$MATRIX" checkpoint "hardline event: $line" >/dev/null 2>&1 || true
    # The host CLI/agent layer is responsible for actually invoking Neo with:
    #   $line   (guarded by Commander Lock in unattended mode)
done
