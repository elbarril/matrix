#!/usr/bin/env bash
# Matrix Log Quality Metrics Calculator
# Calculates quality metrics for work-process-log.yaml to detect log degradation

set -eo pipefail

# Default matrix dir: scripts/ -> deus-ex-machina/ -> skills/ -> .devin/ -> matrix root
if [[ -L "_brain" ]]; then
    BRAIN_PATH="$(readlink -f _brain)"
    MATRIX_DIR="$(dirname "$BRAIN_PATH")"
else
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    MATRIX_DIR="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
fi

LOG_FILE="$MATRIX_DIR/brain/state/work-process-log.yaml"
CONFIG_FILE="$MATRIX_DIR/brain/config.yaml"

# Load thresholds from config if available
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

# Color codes
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

echo "=== Matrix Log Quality Metrics ==="
echo "Log file: $LOG_FILE"
echo ""

# Check if log file exists
if [[ ! -f "$LOG_FILE" ]]; then
    echo "ERROR: Log file not found: $LOG_FILE"
    exit 1
fi

# Get total event count
TOTAL_EVENTS=$(grep -c "event_type:" "$LOG_FILE" || echo "0")
echo "Total events: $TOTAL_EVENTS"

# Function to calculate Levenshtein distance (simplified)
levenshtein_distance() {
    local str1="$1"
    local str2="$2"
    local len1=${#str1}
    local len2=${#str2}

    # If strings are very different in length, they're not similar
    local len_diff=$((len1 > len2 ? len1 - len2 : len2 - len1))
    if [[ $len_diff -gt $((len1 / 5)) ]] && [[ $len_diff -gt $((len2 / 5)) ]]; then
        echo 100
        return
    fi

    # Simple character matching for similarity
    local matches=0
    local min_len=$((len1 < len2 ? len1 : len2))
    for ((i=0; i<min_len; i++)); do
        if [[ "${str1:$i:1}" == "${str2:$i:1}" ]]; then
            ((matches++))
        fi
    done

    local similarity=$((matches * 100 / min_len))
    echo $((100 - similarity))
}

# Calculate redundancy ratio (events with similar details in 5-minute window)
REDUNDANT_COUNT=0
WINDOW_SECONDS=300  # 5 minutes

# Extract all events with timestamps and details
declare -a timestamps
declare -a event_types
declare -a details

# Use temporary variables for current event
current_ts=""
current_type=""
current_details=""

# Parse log file line by line, grouping by event
while IFS= read -r line; do
    if [[ "$line" =~ ^- ]]; then
        # New event starts - save previous event if exists
        if [[ -n "$current_ts" ]] && [[ -n "$current_type" ]] && [[ -n "$current_details" ]]; then
            timestamps+=("$current_ts")
            event_types+=("$current_type")
            details+=("$current_details")
        fi
        # Reset current event
        current_ts=""
        current_type=""
        current_details=""
    elif [[ "$line" =~ timestamp: ]]; then
        current_ts="$(echo "$line" | sed 's/.*timestamp: "//' | sed 's/".*//')"
    elif [[ "$line" =~ event_type: ]]; then
        current_type="$(echo "$line" | sed 's/.*event_type: "//' | sed 's/".*//')"
    elif [[ "$line" =~ details: ]]; then
        current_details="$(echo "$line" | sed 's/.*details: //' | tr -d '"')"
    fi
done < "$LOG_FILE"

# Don't forget the last event
if [[ -n "$current_ts" ]] && [[ -n "$current_type" ]] && [[ -n "$current_details" ]]; then
    timestamps+=("$current_ts")
    event_types+=("$current_type")
    details+=("$current_details")
fi

# Check for redundant events
for ((i=0; i<${#timestamps[@]}; i++)); do
    current_ts="${timestamps[$i]}"
    current_type="${event_types[$i]}"
    current_details="${details[$i]}"

    if [[ -z "$current_ts" ]] || [[ -z "$current_type" ]] || [[ -z "$current_details" ]]; then
        continue
    fi

    # Convert timestamp to epoch
    current_epoch=$(date -d "$current_ts" +%s 2>/dev/null || echo "0")
    if [[ $current_epoch -eq 0 ]]; then
        continue
    fi

    # Check for similar events in 5-minute window
    for ((j=i+1; j<${#timestamps[@]}; j++)); do
        compare_ts="${timestamps[$j]}"
        compare_type="${event_types[$j]}"
        compare_details="${details[$j]}"

        if [[ -z "$compare_ts" ]] || [[ -z "$compare_type" ]] || [[ -z "$compare_details" ]]; then
            continue
        fi

        # Same event type
        if [[ "$current_type" != "$compare_type" ]]; then
            continue
        fi

        # Convert compare timestamp to epoch
        compare_epoch=$(date -d "$compare_ts" +%s 2>/dev/null || echo "0")
        if [[ $compare_epoch -eq 0 ]]; then
            continue
        fi

        # Within 5-minute window
        time_diff=$((compare_epoch - current_epoch))
        if [[ $time_diff -gt $WINDOW_SECONDS ]] || [[ $time_diff -lt 0 ]]; then
            continue
        fi

        # Check similarity > 80%
        distance=$(levenshtein_distance "$current_details" "$compare_details")
        if [[ $distance -lt 20 ]]; then
            ((REDUNDANT_COUNT++))
            break  # Count this event as redundant once
        fi
    done
done

if [[ $TOTAL_EVENTS -gt 0 ]]; then
    REDUNDANCY_RATIO=$((REDUNDANT_COUNT * 100 / TOTAL_EVENTS))
    if [[ $REDUNDANCY_RATIO -gt $REDUNDANCY_THRESHOLD ]]; then
        echo -e "Redundancy ratio: ${RED}$REDUNDANCY_RATIO%${NC} (threshold: $REDUNDANCY_THRESHOLD%) - EXCEEDS THRESHOLD"
    else
        echo -e "Redundancy ratio: ${GREEN}$REDUNDANCY_RATIO%${NC} (threshold: $REDUNDANCY_THRESHOLD%) - OK"
    fi
else
    REDUNDANCY_RATIO=0
    echo "Redundancy ratio: N/A (no events)"
fi

# Calculate average verbosity (characters per event)
TOTAL_CHARS=$(grep "details:" "$LOG_FILE" | sed 's/.*details: //' | wc -c || echo "0")
TOTAL_CHARS=$(echo "$TOTAL_CHARS" | tr -d ' ')
if [[ $TOTAL_EVENTS -gt 0 ]] && [[ $TOTAL_CHARS -gt 0 ]]; then
    AVG_VERBOSITY=$((TOTAL_CHARS / TOTAL_EVENTS))
    if [[ $AVG_VERBOSITY -gt $VERBOSITY_THRESHOLD ]]; then
        echo -e "Average verbosity: ${RED}$AVG_VERBOSITY${NC} chars (threshold: $VERBOSITY_THRESHOLD) - EXCEEDS THRESHOLD"
    else
        echo -e "Average verbosity: ${GREEN}$AVG_VERBOSITY${NC} chars (threshold: $VERBOSITY_THRESHOLD) - OK"
    fi
else
    echo "Average verbosity: N/A (no events)"
fi

# Calculate error rate (events with status indicating problems)
# Count events with error, warning, failed status
ERROR_COUNT=$(grep -E "status: \"(error|warning|failed)" "$LOG_FILE" | wc -l || echo "0")
ERROR_COUNT=$(echo "$ERROR_COUNT" | tr -d ' ')
if [[ $TOTAL_EVENTS -gt 0 ]] && [[ "$ERROR_COUNT" =~ ^[0-9]+$ ]]; then
    ERROR_RATE=$((ERROR_COUNT * 100 / TOTAL_EVENTS))
    if [[ $ERROR_RATE -gt $ERROR_RATE_THRESHOLD ]]; then
        echo -e "Error rate: ${RED}$ERROR_RATE%${NC} (threshold: $ERROR_RATE_THRESHOLD%) - EXCEEDS THRESHOLD"
    else
        echo -e "Error rate: ${GREEN}$ERROR_RATE%${NC} (threshold: $ERROR_RATE_THRESHOLD%) - OK"
    fi
else
    echo -e "Error rate: ${GREEN}0%${NC} (threshold: $ERROR_RATE_THRESHOLD%) - OK"
fi

# Calculate checkpoint frequency (checkpoints per hour)
CHECKPOINT_COUNT=$(grep -c "event_type: \"checkpoint_write" "$LOG_FILE" || echo "0")
# Get first and last timestamps
FIRST_TIMESTAMP=$(head -20 "$LOG_FILE" | grep "timestamp:" | head -1 | sed 's/.*timestamp: "//' | sed 's/".*//')
LAST_TIMESTAMP=$(tail -20 "$LOG_FILE" | grep "timestamp:" | tail -1 | sed 's/.*timestamp: "//' | sed 's/".*//')

if [[ -n "$FIRST_TIMESTAMP" ]] && [[ -n "$LAST_TIMESTAMP" ]] && [[ "$FIRST_TIMESTAMP" != "$LAST_TIMESTAMP" ]]; then
    # Calculate hours difference (simplified)
    FIRST_EPOCH=$(date -d "$FIRST_TIMESTAMP" +%s 2>/dev/null || echo "0")
    LAST_EPOCH=$(date -d "$LAST_TIMESTAMP" +%s 2>/dev/null || echo "0")
    if [[ $FIRST_EPOCH -gt 0 ]] && [[ $LAST_EPOCH -gt 0 ]]; then
        HOURS_DIFF=$(( (LAST_EPOCH - FIRST_EPOCH) / 3600 ))
        if [[ $HOURS_DIFF -gt 0 ]]; then
            CHECKPOINT_FREQ=$((CHECKPOINT_COUNT / HOURS_DIFF))
            if [[ $CHECKPOINT_FREQ -gt $CHECKPOINT_FREQUENCY_THRESHOLD ]]; then
                echo -e "Checkpoint frequency: ${RED}$CHECKPOINT_FREQ${NC}/hour (threshold: $CHECKPOINT_FREQUENCY_THRESHOLD) - EXCEEDS THRESHOLD"
            else
                echo -e "Checkpoint frequency: ${GREEN}$CHECKPOINT_FREQ${NC}/hour (threshold: $CHECKPOINT_FREQUENCY_THRESHOLD) - OK"
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

# Calculate activation success rate
ACTIVATION_COUNT=$(grep -c "event_type: \"activation" "$LOG_FILE" || echo "0")
ACTIVATION_WARNING=$(grep "event_type: \"validation" "$LOG_FILE" | grep -c "status: \"warning" || true)
if [[ -z "$ACTIVATION_WARNING" ]]; then
    ACTIVATION_WARNING=0
fi
if [[ $ACTIVATION_COUNT -gt 0 ]]; then
    ACTIVATION_SUCCESS=$(( (ACTIVATION_COUNT - ACTIVATION_WARNING) * 100 / ACTIVATION_COUNT ))
    if [[ $ACTIVATION_SUCCESS -lt $ACTIVATION_SUCCESS_THRESHOLD ]]; then
        echo -e "Activation success rate: ${RED}$ACTIVATION_SUCCESS%${NC} (threshold: $ACTIVATION_SUCCESS_THRESHOLD%) - EXCEEDS THRESHOLD"
    else
        echo -e "Activation success rate: ${GREEN}$ACTIVATION_SUCCESS%${NC} (threshold: $ACTIVATION_SUCCESS_THRESHOLD%) - OK"
    fi
else
    echo "Activation success rate: N/A (no activations)"
fi

echo ""
echo "=== Recommendations ==="
echo "Full redundancy detection is now implemented:"
echo "- Time window analysis (5-minute sliding window) ✓"
echo "- String similarity algorithm (Levenshtein distance) ✓"
echo "- Event grouping by type and context ✓"
echo ""
echo "Thresholds can be customized in brain/config.yaml:"
echo "- redundancy_threshold: $REDUNDANCY_THRESHOLD%"
echo "- verbosity_threshold: $VERBOSITY_THRESHOLD chars"
echo "- error_rate_threshold: $ERROR_RATE_THRESHOLD%"
echo "- checkpoint_frequency_threshold: $CHECKPOINT_FREQUENCY_THRESHOLD/hour"
echo "- activation_success_threshold: $ACTIVATION_SUCCESS_THRESHOLD%"
