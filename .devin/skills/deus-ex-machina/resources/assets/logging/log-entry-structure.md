# Log Entry Structure

This resource defines the structure for work process log entries used by deus-ex-machina.

## Entry Structure

```yaml
entries:
  - timestamp: "2026-05-20T13:00:00-03:00"
    event_type: "activation_step"
    step_number: 1
    step_name: "Load configuration"
    status: "success" | "error"
    details: "Loaded configuration: user=Emiliano, language=es"
    user_request: null

  - timestamp: "2026-05-20T13:00:05-03:00"
    event_type: "routing_decision"
    specialists_detected: ["Morpheus", "Sion"]
    pattern_selected: "Pattern 6: Planning + Documentation"
    status: "success"
    details: "Multi-specialist coordination initiated"
    user_request: "planea el proceso de documentacion..."

  - timestamp: "2026-05-20T13:00:10-03:00"
    event_type: "specialist_invocation"
    specialist: "Morpheus"
    invocation_method: "run_subagent"
    status: "success"
    context_passed: "User request: planea el proceso..."
    message_summary: "Create a strategic documentation plan for the new API module"
    user_request: "planea el proceso de documentacion..."

  - timestamp: "2026-05-20T13:00:30-03:00"
    event_type: "specialist_completion"
    specialist: "Morpheus"
    outcome: "completed"
    findings_summary: "Created documentation plan with 3 phases"
    response_summary: "Morpheus provided a 3-phase documentation plan: Phase 1 (API overview), Phase 2 (Endpoint documentation), Phase 3 (Examples and tutorials)"
    user_request: "planea el proceso de documentacion..."
```

## Required Fields

All log entries MUST include:

- `timestamp`: ISO 8601 format with timezone
- `event_type`: Type of event (activation_step, routing_decision, specialist_invocation, specialist_completion, checkpoint_write)
- `status`: "success" or "error"
- `details`: Human-readable description of what happened
- `user_request`: The original user request (null if not applicable)

## Event-Specific Fields

**activation_step**:

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

**checkpoint_write**:

- `checkpoint_note`: Note written to checkpoint
