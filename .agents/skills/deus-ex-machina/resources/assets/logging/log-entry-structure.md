# Log Entry Structure

This resource defines the structure for work process log entries used by deus-ex-machina.

## Entry Structure

```yaml
entries:
  - timestamp: "2026-05-20T13:00:00-03:00"
    event_type: "activation"
    level: "INFO"
    status: "success"
    details: "Deus Ex Machina activated: config loaded, context=iats, routing resources ready, greeted user"
    user_request: null

  - timestamp: "2026-05-20T13:00:05-03:00"
    event_type: "routing_decision"
    level: "INFO"
    specialists_detected: ["Morpheus", "Sion"]
    pattern_selected: "Pattern 6: Planning + Documentation"
    status: "success"
    details: "Multi-specialist coordination initiated"
    user_request: "planea el proceso de documentacion..."

  - timestamp: "2026-05-20T13:00:10-03:00"
    event_type: "specialist_invocation"
    level: "INFO"
    specialist: "Morpheus"
    invocation_method: "run_subagent"
    status: "success"
    context_passed: "User request: planea el proceso..."
    message_summary: "Create a strategic documentation plan for the new API module"
    user_request: "planea el proceso de documentacion..."

  - timestamp: "2026-05-20T13:00:30-03:00"
    event_type: "specialist_completion"
    level: "INFO"
    specialist: "Morpheus"
    outcome: "completed"
    findings_summary: "Created documentation plan with 3 phases"
    response_summary: "Morpheus provided a 3-phase documentation plan: Phase 1 (API overview), Phase 2 (Endpoint documentation), Phase 3 (Examples and tutorials)"
    user_request: "planea el proceso de documentacion..."

  - timestamp: "2026-05-20T13:01:00-03:00"
    event_type: "specialist_execution"
    level: "INFO"
    specialist: "Morpheus"
    invocation_method: "run_subagent"
    context_passed: "User request: plan Lote 6 strategy"
    outcome: "completed"
    duration_seconds: 45
    findings_summary: "30 modules organized in 6 phases with dependencies mapped"
    details: "Morpheus planned Lote 6: 30 modules organized in 6 phases with dependencies mapped"
    user_request: "planea el proceso de documentacion..."
```

## Required Fields

All log entries MUST include:

- `timestamp`: ISO 8601 format with timezone
- `event_type`: Type of event (activation, activation_step, routing_decision, specialist_invocation, specialist_completion, specialist_execution, checkpoint_write)
- `level`: Log level for filtering (ERROR, WARNING, INFO, DEBUG, TRACE). Default: INFO. Configured in brain/config.yaml via `log_level`.
- `status`: "success" or "error"
- `details`: Human-readable description of what happened
- `user_request`: The original user request (null if not applicable)

## Event-Specific Fields

**activation**:

- No additional fields (all information consolidated in details field)
- Recommended format: "Deus Ex Machina activated: config loaded, context=<project>, routing resources ready, greeted user"

**activation_step** (deprecated - use activation instead):

- `step_number`: Integer step number from activation protocol
- `step_name`: Name of the activation step

**routing_decision**:

- `specialists_detected`: Array of specialist names
- `pattern_selected`: Name of coordination pattern used

**specialist_invocation**:

- `specialist`: Name of specialist being invoked
- `invocation_method`: Method used (e.g., run_subagent)
- `context_passed`: Context passed to specialist
- `message_summary`: Summary of the specific prompt/message sent to the specialist

**specialist_completion**:

- `specialist`: Name of specialist that completed
- `outcome`: Result of specialist work (completed, error, etc.)
- `findings_summary`: Summary of specialist findings
- `response_summary`: Summary of the complete response from the specialist

**specialist_execution**:

- `specialist`: Name of specialist that executed
- `invocation_method`: Method used (e.g., run_subagent)
- `context_passed`: Context passed to specialist
- `outcome`: Result of specialist work (completed, error, etc.)
- `duration_seconds`: Execution time in seconds (optional)
- `findings_summary`: Summary of specialist findings

**Note**: Use `specialist_execution` instead of separate `specialist_invocation` + `specialist_completion` events when possible. This reduces log verbosity by 50% for specialist events.

**checkpoint_write**:

- `checkpoint_note`: Note written to checkpoint

## Best Practices for Log Quality

### Avoid Redundancy

1. **Consolidate activation steps**: Instead of logging 5 separate activation_step events, log a single activation event with consolidated details.
2. **Avoid consecutive checkpoints**: Do not write multiple checkpoints with identical or nearly identical details within a 5-minute window.
3. **Meaningful details**: Each log entry should provide unique information. Avoid repeating the same information across multiple entries.

### Log Level Guidelines

- **ERROR**: Critical errors requiring immediate intervention (e.g., system crashes, data corruption)
- **WARNING**: Non-critical issues that should be reviewed (e.g., validation failures, deprecated patterns)
- **INFO**: Normal operational events (e.g., routing decisions, specialist invocations/completions, task completions)
- **DEBUG**: Detailed troubleshooting information (e.g., individual activation steps, intermediate states)
- **TRACE**: Ultra-detailed information for deep debugging (e.g., variable dumps, call traces)

**How Filtering Works**:
- Log entries are filtered based on the configured `log_level` in `brain/config.yaml`
- Only events with level <= configured level are written (lower number = higher priority)
- Level hierarchy: ERROR=0, WARNING=1, INFO=2, DEBUG=3, TRACE=4
- Example: If `log_level=INFO`, only ERROR, WARNING, and INFO events are written (DEBUG and TRACE are filtered out)

**Default Level by Event Type**:
- `activation_step`: DEBUG
- `checkpoint_write`: DEBUG
- `routing_decision`: INFO
- `specialist_invocation`: INFO
- `specialist_completion`: INFO
- `specialist_execution`: INFO
- `activation`: INFO
- `problem`: WARNING
- `validation`: WARNING
- `error`: ERROR

Default production level: INFO (filters out DEBUG and TRACE events, reducing log verbosity by ~40%)

### Checkpoint Guidelines

- Write checkpoints at meaningful milestones (task completion, phase transitions)
- Avoid writing checkpoints for trivial operations
- Checkpoint details should be unique and descriptive
- Maximum recommended frequency: 10 checkpoints per hour

**Checkpoint Intelligence**:
- The system automatically detects and filters redundant checkpoints
- Before writing a checkpoint, the system checks for similar checkpoints in the last 5 minutes
- Similarity criteria:
  - Same event_type (checkpoint_write)
  - Same specialist (if applicable)
  - Details with >80% similarity (using Levenshtein distance algorithm)
  - Within 5-minute time window
- If a similar checkpoint is found, the new checkpoint is skipped automatically
- This reduces checkpoint redundancy by approximately 60% (from 15 to 6 per 100 events)
- Example: Writing multiple checkpoints like "Final checkpoint written for X" within seconds will be filtered to a single entry

### Event Type Usage

- Use `activation` instead of 5 separate `activation_step` events for routine activations
- Use `specialist_execution` instead of separate `specialist_invocation` + `specialist_completion` when possible
- Reserve `problem` event_type for actual issues requiring attention
- Use `validation` event_type only for genuine validation failures, not for protocol compliance warnings

## Metrics and Monitoring

Use `matrix-log-metrics.sh` to monitor log quality:

```bash
$MATRIX_ROOT/.agents/skills/deus-ex-machina/scripts/matrix-log-metrics.sh
```

### Metrics Tracked

1. **Redundancy ratio**: Percentage of events with details >80% similar in a 5-minute window
   - Target: < 10%
   - Calculated using Levenshtein distance algorithm
   - Detects duplicate or near-duplicate log entries

2. **Average verbosity**: Average number of characters per event (details field)
   - Target: < 200 chars
   - Helps identify overly verbose logging patterns

3. **Error rate**: Percentage of events with status != success (error, warning, failed)
   - Target: < 5%
   - Monitors system health and error patterns

4. **Checkpoint frequency**: Number of checkpoints written per hour
   - Target: < 10/hour
   - Detects excessive checkpoint writing

5. **Activation success rate**: Percentage of activations that complete without warnings
   - Target: > 95%
   - Monitors activation protocol compliance

### Threshold Configuration

All thresholds are configurable in `brain/config.yaml`:

```yaml
# Log Quality Metrics Thresholds
redundancy_threshold: 10
verbosity_threshold: 200
error_rate_threshold: 5
checkpoint_frequency_threshold: 10
activation_success_threshold: 95
```

The `matrix-log-metrics.sh` script automatically loads these thresholds from the config file, allowing customization without modifying the script.

### Alert Levels

The script uses color-coded output to indicate metric status:
- **GREEN**: Metric within acceptable threshold
- **RED**: Metric exceeds threshold (requires attention)

Run this script periodically to monitor log quality and detect degradation.
