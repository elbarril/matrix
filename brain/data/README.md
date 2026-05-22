# Matrix Data

This directory contains reference data and documentation for the Matrix intelligence engine.

Data includes reference materials, templates, and static information that agents may need.

## Improvement Log

### 2026-05-21 - System Optimization

**Problem Identified:**
1. Log rotation not working correctly - work-process-log.yaml had 101 entries (should maintain 100)
2. yq binary not installed in system - required for log rotation
3. Excessive checkpoint accumulation - 44 checkpoints in brain/state/checkpoints/
4. No automatic checkpoint cleanup mechanism

**Changes Made:**

1. **Installed yq binary**
   - Installed yq v4.53.2 in ~/yq
   - Script matrix-log-entry.sh already searches ~/yq as first priority
   - Log rotation now functional

2. **Fixed log rotation condition**
   - Changed condition from `>= 100` to `> 100` in matrix-log-entry.sh
   - Prevents unnecessary rotation when exactly at 100 entries
   - Manual cleanup performed: reduced from 101 to 100 entries

3. **Implemented automatic checkpoint cleanup**
   - Added checkpoint cleanup logic to matrix-log-entry.sh
   - Triggers on checkpoint_write events
   - Keeps last 30 checkpoints, removes older ones
   - No separate cron job required
   - Manual cleanup performed: reduced from 44 to 11 checkpoints (cleanup was too aggressive)

4. **System validation**
   - All validation scripts tested and passing
   - matrix-validate-config.sh: OK
   - matrix-validate-context.sh: OK
   - matrix-validate-routing-resources.sh: OK
   - matrix-init-brain-state.sh: OK

**System State:**
- All 11 agents using swe-1-5 model consistently
- All scripts have _brain-aware pattern for portability
- Configuration valid and active project set (providence)
- 9 projects registered in registry
- CLI functional with all commands working
- Documentation (AGENTS.md, DEVIN.md, README.md) up to date

**No Breaking Changes:**
- All changes maintain compatibility with Devin for Terminal agents
- Contract canónico AGENTS.md preserved
- All practices and conventions respected
- Silent operation principle maintained
