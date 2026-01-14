# Parallel Processing Status Check

## Current Status

| Stage | Processing Method | Status | Performance |
|-------|-------------------|--------|-------------|
| **File Distribution** | ✅ Parallel | **OPTIMIZED** | All GPUs simultaneously |
| **Denoise** | ✅ Parallel | **ALREADY GOOD** | `mediator.process_files_parallel()` |
| **IVR** | ✅ Parallel | **ALREADY GOOD** | `mediator.process_files_parallel()` |
| **LID** | ✅ Parallel | **ALREADY GOOD** | `mediator.process_files_parallel()` |
| **STT** | ✅ Parallel | **ALREADY GOOD** | `mediator.process_files_parallel()` |
| **LLM1** | ❌ Sequential | **NEEDS FIX** | One call at a time (SLOW!) |
| **LLM2** | ❌ Sequential | **NEEDS FIX** | One call at a time (SLOW!) |

---

## Details

### ✅ Parallel Stages (Good!)

#### File Distribution
**Location:** `cofi-service/src/main.py` - `distribute_files()`

```python
# Create tasks for all files
upload_tasks = []
for gpu_ip, file_paths in distribution.items():
    for file_path in file_paths:
        upload_tasks.append(upload_and_record(gpu_ip, file_path))

# Execute ALL uploads in parallel
await asyncio.gather(*upload_tasks)
```

**Performance:** 5× to 10× faster than sequential

#### Denoise / IVR / LID / STT Stages
**Location:** `cofi-service/src/pipeline/base.py` - `execute()`

```python
# Line 109: Process all files in parallel
results = await self.mediator.process_files_parallel(
    file_gpu_mapping,
    self.api_endpoint,
    self.build_payload
)
```

**Implementation in mediator_client.py:**
```python
def process_files_parallel(...):
    all_tasks = []
    for gpu_ip, files in file_gpu_mapping.items():
        for file_name in files:
            task = self.call_processing_api(gpu_ip, endpoint, payload)
            all_tasks.append(task)

    # Execute ALL API calls in parallel
    results = await asyncio.gather(*all_tasks, return_exceptions=True)
```

**Performance:** All GPUs process files simultaneously ✅

---

### ❌ Sequential Stages (Needs Optimization!)

#### LLM1 Stage (SLOW!)
**Location:** `cofi-service/src/pipeline/llm1_stage.py` - `execute()`

```python
# Line 307-328: Sequential loop (SLOW!)
for call_record in call_records:
    try:
        payload = self.build_payload(call_record)
        response = await self.call_nlp_api(payload)  # WAIT for each call
        self.process_response(call_record, response)
        successful += 1
    except Exception as e:
        failed += 1
```

**Problem:**
- Processes one call at a time
- Even though it's async, the `for` loop makes it sequential
- For 10,000 calls × 5 seconds each = 13.9 hours! 🐌

**Example timeline:**
```
0s   ─────[Call 1]─────> 5s
5s   ─────[Call 2]─────> 10s
10s  ─────[Call 3]─────> 15s
...
49995s ─────[Call 10000]─────> 50000s

Total: 13.9 hours for 10,000 calls
```

#### LLM2 Stage (SLOW!)
**Location:** `cofi-service/src/pipeline/llm2_stage.py` - `execute()`

```python
# Line 448-472: Sequential loop (SLOW!)
for call_record in call_records:
    try:
        await self.process_call(call_record)  # WAIT for each call
        self.call_repo.update_status(...)
        successful += 1
    except Exception as e:
        failed += 1
```

**Same problem as LLM1:**
- One call at a time
- For 10,000 calls × 10 seconds each = 27.8 hours! 🐌

---

## Performance Impact

### Current (Sequential LLM1 + LLM2)

For a batch of 10,000 files:

```
File Distribution: 1.1 hours (parallel) ✅
Denoise:          1.1 hours (parallel) ✅
IVR:              1.1 hours (parallel) ✅
LID:              1.1 hours (parallel) ✅
STT:              1.1 hours (parallel) ✅
LLM1:             13.9 hours (sequential) ❌
LLM2:             27.8 hours (sequential) ❌

Total: ~48 hours (2 days!)
```

### After Optimization (Parallel LLM1 + LLM2)

```
File Distribution: 1.1 hours (parallel) ✅
Denoise:          1.1 hours (parallel) ✅
IVR:              1.1 hours (parallel) ✅
LID:              1.1 hours (parallel) ✅
STT:              1.1 hours (parallel) ✅
LLM1:             0.5 hours (parallel, 100 concurrent) ⚡
LLM2:             1.0 hours (parallel, 100 concurrent) ⚡

Total: ~8 hours (6× faster!)
```

**Potential speedup: 48 hours → 8 hours (40 hours saved!)** 🚀

---

## Why LLM Stages Are Different

### Other Stages (Denoise, IVR, LID, STT)
- Call APIs via **GPU mediator** on GPU machines
- Each GPU has local processing power
- Naturally parallel across multiple GPUs
- Already optimized ✅

### LLM Stages (LLM1, LLM2)
- Call **external NLP API** directly (not via mediator)
- Single external service endpoint
- Need concurrency limiting to avoid overwhelming the API
- Currently sequential ❌

---

## Recommended Fix

### For LLM1 and LLM2 Stages

Add parallel processing with concurrency limit:

```python
async def execute(self, batch_id: int, previous_container: Optional[str] = None):
    call_records = self.call_repo.get_by_status(batch_id, "TranscriptDone")

    # Semaphore to limit concurrent API calls
    semaphore = asyncio.Semaphore(100)  # Max 100 concurrent calls

    async def process_with_limit(call_record):
        async with semaphore:
            # Process one call
            payload = self.build_payload(call_record)
            response = await self.call_nlp_api(payload)
            self.process_response(call_record, response)
            return True

    # Create tasks for all calls
    tasks = [process_with_limit(record) for record in call_records]

    # Execute all in parallel (with limit)
    results = await asyncio.gather(*tasks, return_exceptions=True)
```

**Benefits:**
- Up to 100 calls process simultaneously
- Much faster than sequential
- Won't overwhelm the external API
- Still handles errors gracefully

---

## Summary

✅ **Already Parallel (Good!):**
- File Distribution (just optimized)
- Denoise, IVR, LID, STT stages

❌ **Sequential (Needs Fix):**
- LLM1 stage
- LLM2 stage

**Optimization potential:**
- Current total time: ~48 hours
- Optimized total time: ~8 hours
- **Saves 40 hours per batch!** 🚀
