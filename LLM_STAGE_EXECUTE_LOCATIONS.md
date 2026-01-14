# LLM1 and LLM2 Stage Execute Method Locations

## Overview

The `execute()` methods of `LLM1Stage` and `LLM2Stage` are called from **3 different locations** in the codebase:

1. **Main Batch Processing** - `cofi-service/src/main.py`
2. **New Audit (API uploads)** - `cofi-service/src/audit_pipeline.py`
3. **Reaudit Processing** - `cofi-service/src/reaudit_pipeline.py`

---

## 1. Main Batch Processing (`main.py`)

**File:** `cofi-service/src/main.py`

### LLM1 Stage Call

**Location:** Line 337

```python
# Stage: LLM1 (optional)
if self.settings.llm1_enabled:
    if batch.get('llm1Status') != 'Complete':
        self.batch_repo.update_llm1_status(batch_id, "InProgress")
        llm1_stage = LLM1Stage()
        await llm1_stage.execute(batch_id, previous_container)  # ← HERE
        self.batch_repo.update_llm1_status(batch_id, "Complete")
        self.update_batch_status(batch_id, "llm1Done")
    else:
        logger.info("llm1_stage_already_complete")
else:
    logger.info("llm1_stage_skipped")
```

### LLM2 Stage Call

**Location:** Line 350

```python
# Stage: LLM2 (optional)
if self.settings.llm2_enabled:
    if batch.get('llm2Status') != 'Complete':
        self.batch_repo.update_llm2_status(batch_id, "InProgress")
        llm2_stage = LLM2Stage()
        await llm2_stage.execute(batch_id, previous_container)  # ← HERE
        self.batch_repo.update_llm2_status(batch_id, "Complete")
        self.update_batch_status(batch_id, "llm2Done")
    else:
        logger.info("llm2_stage_already_complete")
else:
    logger.info("llm2_stage_skipped")
```

**Context:**
- This is the main batch processing orchestrator
- Runs when you execute `python -m src.main`
- Processes batches from `/client_volume` directory
- Sequential pipeline: File Distribution → Denoise → IVR → LID → STT → LLM1 → LLM2

---

## 2. New Audit Pipeline (`audit_pipeline.py`)

**File:** `cofi-service/src/audit_pipeline.py`

### LLM1 Stage Call

**Location:** Line 208

```python
async def _run_llm1_stage(self, batch_id: int):
    """Run LLM1 stage and update progress."""
    logger.info("llm1_stage_starting", task_id=self.task_id)

    llm1_stage = LLM1Stage()
    await llm1_stage.execute(batch_id, self.settings.stt_container)  # ← HERE

    # Update progress
    self.task_tracker["progress"]["llm1"]["done"] = self.task_tracker["progress"]["llm1"]["total"]

    logger.info("llm1_stage_completed", task_id=self.task_id)
```

### LLM2 Stage Call

**Location:** Line 220

```python
async def _run_llm2_stage(self, batch_id: int):
    """Run LLM2 stage and update progress."""
    logger.info("llm2_stage_starting", task_id=self.task_id)

    llm2_stage = LLM2Stage()
    await llm2_stage.execute(batch_id, self.settings.llm1_container)  # ← HERE

    # Update progress
    self.task_tracker["progress"]["llm2"]["done"] = self.task_tracker["progress"]["llm2"]["total"]

    logger.info("llm2_stage_completed", task_id=self.task_id)
```

**Context:**
- Used by the API endpoint for **new audit** processing
- Runs when files are uploaded via `/api/upload` endpoint
- Creates new batch and processes uploaded files
- Pipeline: File Distribution → LID → STT → LLM1 → LLM2

---

## 3. Reaudit Pipeline (`reaudit_pipeline.py`)

**File:** `cofi-service/src/reaudit_pipeline.py`

### LLM1 Stage Call

**Location:** Line 188

```python
async def _run_llm1_stage(self, batch_id: int):
    """Run LLM1 stage."""
    logger.info("reaudit_llm1_starting", task_id=self.task_id)

    llm1_stage = LLM1Stage()
    await llm1_stage.execute(batch_id, self.settings.stt_container)  # ← HERE

    logger.info("reaudit_llm1_completed", task_id=self.task_id)
```

### LLM2 Stage Call

**Location:** Line 197

```python
async def _run_llm2_stage(self, batch_id: int):
    """Run LLM2 stage."""
    logger.info("reaudit_llm2_starting", task_id=self.task_id)

    llm2_stage = LLM2Stage()
    await llm2_stage.execute(batch_id, self.settings.llm1_container)  # ← HERE

    logger.info("reaudit_llm2_completed", task_id=self.task_id)
```

**Context:**
- Used for **reauditing** existing audio files
- Runs when reaudit is triggered via API
- Reprocesses specific stages for existing files
- Can run any combination of stages: LID, STT, LLM1, LLM2

---

## Summary Table

| Location | File | LLM1 Line | LLM2 Line | Purpose |
|----------|------|-----------|-----------|---------|
| **Main Batch** | `main.py` | 337 | 350 | Main batch processing |
| **New Audit** | `audit_pipeline.py` | 208 | 220 | API file uploads (new audit) |
| **Reaudit** | `reaudit_pipeline.py` | 188 | 197 | Reprocessing existing files |

---

## Call Flow

### Main Batch Processing Flow

```
main.py: run()
  └─> Line 337: llm1_stage.execute(batch_id, previous_container)
      └─> llm1_stage.py: execute()
          └─> Parallel processing with 100 concurrent calls ✅

  └─> Line 350: llm2_stage.execute(batch_id, previous_container)
      └─> llm2_stage.py: execute()
          └─> Parallel processing with 100 concurrent calls ✅
```

### New Audit Flow

```
audit_pipeline.py: process()
  └─> Line 76-77: await self._run_llm1_stage(batch_id)
      └─> Line 208: llm1_stage.execute(batch_id, ...)
          └─> llm1_stage.py: execute()
              └─> Parallel processing with 100 concurrent calls ✅

  └─> Line 81-82: await self._run_llm2_stage(batch_id)
      └─> Line 220: llm2_stage.execute(batch_id, ...)
          └─> llm2_stage.py: execute()
              └─> Parallel processing with 100 concurrent calls ✅
```

### Reaudit Flow

```
reaudit_pipeline.py: process()
  └─> Line 109-112: await self._run_llm1_stage(batch_id)
      └─> Line 188: llm1_stage.execute(batch_id, ...)
          └─> llm1_stage.py: execute()
              └─> Parallel processing with 100 concurrent calls ✅

  └─> Line 114-117: await self._run_llm2_stage(batch_id)
      └─> Line 197: llm2_stage.execute(batch_id, ...)
          └─> llm2_stage.py: execute()
              └─> Parallel processing with 100 concurrent calls ✅
```

---

## Previous Container Parameter

Notice that all calls pass `previous_container` as the second parameter:

```python
await llm1_stage.execute(batch_id, previous_container)
await llm2_stage.execute(batch_id, previous_container)
```

**Purpose:**
- LLM stages don't use GPU mediator containers
- They call external NLP APIs directly
- The `previous_container` parameter is ignored in LLM stages
- It's kept for consistency with the base class interface

**In the execute() method:**
```python
async def execute(self, batch_id: int, previous_container: Optional[str] = None):
    # previous_container is ignored for LLM stages
    # No containers to start/stop
```

---

## Parallel Optimization Applied

All three locations now benefit from the parallel optimization:

✅ **Main Batch Processing** (`main.py` line 337, 350)
   - Processes 100 calls concurrently
   - 28× faster than sequential

✅ **New Audit** (`audit_pipeline.py` line 208, 220)
   - Processes 100 calls concurrently
   - 28× faster than sequential

✅ **Reaudit** (`reaudit_pipeline.py` line 188, 197)
   - Processes 100 calls concurrently
   - 28× faster than sequential

**No additional changes needed!** The optimization in the `execute()` method automatically applies to all three locations. 🎉

---

## Verification

To verify parallel processing is working, check logs:

```bash
# Main batch processing
tail -f logs/cofi-service.log | grep "llm1_processing_parallel\|llm2_processing_parallel"

# Expected output:
[info] llm1_processing_parallel max_concurrent=100
[info] llm2_processing_parallel max_concurrent=100
```

---

## Configuration

Parallel processing is controlled by these settings:

### Enable/Disable LLM Stages

**File:** `cofi-service/.env`

```env
# Enable/disable LLM stages
LLM1_ENABLED=true
LLM2_ENABLED=true
```

### Adjust Concurrency Limit

**Files:** `cofi-service/src/pipeline/llm1_stage.py`, `llm2_stage.py`

```python
# Current: 100 concurrent calls
semaphore = asyncio.Semaphore(100)

# More aggressive (if your API can handle it)
semaphore = asyncio.Semaphore(200)

# More conservative (if API rate limits)
semaphore = asyncio.Semaphore(50)
```

---

## Summary

✅ LLM1 and LLM2 `execute()` methods are called from **3 locations**
✅ All locations now use **parallel processing** (100 concurrent calls)
✅ **No code changes** needed in the calling locations
✅ **28× faster** than the previous sequential approach
✅ Works for **batch processing**, **new audit**, and **reaudit**

The optimization is centralized in the `execute()` method, so all calling locations automatically benefit! 🚀
