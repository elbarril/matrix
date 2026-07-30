#!/bin/bash
# The Hardline — persistent event monitor. Blocks on tail -F (zero tokens idle),
# wakes on each external event, validates it, logs it to the Link ledger, and
# dispatches to the bound project via bin/matrix hardline dispatch. One poller,
# no busy-loop. Synchronous per-event processing: never cancels an in-flight
# event (D7.c).
set -uo pipefail

ROOT="${MATRIX_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
MODULE_DIR="$ROOT/modules/hardline"
INBOX="$MODULE_DIR/inbox.log"
MATRIX="$ROOT/bin/matrix"

mkdir -p "$MODULE_DIR"
[[ -f "$INBOX" ]] || : > "$INBOX"

echo "[hardline] monitoring $INBOX (Ctrl-C to stop). Zero tokens while idle."

# Inbox line format: <project>|<line>
#   <project>  registered, bound project name (letters, numbers, dot, underscore, hyphen)
#   <line>     the unattended prompt/task; must not contain a newline
# Example: mck|Update the README with a one-line note about hardline events.

# Follow new lines only; block until they arrive.
tail -n0 -F "$INBOX" | while IFS= read -r line; do
    line="$(echo "$line" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
    [[ -z "$line" ]] && continue
    event_id="hardline-monitor-$(date +%s)-$$-$RANDOM"

    # Parse project|line. Project names are constrained to [A-Za-z0-9._-]+.
    # No project is addressable yet at this point, so there is no dedupe_key a
    # bridge could match — this rejection stays Link-only (see design §6.a).
    if [[ "$line" != *"|"* ]]; then
        echo "[hardline] REJECT malformed (missing '|' delimiter): $line"
        "$MATRIX" link hardline:rejected hardline --ref="$event_id" \
            "event_id=$event_id reason=missing-delimiter" >/dev/null || true
        continue
    fi

    project="${line%%|*}"
    raw_line="${line#*|}"

    if [[ -z "$project" || -z "$raw_line" ]]; then
        echo "[hardline] REJECT malformed (empty project or line): $line"
        "$MATRIX" link hardline:rejected hardline --ref="$event_id" \
            "event_id=$event_id reason=empty-field" >/dev/null || true
        "$MATRIX" hardline reject "$project" "$raw_line" \
            "el proyecto o la tarea llegaron vacíos tras separar por '|'; evento descartado sin ejecutar" >/dev/null || true
        continue
    fi

    if [[ ! "$project" =~ ^[A-Za-z0-9._-]+$ ]]; then
        echo "[hardline] REJECT malformed (invalid project '$project'): $line"
        "$MATRIX" link hardline:rejected hardline --ref="$event_id" \
            "event_id=$event_id reason=invalid-project project=$project" >/dev/null || true
        "$MATRIX" hardline reject "$project" "$raw_line" \
            "el proyecto '$project' no cumple el formato permitido (letras, números, punto, guion, guion bajo); evento descartado sin ejecutar" >/dev/null || true
        continue
    fi

    # Minimal validation: reject lines that look like they carry secrets. Only
    # checked on raw_line (the task text) — project's charset above already
    # rules out anything secret-shaped there. Project is known now, so this
    # rejection can also reach the queue for the bridge to notify on.
    if echo "$raw_line" | grep -qiE '\b(token|password|secret|api[_-]?key)([[:space:]]+[[:alnum:]_.-]+){0,2}[[:space:]]*[:=][[:space:]]*[^[:space:]]+'; then
        echo "[hardline] SKIP (possible secret in event): redacted"
        "$MATRIX" link hardline:skip-secret hardline --ref="$event_id" \
            "event_id=$event_id marker=[REDACTED]" >/dev/null || true
        "$MATRIX" hardline reject "$project" "$raw_line" \
            "contenido con forma de secreto detectado antes de despachar; evento descartado sin ejecutar" >/dev/null || true
        continue
    fi

    echo "[hardline] event → dispatch: project=$project line=$raw_line"
    # Record to the Link ledger via the CLI (never hand-edit state).
    "$MATRIX" link hardline:event "$project" --ref="$event_id" \
        "event_id=$event_id project=$project line=$raw_line" >/dev/null || true

    # Dispatch synchronously. D7.c: the monitor never cancels an in-flight event.
    # Different-project concurrency is intentionally serialized in this MVP
    # monitor; the Layer 1 queue + per-project lock still preserve ordering and
    # safety when multiple consumers are added later.
    if "$MATRIX" hardline dispatch "$project" "$raw_line"; then
        : # dispatched and acked by Layer 1
    else
        echo "[hardline] dispatch failed for project=$project line=$raw_line" >&2
    fi
done
