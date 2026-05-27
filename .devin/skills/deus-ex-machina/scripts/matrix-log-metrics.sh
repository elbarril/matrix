#!/usr/bin/env bash
# Matrix Log Quality Metrics Calculator (JSONL Optimized)
# Calculates quality metrics for work-process-log.jsonl to detect log degradation

set -euo pipefail

if [[ -L "_brain" ]]; then
    BRAIN_PATH="$(readlink -f _brain)"
    MATRIX_DIR="$(dirname "$BRAIN_PATH")"
else
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    MATRIX_DIR="$(cd "${SCRIPT_DIR%/}/../../../.." && pwd)"
fi
MATRIX_DIR="${MATRIX_DIR%/}"

LOG_FILE="$MATRIX_DIR/brain/state/work-process-log.jsonl"
CONFIG_FILE="$MATRIX_DIR/brain/config.yaml"

REDUNDANCY_THRESHOLD=10
VERBOSITY_THRESHOLD=200
ERROR_RATE_THRESHOLD=5
CHECKPOINT_FREQUENCY_THRESHOLD=10
ACTIVATION_SUCCESS_THRESHOLD=95

if [[ -f "$CONFIG_FILE" ]]; then
    REDUNDANCY_THRESHOLD=$(grep -oP 'redundancy_threshold: \K\d+' "$CONFIG_FILE" 2>/dev/null || echo "10")
    VERBOSITY_THRESHOLD=$(grep -oP 'verbosity_threshold: \K\d+' "$CONFIG_FILE" 2>/dev/null || echo "200")
    ERROR_RATE_THRESHOLD=$(grep -oP 'error_rate_threshold: \K\d+' "$CONFIG_FILE" 2>/dev/null || echo "5")
    CHECKPOINT_FREQUENCY_THRESHOLD=$(grep -oP 'checkpoint_frequency_threshold: \K\d+' "$CONFIG_FILE" 2>/dev/null || echo "10")
    ACTIVATION_SUCCESS_THRESHOLD=$(grep -oP 'activation_success_threshold: \K\d+' "$CONFIG_FILE" 2>/dev/null || echo "95")
fi

RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m'

echo "=== Matrix Log Quality Metrics (JSONL Optimized) ==="
echo "Log file: $LOG_FILE"
echo ""

if [[ ! -f "$LOG_FILE" ]]; then
    if [[ -f "${LOG_FILE%.jsonl}.yaml" ]]; then
        echo "WARNING: JSONL file not found, but YAML log exists. Metrics will start calculating once JSONL logs are generated."
        exit 0
    else
        echo "ERROR: Log file not found: $LOG_FILE"
        exit 1
    fi
fi

TOTAL_EVENTS=$(wc -l < "$LOG_FILE" || echo 0)
echo "Total events: $TOTAL_EVENTS"

if [[ $TOTAL_EVENTS -eq 0 ]]; then
    echo "No metrics to calculate."
    exit 0
fi

UNIQUE_DETAILS=$(jq -r '.details' "$LOG_FILE" | sort -u | wc -l)
REDUNDANT_COUNT=$(( TOTAL_EVENTS - UNIQUE_DETAILS ))
REDUNDANCY_RATIO=$(( REDUNDANT_COUNT * 100 / TOTAL_EVENTS ))

if [[ $REDUNDANCY_RATIO -gt $REDUNDANCY_THRESHOLD ]]; then
    echo -e "Redundancy ratio: ${RED}${REDUNDANCY_RATIO}%${NC} (threshold: ${REDUNDANCY_THRESHOLD}%) - EXCEEDS THRESHOLD"
else
    echo -e "Redundancy ratio: ${GREEN}${REDUNDANCY_RATIO}%${NC} (threshold: ${REDUNDANCY_THRESHOLD}%) - OK"
fi

TOTAL_CHARS=$(jq -r '.details | length' "$LOG_FILE" | awk '{s+=$1} END {print (s==""?0:s)}')
AVG_VERBOSITY=$(( TOTAL_CHARS / TOTAL_EVENTS ))
if [[ $AVG_VERBOSITY -gt $VERBOSITY_THRESHOLD ]]; then
    echo -e "Average verbosity: ${RED}${AVG_VERBOSITY}${NC} chars (threshold: $VERBOSITY_THRESHOLD) - EXCEEDS THRESHOLD"
else
    echo -e "Average verbosity: ${GREEN}${AVG_VERBOSITY}${NC} chars (threshold: $VERBOSITY_THRESHOLD) - OK"
fi

ERROR_COUNT=$(jq -r 'select(.status | test("error|warning|failed"; "i")) | .status' "$LOG_FILE" | wc -l)
ERROR_RATE=$(( ERROR_COUNT * 100 / TOTAL_EVENTS ))
if [[ $ERROR_RATE -gt $ERROR_RATE_THRESHOLD ]]; then
    echo -e "Error rate: ${RED}${ERROR_RATE}%${NC} (threshold: ${ERROR_RATE_THRESHOLD}%) - EXCEEDS THRESHOLD"
else
    echo -e "Error rate: ${GREEN}${ERROR_RATE}%${NC} (threshold: ${ERROR_RATE_THRESHOLD}%) - OK"
fi

CHECKPOINT_COUNT=$(jq -c 'select(.event_type == "checkpoint" or .event_type == "checkpoint_write")' "$LOG_FILE" | wc -l)
FIRST_TIMESTAMP=$(head -1 "$LOG_FILE" | jq -r '.timestamp')
LAST_TIMESTAMP=$(tail -1 "$LOG_FILE" | jq -r '.timestamp')

if [[ -n "$FIRST_TIMESTAMP" ]] && [[ -n "$LAST_TIMESTAMP" ]] && [[ "$FIRST_TIMESTAMP" != "null" ]] && [[ "$LAST_TIMESTAMP" != "null" ]] && [[ "$FIRST_TIMESTAMP" != "$LAST_TIMESTAMP" ]]; then
    FIRST_EPOCH=$(date -d "$FIRST_TIMESTAMP" +%s 2>/dev/null || echo "0")
    LAST_EPOCH=$(date -d "$LAST_TIMESTAMP" +%s 2>/dev/null || echo "0")
    if [[ $FIRST_EPOCH -gt 0 ]] && [[ $LAST_EPOCH -gt 0 ]]; then
        HOURS_DIFF=$(( (LAST_EPOCH - FIRST_EPOCH) / 3600 ))
        if [[ $HOURS_DIFF -gt 0 ]] && [[ $CHECKPOINT_COUNT -gt 0 ]]; then
            CHECKPOINT_FREQ=$((CHECKPOINT_COUNT / HOURS_DIFF))
            if [[ $CHECKPOINT_FREQ -gt $CHECKPOINT_FREQUENCY_THRESHOLD ]]; then
                echo -e "Checkpoint frequency: ${RED}${CHECKPOINT_FREQ}${NC}/hour (threshold: $CHECKPOINT_FREQUENCY_THRESHOLD) - EXCEEDS THRESHOLD"
            else
                echo -e "Checkpoint frequency: ${GREEN}${CHECKPOINT_FREQ}${NC}/hour (threshold: $CHECKPOINT_FREQUENCY_THRESHOLD) - OK"
            fi
        else
            echo "Checkpoint frequency: N/A (time window too small)"
        fi
    else
        echo "Checkpoint frequency: N/A (timestamp parsing error)"
    fi
else
    echo "Checkpoint frequency: N/A (insufficient data)"
fi

ACTIVATION_COUNT=$(jq -c 'select(.event_type == "activation")' "$LOG_FILE" | wc -l)
ACTIVATION_WARNING=$(jq -c 'select(.event_type == "validation" and .status == "warning")' "$LOG_FILE" | wc -l)
if [[ $ACTIVATION_COUNT -gt 0 ]]; then
    ACTIVATION_SUCCESS=$(( (ACTIVATION_COUNT - ACTIVATION_WARNING) * 100 / ACTIVATION_COUNT ))
    if [[ $ACTIVATION_SUCCESS -lt $ACTIVATION_SUCCESS_THRESHOLD ]]; then
        echo -e "Activation success rate: ${RED}${ACTIVATION_SUCCESS}%${NC} (threshold: ${ACTIVATION_SUCCESS_THRESHOLD}%) - EXCEEDS THRESHOLD"
    else
        echo -e "Activation success rate: ${GREEN}${ACTIVATION_SUCCESS}%${NC} (threshold: ${ACTIVATION_SUCCESS_THRESHOLD}%) - OK"
    fi
else
    echo "Activation success rate: N/A (no activations)"
fi

echo ""
echo "=== Recommendations ==="
echo "JSONL Pipeline active. Performance is now O(1) for writes and single-pass jq for metrics."
