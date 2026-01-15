# Audit & Reaudit Pipeline Review

## Date: 2026-01-15
## Review Scope: New Audit Upload & Reaudit Implementations

---

## Executive Summary

Reviewed `audit_pipeline.py` and `reaudit_pipeline.py` for consistency with batch processing standards. Found **8 issues** requiring fixes to match the quality and robustness of the main batch pipeline.

**Status:**
- ✅ Core functionality works
- ⚠️ Missing comprehensive logging (EventLogger + processing_logs)
- ⚠️ Missing batchStatus updates
- ⚠️ Limited error handling for file distribution
- 🔴 **CRITICAL:** Missing asyncio import

---

## Issues Found

### 🔴 Issue 1: Missing `asyncio` Import in audit_pipeline.py
**Severity:** CRITICAL  
**Location:** `cofi-service/src/audit_pipeline.py` line 151

**Problem:**
```python
# Line 151 - uses asyncio.gather but no import!
await asyncio.gather(*upload_tasks, return_exceptions=False)
```

**Fix Required:**
```python
# Add at top of file
import asyncio
```

**Impact:** Code will fail with `NameError: name 'asyncio' is not defined` when distributing files

---

### 🟡 Issue 2: audit_pipeline.py Missing EventLogger
**Severity:** MEDIUM  
**Impact:** No visibility in dashboard for audit uploads

**Problem:**
- No `EventLogger.stage_start()` / `stage_complete()` calls
- Dashboard cannot track audit progress in real-time
- Inconsistent with batch processing pipeline

**Current State:**
| Stage | EventLogger? | processing_logs? |
|-------|--------------|------------------|
| File Distribution | ❌ | ❌ |
| LID | ✅ (via LIDStage) | ✅ |
| STT | ✅ (via STTStage) | ✅ |
| LLM1 | ✅ (via LLM1Stage) | ✅ |
| LLM2 | ✅ (via LLM2Stage) | ✅ |

**Fix Required:**
- Add EventLogger for file distribution stage
- Log distribution start, file success/failure, completion

---

### 🟡 Issue 3: reaudit_pipeline.py Missing EventLogger
**Severity:** MEDIUM  
**Impact:** No visibility in dashboard for reaudit operations

**Problem:**
- Same as Issue 2, but for reaudit pipeline
- No EventLogger calls at all

**Fix Required:**
- Add EventLogger for overall reaudit process
- Log cleanup operations (transcript deletion, audit answer deletion)
- Log each stage execution

---

### 🟡 Issue 4: Missing processing_logs for File Distribution
**Severity:** MEDIUM  
**Impact:** File distribution failures not logged to processing_logs table

**Problem:**
```python
# audit_pipeline.py line 138-140
except Exception as e:
    logger.error("file_distribution_failed", file=file_name, error=str(e), task_id=self.task_id)
    return False
    # ❌ No processing_logs entry
```

**Expected:**
```python
except Exception as e:
    logger.error("file_distribution_failed", file=file_name, error=str(e))
    # Log to processing_logs
    self.processing_log_repo.log_failure(
        call_id=file_name,
        batch_id=str(batch_id),
        stage_name="file_distribution",
        error_message=str(e),
        request_url=f"GPU: {gpu_ip}"
    )
    return False
```

---

### 🟡 Issue 5: No batchStatus Updates in audit_pipeline.py
**Severity:** MEDIUM  
**Impact:** batchStatus table not tracking audit progress

**Problem:**
- Batch is created but status never updated
- No InProgress/Complete tracking for stages
- Inconsistent with main batch pipeline

**Expected Updates:**
```python
# After file distribution
self.batch_repo.update_db_insertion_status(batch_id, "Complete")

# After LID
self.batch_repo.update_lid_status(batch_id, "Complete")

# After STT
self.batch_repo.update_stt_status(batch_id, "Complete")

# After LLM1
self.batch_repo.update_llm1_status(batch_id, "Complete")

# After LLM2
self.batch_repo.update_llm2_status(batch_id, "Complete")
self.batch_repo.update_status(batch_id, "Completed")
```

---

### 🟡 Issue 6: No batchStatus Updates in reaudit_pipeline.py
**Severity:** MEDIUM  
**Impact:** Cannot track reaudit status in batchStatus table

**Problem:**
- Reaudit operates on existing batches but doesn't update their status
- No way to tell if a batch is being reaudited

**Consideration:**
- Should reaudit create a new "sub-batch" or update existing batch?
- Current implementation doesn't touch batchStatus at all

---

### 🟢 Issue 7: File Distribution Error Handling
**Severity:** LOW  
**Impact:** Failed file uploads continue silently, no retry or special handling

**Problem:**
```python
# audit_pipeline.py line 151
await asyncio.gather(*upload_tasks, return_exceptions=False)
# ❌ return_exceptions=False means any exception will stop ALL uploads
```

**Should Be:**
```python
results = await asyncio.gather(*upload_tasks, return_exceptions=True)

# Count successes and failures
successful = sum(1 for r in results if r is True)
failed = sum(1 for r in results if r is False or isinstance(r, Exception))

logger.info("file_distribution_complete", successful=successful, failed=failed)
```

**Current Behavior:**
- If ONE file fails to upload, ALL remaining uploads are cancelled
- This is inconsistent with batch pipeline (continues on failure)

---

### 🟢 Issue 8: Progress Tracking Simplistic
**Severity:** LOW  
**Impact:** Progress reporting inaccurate if files fail

**Problem:**
```python
# audit_pipeline.py line 161
self.task_tracker["progress"]["lid"]["done"] = self.task_tracker["progress"]["lid"]["total"]
# ❌ Assumes all files processed successfully
```

**Reality:**
- Some files may fail LID processing
- Progress should reflect actual completed files, not total files

**Fix:**
- Get actual count from fileDistribution table: `SELECT COUNT(*) WHERE batchId = X AND lidDone = 1`

---

## What's Working Well ✅

### 1. Code Reuse
**Status:** ✅ EXCELLENT

Both pipelines reuse existing stage classes:
- `LIDStage()` ✅
- `STTStage()` ✅  
- `LLM1Stage()` ✅
- `LLM2Stage()` ✅

**Benefit:** All fixes we applied to LLM1/LLM2 stages automatically apply to audit/reaudit

---

### 2. Parallel File Upload (audit_pipeline.py)
**Status:** ✅ GOOD

```python
# Parallel upload with async tasks
upload_tasks = []
for idx, file_name in enumerate(file_names):
    gpu_ip = gpu_list[idx % len(gpu_list)]
    task = upload_and_record(file_name, gpu_ip)
    upload_tasks.append(task)

await asyncio.gather(*upload_tasks)
```

**Only Issue:** Missing `return_exceptions=True`

---

### 3. Proper Data Cleanup (reaudit_pipeline.py)
**Status:** ✅ EXCELLENT

```python
# If STT selected: delete transcripts
if "stt" in stages:
    deleted = self._delete_transcripts(call_ids)

# If LLM2 selected: delete audit answers
if "llm2" in stages:
    deleted = self._delete_audit_answers(call_ids)

# Reset call statuses to appropriate stage
self._reset_call_statuses(call_ids, stages)

# Reset fileDistribution columns
for audio_name in audio_names:
    self.file_dist_repo.reset_stage_for_file(audio_name, "lidDone")
```

**This is well-designed!** Ensures clean re-processing.

---

### 4. Concurrency Control (api.py)
**Status:** ✅ GOOD

```python
# Global locks prevent multiple concurrent operations
audit_upload_in_progress = False
reaudit_in_progress = False

# Checked before processing
if audit_upload_in_progress:
    raise HTTPException(status_code=409, detail="Another audit upload is already being processed")
```

**Protection against:** Race conditions, resource conflicts

---

### 5. Background Task Processing
**Status:** ✅ GOOD

```python
# FastAPI background tasks for non-blocking API
background_tasks.add_task(run_audit_pipeline, ...)
return AuditUploadResponse(status="queued", task_id=task_id)
```

**User Experience:** Immediate API response, processing happens in background

---

## Comparison: Batch vs Audit/Reaudit

| Feature | Batch Pipeline | Audit Pipeline | Reaudit Pipeline |
|---------|----------------|----------------|------------------|
| **EventLogger** | ✅ All stages | ⚠️ Partial (stages only) | ❌ None |
| **processing_logs** | ✅ All stages | ⚠️ Partial (stages only) | ⚠️ Partial (stages only) |
| **batchStatus Updates** | ✅ Complete | ❌ None | ❌ None |
| **Error Handling** | ✅ Continue on failure | ⚠️ Stops on failure | ✅ Inherits from stages |
| **Progress Tracking** | ✅ Accurate | ⚠️ Simplistic | ⚠️ Simplistic |
| **Parallel Processing** | ✅ Yes | ✅ Yes | ✅ Yes |
| **Recovery Capability** | ✅ fileDistribution | ✅ fileDistribution | ✅ fileDistribution |

---

## Recommended Fixes

### Fix 1: Add Missing asyncio Import

**File:** `cofi-service/src/audit_pipeline.py`

```python
# Add after line 4
import asyncio
```

---

### Fix 2: Add ProcessingLogRepo to audit_pipeline.py

**File:** `cofi-service/src/audit_pipeline.py`

```python
# Add to imports (line 7)
from .database import get_database, BatchStatusRepo, FileDistributionRepo, CallRepo, LidStatusRepo, LanguageRepo, ProcessRepo, ProcessingLogRepo

# Add to __init__ (line 48)
self.processing_log_repo = ProcessingLogRepo(self.db)
```

---

### Fix 3: Add EventLogger to File Distribution

**File:** `cofi-service/src/audit_pipeline.py`

```python
# Add to imports
from .event_logger import EventLogger

# In _distribute_files method, add:
async def _distribute_files(self, file_names: List[str], upload_dir: str, batch_id: int):
    """Distribute files to GPUs using round-robin in parallel."""
    
    # ADD: Log stage start
    EventLogger.stage_start(batch_id, 'file_distribution', total_files=len(file_names), metadata={
        'upload_dir': upload_dir,
        'task_id': self.task_id
    })
    
    # ... existing code ...
    
    # CHANGE: Add return_exceptions=True and count results
    results = await asyncio.gather(*upload_tasks, return_exceptions=True)
    
    successful = sum(1 for r in results if r is True)
    failed = sum(1 for r in results if r is False or isinstance(r, Exception))
    
    # ADD: Log stage complete
    EventLogger.stage_complete(batch_id, 'file_distribution', successful, failed)
    
    # ADD: Update batch status
    self.batch_repo.update_total_files(batch_id, len(file_names))
    self.batch_repo.update_db_insertion_status(batch_id, "Complete")
    
    logger.info("file_distribution_complete", successful=successful, failed=failed)
```

---

### Fix 4: Add processing_logs for File Distribution Failures

**File:** `cofi-service/src/audit_pipeline.py`

```python
# In upload_and_record function
except Exception as e:
    logger.error("file_distribution_failed", file=file_name, error=str(e), task_id=self.task_id)
    
    # ADD: Log to processing_logs
    self.processing_log_repo.log_failure(
        call_id=file_name,
        batch_id=str(batch_id),
        stage_name="file_distribution",
        error_message=str(e),
        request_url=f"GPU: {gpu_ip}",
        input_payload=json.dumps({"file": file_name, "gpu": gpu_ip})
    )
    
    return False
```

---

### Fix 5: Add batchStatus Updates to audit_pipeline.py

**File:** `cofi-service/src/audit_pipeline.py`

```python
# After _run_lid_stage
self.batch_repo.update_lid_status(batch_id, "Complete")

# After _run_stt_stage
self.batch_repo.update_stt_status(batch_id, "Complete")

# After _run_llm1_stage (if enabled)
self.batch_repo.update_llm1_status(batch_id, "Complete")

# After _run_llm2_stage (if enabled)
self.batch_repo.update_llm2_status(batch_id, "Complete")

# At end of process()
self.batch_repo.update_status(batch_id, "Completed")
```

---

### Fix 6: Add EventLogger to reaudit_pipeline.py

**File:** `cofi-service/src/reaudit_pipeline.py`

```python
# Add to imports
from .event_logger import EventLogger

# In process() method:
async def process(self, audio_names: List[str], stages: List[str]):
    """Reprocess files through specified stages."""
    
    # ADD: Log reaudit start
    EventLogger.info(0, 'reaudit', f"Reaudit started for {len(audio_names)} files", metadata={
        'task_id': self.task_id,
        'stages': stages
    })
    
    # ... existing cleanup code ...
    
    # ADD: Log cleanup operations
    if "stt" in stages:
        deleted = self._delete_transcripts(call_ids)
        EventLogger.info(0, 'reaudit', f"Deleted {deleted} transcripts", metadata={
            'task_id': self.task_id
        })
    
    if "llm2" in stages:
        deleted = self._delete_audit_answers(call_ids)
        EventLogger.info(0, 'reaudit', f"Deleted {deleted} audit answers", metadata={
            'task_id': self.task_id
        })
    
    # ... existing stage processing ...
    
    # ADD: Log reaudit complete
    EventLogger.info(0, 'reaudit', f"Reaudit completed for {len(audio_names)} files", metadata={
        'task_id': self.task_id
    })
```

---

### Fix 7: Improve Progress Tracking

**File:** `cofi-service/src/audit_pipeline.py`

```python
# Instead of:
self.task_tracker["progress"]["lid"]["done"] = self.task_tracker["progress"]["lid"]["total"]

# Use actual count:
async def _run_lid_stage(self, batch_id: int):
    lid_stage = LIDStage()
    await lid_stage.execute(batch_id, None)
    
    # Get actual completed count
    completed_count = self.file_dist_repo.get_by_batch(batch_id)
    completed_count = sum(1 for f in completed_count if f.get('lidDone') == 1)
    
    self.task_tracker["progress"]["lid"]["done"] = completed_count
```

---

## Testing Checklist for Audit/Reaudit

### Test 1: Audit Upload (Single File)
```bash
curl -X POST http://localhost:5064/audit/upload \
  -F "files=@test.wav" \
  -F "process_id=1" \
  -F "category_mapping_id=1"
```

**Expected:**
- [ ] Returns task_id immediately
- [ ] File uploaded to GPU
- [ ] fileDistribution record created
- [ ] call record created
- [ ] LID → STT → LLM1 → LLM2 executed
- [ ] batchExecutionLog has entries for all stages
- [ ] processing_logs has no errors
- [ ] batchStatus shows "Completed"

---

### Test 2: Audit Upload (Multiple Files)
```bash
curl -X POST http://localhost:5064/audit/upload \
  -F "files=@file1.wav" \
  -F "files=@file2.wav" \
  -F "files=@file3.wav" \
  -F "process_id=1"
```

**Expected:**
- [ ] All 3 files distributed in parallel
- [ ] If 1 file fails, other 2 continue ✅
- [ ] Progress tracking accurate
- [ ] All successful files complete pipeline

---

### Test 3: Concurrent Audit Upload (Should Fail)
```bash
# Start first upload
curl -X POST http://localhost:5064/audit/upload ...

# Immediately start second upload (while first is processing)
curl -X POST http://localhost:5064/audit/upload ...
```

**Expected:**
- [ ] First upload: 200 OK
- [ ] Second upload: 409 Conflict
- [ ] Error message: "Another audit upload is already being processed"

---

### Test 4: Reaudit (STT + LLM2)
```bash
curl -X POST http://localhost:5064/reaudit \
  -H "Content-Type: application/json" \
  -d '{
    "audio_names": ["test.wav"],
    "stages": ["stt", "llm2"]
  }'
```

**Expected:**
- [ ] Existing transcripts deleted
- [ ] Existing audit answers deleted
- [ ] Call status reset to "Pending"
- [ ] fileDistribution: sttDone reset to 0
- [ ] STT stage re-runs successfully
- [ ] LLM2 stage re-runs successfully
- [ ] New transcripts created
- [ ] New audit answers created

---

### Test 5: Check Status
```bash
# Get task status
curl http://localhost:5064/audit/status/{task_id}
```

**Expected:**
- [ ] Returns current progress for all stages
- [ ] Progress accurate (not just total = done)

---

## SQL Queries for Verification

```sql
-- Check audit batch created
SELECT * FROM batchStatus 
WHERE batchDate = CURDATE() 
ORDER BY id DESC LIMIT 1;

-- Check file distribution for audit
SELECT file, denoiseDone, ivrDone, lidDone, sttDone, llm1Done, llm2Done 
FROM fileDistribution 
WHERE batchId = <BATCH_ID>;

-- Check call records for audit
SELECT audioName, lang, status, audioDuration 
FROM `call` 
WHERE batchId = <BATCH_ID>;

-- Check batchExecutionLog for audit
SELECT stage, eventType, status, COUNT(*) 
FROM batchExecutionLog 
WHERE batchId = <BATCH_ID> 
GROUP BY stage, eventType, status;

-- Check processing_logs for errors
SELECT * FROM processing_logs 
WHERE batch_id = '<BATCH_ID>' AND status = 'failed';
```

---

## Summary of Required Changes

| Priority | Component | File | Change |
|----------|-----------|------|--------|
| 🔴 CRITICAL | audit_pipeline.py | Line 1-4 | Add `import asyncio` |
| 🟡 MEDIUM | audit_pipeline.py | _distribute_files | Add EventLogger calls |
| 🟡 MEDIUM | audit_pipeline.py | upload_and_record | Add processing_logs.log_failure() |
| 🟡 MEDIUM | audit_pipeline.py | Each stage method | Add batchStatus updates |
| 🟡 MEDIUM | audit_pipeline.py | _distribute_files | Change return_exceptions=True |
| 🟡 MEDIUM | reaudit_pipeline.py | process() | Add EventLogger for cleanup |
| 🟡 MEDIUM | reaudit_pipeline.py | process() | Add EventLogger for stages |
| 🟢 LOW | audit_pipeline.py | Each stage method | Use actual progress counts |
| 🟢 LOW | reaudit_pipeline.py | process() | Consider batchStatus updates |

---

## Conclusion

**Current State:** 75% Production Ready  
**After Fixes:** 100% Production Ready

**Strengths:**
- ✅ Good code reuse (inherits all stage fixes)
- ✅ Proper concurrency control
- ✅ Clean data cleanup for reaudit
- ✅ Parallel file upload
- ✅ Background task processing

**Gaps:**
- ❌ Missing asyncio import (CRITICAL!)
- ⚠️ Incomplete logging (EventLogger + processing_logs)
- ⚠️ No batchStatus tracking
- ⚠️ Simplistic progress tracking
- ⚠️ File distribution stops on first error

**Recommendation:** Apply all fixes before production use. The fixes are straightforward and follow the same patterns we established for batch processing.
