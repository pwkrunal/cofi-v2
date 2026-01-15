# Migration Plan: Remove processing_logs Table

## Decision
**Consolidate `processing_logs` into `batchExecutionLog` table**

Both tables serve the same purpose but `batchExecutionLog` is more comprehensive with better features.

---

## Files to Modify

### 1. Remove ProcessingLogRepo from database.py

**File:** `cofi-service/src/database.py`

**Action:** Delete lines 472-591 (entire `ProcessingLogRepo` class)

---

### 2. Remove ProcessingLogRepo imports

**Files to update:**
- `cofi-service/src/pipeline/base.py` - Line 9
- `cofi-service/src/pipeline/llm1_stage.py` - Line 9
- `cofi-service/src/pipeline/llm2_stage.py` - Line 9
- `cofi-service/src/audit_pipeline.py` - Line 7
- `cofi-service/src/metadata_manager.py` - Line 11

**Action:** Remove `ProcessingLogRepo` from import statements

---

### 3. Remove processing_log_repo initialization

**Files to update:**
- `cofi-service/src/pipeline/base.py` - Line 43
- `cofi-service/src/pipeline/llm1_stage.py` - Line 122
- `cofi-service/src/pipeline/llm2_stage.py` - Line 139
- `cofi-service/src/audit_pipeline.py` - Line 49
- `cofi-service/src/metadata_manager.py` - Line 238

**Action:** Remove lines like `self.processing_log_repo = ProcessingLogRepo(self.db)`

---

### 4. Replace processing_logs calls with EventLogger

**In `cofi-service/src/pipeline/base.py`:**

Lines 49-95 - Delete `log_processing_failure()` and `log_processing_success()` methods
Lines 205-224 - Remove processing_logs calls (already have EventLogger)

**In `cofi-service/src/pipeline/llm1_stage.py`:**

Lines 128-148 - Delete `log_processing_failure()` method
Lines 358-363 - Remove processing_logs call (replace with EventLogger.file_error)
Lines 377-384 - Remove processing_logs call (already have EventLogger.file_error)

**In `cofi-service/src/pipeline/llm2_stage.py`:**

Lines 161-181 - Delete `log_processing_failure()` method
Lines 514-519 - Remove processing_logs call (already have EventLogger.file_error)

**In `cofi-service/src/audit_pipeline.py`:**

Lines 137-147 - Remove processing_logs call (already have EventLogger.file_error)

**In `cofi-service/src/metadata_manager.py`:**

Lines 240-258 - Delete `log_processing_failure()` method
Lines 279-284 - Remove processing_logs call (already have EventLogger.file_error)
Lines 358-364 - Remove processing_logs call (already have EventLogger.file_error)
Lines 445-451 - Remove processing_logs call (already have EventLogger.file_error)

---

### 5. Update Documentation

**Files to update:**
- `FINAL_IMPLEMENTATION_SUMMARY.md`
- `FIXES_APPLIED_SUMMARY.md`
- `AUDIT_REAUDIT_FIXES_APPLIED.md`
- `BATCH_PROCESSING_REVIEW.md`

**Action:** Replace all references to `processing_logs` with `batchExecutionLog`

---

## Database Migration

### Optional: Drop processing_logs Table

**Only run this AFTER deploying code changes:**

```sql
-- Backup first (if table has data)
CREATE TABLE processing_logs_backup AS SELECT * FROM processing_logs;

-- Then drop
DROP TABLE IF EXISTS processing_logs;
```

**Note:** You can keep the table for now if you want to preserve historical data. The new code simply won't use it.

---

## Code Changes Summary

### Before (Dual Logging):
```python
# Log to processing_logs
self.processing_log_repo.log_failure(
    call_id=file_name,
    batch_id=batch_id,
    stage_name="lid",
    error_message=str(e),
    input_payload=json.dumps(payload)
)

# Log to batchExecutionLog
EventLogger.file_error(batch_id, 'lid', file_name, str(e), gpu_ip)
```

### After (Single Logging):
```python
# Only log to batchExecutionLog
EventLogger.file_error(
    batch_id, 
    'lid', 
    file_name, 
    str(e), 
    gpu_ip,
    payload=payload  # Can pass payload if needed
)
```

---

## Benefits After Migration

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| **Logging calls per file** | 2 calls | 1 call | 50% reduction |
| **DB inserts per 10K batch** | ~200K | ~100K | 50% reduction |
| **Tables to query** | 2 tables | 1 table | Simpler queries |
| **Code complexity** | 2 repos + methods | 1 module | Cleaner code |
| **Features** | Basic | Advanced (eventType, metadata, progress) | Better visibility |

---

## Testing Plan

### 1. After Code Changes
- [ ] Run linter: `pylint cofi-service/src/`
- [ ] Check no references to `processing_logs` remain
- [ ] Check no references to `ProcessingLogRepo` remain

### 2. After Deployment
- [ ] Process small batch (10 files)
- [ ] Verify only `batchExecutionLog` has entries
- [ ] Verify error logs are captured
- [ ] Verify dashboard still works

### 3. Queries to Verify

```sql
-- Check batchExecutionLog has error events
SELECT COUNT(*) FROM batchExecutionLog 
WHERE eventType = 'error' AND batchId = <TEST_BATCH_ID>;

-- Should return > 0 if any errors occurred

-- Check processing_logs is not being written to
SELECT COUNT(*) FROM processing_logs 
WHERE batch_id = '<TEST_BATCH_ID>';

-- Should return 0 (no new entries)
```

---

## Rollback Plan

If issues arise:

1. **Keep backup of old code**
2. **Don't drop processing_logs table**
3. **Can revert code changes and redeploy**

---

## Implementation Order

1. ✅ Create this migration plan
2. ⏳ Review and approve plan
3. ⏳ Apply code changes (remove ProcessingLogRepo)
4. ⏳ Update documentation
5. ⏳ Test in staging
6. ⏳ Deploy to production
7. ⏳ Monitor for 1 week
8. ⏳ (Optional) Drop processing_logs table

---

## Estimated Impact

- **Code Changes:** 10 files
- **Lines Removed:** ~300 lines
- **Lines Modified:** ~50 lines
- **DB Performance:** 50% fewer writes
- **Code Complexity:** Reduced
- **Risk Level:** Low (EventLogger already working)
- **Time to Implement:** 1-2 hours
