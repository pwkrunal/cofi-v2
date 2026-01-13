# Real-Time Progress Tracking - Complete Guide

## How Dashboard Knows "100 out of 500 files processed"

---

## 📊 The Complete Flow

### Step 1: Stage Starts
```python
# In pipeline/base.py
EventLogger.stage_start(batch_id, 'denoise', total_files=500)
```
**Database Record:**
```sql
INSERT INTO batchExecutionLog (
    batchId, stage, eventType, totalFiles
) VALUES (
    123, 'denoise', 'stage_start', 500
);
```

**Dashboard Receives (via SSE):**
```json
{
  "event": "stage_start",
  "data": {
    "stage": "denoise",
    "totalFiles": 500
  }
}
```

**UI Updates:**
```
Denoise Card:
  Total: 500
  Processed: 0
  Progress: 0%
```

---

### Step 2: Files Process (One by One)

**For Each File Completed:**
```python
EventLogger.file_complete(batch_id, 'denoise', 'audio001.wav', gpu_ip, response)
```

**Database Record:**
```sql
INSERT INTO batchExecutionLog (
    batchId, stage, eventType, fileName, response
) VALUES (
    123, 'denoise', 'file_complete', 'audio001.wav', '{"status":"success"}'
);
```

**Dashboard Receives (SSE stream):**
```json
{
  "event": "file_complete",
  "data": {
    "stage": "denoise",
    "fileName": "audio001.wav",
    "status": "success"
  }
}
```

**Frontend Updates:**
```javascript
// In app.js
case 'file_complete':
    state.stages['denoise'].processed++;  // 0 → 1 → 2 → 3 ... → 100
    updateStageCard('denoise');
    break;
```

**UI Updates (After 100 Files):**
```
Denoise Card:
  Total: 500
  Processed: 100  ✅ (incremented with each file_complete)
  Progress: 20%   ✅ (calculated: 100/500 * 100)

  Progress Bar: [████░░░░░░░░░░░░░░░░░░] 20%
```

---

### Step 3: Periodic Progress Updates (NEW!)

**Every 10 Files:**
```python
EventLogger.stage_progress(batch_id, 'denoise', processed_files=100, total_files=500)
```

**Database Record:**
```sql
INSERT INTO batchExecutionLog (
    batchId, stage, eventType, processedFiles, totalFiles
) VALUES (
    123, 'denoise', 'stage_progress', 100, 500
);
```

**Dashboard Receives:**
```json
{
  "event": "stage_progress",
  "data": {
    "stage": "denoise",
    "processedFiles": 100,
    "totalFiles": 500
  }
}
```

**Frontend Updates:**
```javascript
case 'stage_progress':
    state.stages['denoise'].processed = event.processedFiles;  // Bulk update
    break;
```

**Purpose:** Provides a checkpoint in case client missed some file_complete events

---

### Step 4: Stage Completes

```python
EventLogger.stage_complete(batch_id, 'denoise', processed_files=495, failed_files=5)
```

**Database Record:**
```sql
INSERT INTO batchExecutionLog (
    batchId, stage, eventType, processedFiles
) VALUES (
    123, 'denoise', 'stage_complete', 495
);
```

**UI Updates:**
```
Denoise Card:
  Total: 500
  Processed: 495  ✅ (final count)
  Errors: 5       ✅
  Status: Complete ✅

  Progress Bar: [███████████████████████░] 99%
```

---

## 🔄 Two Tracking Methods

### Method 1: File-by-File Tracking (Primary)
**How it works:**
1. Each `file_complete` event increments counter
2. Real-time updates as files finish
3. Granular progress (1, 2, 3, 4... 100)

**Advantages:**
- ✅ Real-time file-level visibility
- ✅ Click events to see individual file payloads
- ✅ Detailed error tracking per file

**When to use:**
- Default for all stages
- Best for small-to-medium batches (< 1000 files)

### Method 2: Bulk Progress Updates (Supplementary)
**How it works:**
1. `stage_progress` event every N files (e.g., every 10)
2. Provides checkpoints: 10, 20, 30... 100
3. Final count in `stage_complete` event

**Advantages:**
- ✅ Reduces event volume for large batches
- ✅ Provides recovery checkpoints
- ✅ Shows intermediate state

**When to use:**
- Large batches (> 1000 files)
- Network reliability concerns
- Checkpoint-based monitoring

---

## 📈 Progress Calculation

### Formula:
```javascript
const progressPercent = (processed / total) * 100;
```

### Example (100 out of 500):
```javascript
state.stages['denoise'].total = 500;       // From stage_start
state.stages['denoise'].processed = 100;   // From file_complete events
const progress = (100 / 500) * 100;        // = 20%
```

### Progress Bar Width:
```javascript
progressFill.style.width = `${progress}%`;  // 20%
```

### Display Text:
```javascript
progressText.textContent = `${processed}/${total} files`;  // "100/500 files"
```

---

## 🔍 Debugging Progress Tracking

### Check Database Events

**Query 1: Get all denoise events**
```sql
SELECT id, eventType, fileName, totalFiles, processedFiles, timestamp
FROM batchExecutionLog
WHERE batchId = 123 AND stage = 'denoise'
ORDER BY id ASC;
```

**Expected Output:**
```
| id  | eventType      | fileName      | totalFiles | processedFiles | timestamp           |
|-----|----------------|---------------|------------|----------------|---------------------|
| 1   | stage_start    | NULL          | 500        | NULL           | 2024-01-13 10:00:00 |
| 2   | file_complete  | audio001.wav  | NULL       | NULL           | 2024-01-13 10:00:01 |
| 3   | file_complete  | audio002.wav  | NULL       | NULL           | 2024-01-13 10:00:02 |
| ... | ...            | ...           | ...        | ...            | ...                 |
| 12  | stage_progress | NULL          | 500        | 10             | 2024-01-13 10:00:10 |
| ... | ...            | ...           | ...        | ...            | ...                 |
| 102 | file_complete  | audio100.wav  | NULL       | NULL           | 2024-01-13 10:01:40 |
| 103 | stage_progress | NULL          | 500        | 100            | 2024-01-13 10:01:40 |
```

**Query 2: Count completed files**
```sql
SELECT COUNT(*) as files_completed
FROM batchExecutionLog
WHERE batchId = 123
  AND stage = 'denoise'
  AND eventType = 'file_complete';
```

**Query 3: Get latest progress**
```sql
SELECT MAX(processedFiles) as current_progress
FROM batchExecutionLog
WHERE batchId = 123
  AND stage = 'denoise'
  AND eventType IN ('stage_progress', 'stage_complete');
```

### Check Dashboard State

**Browser Console:**
```javascript
// Check current state
console.log(state.stages.denoise);

// Output:
{
  total: 500,
  processed: 100,
  errors: 5,
  status: 'processing'
}
```

**Network Tab:**
Look for SSE connection:
```
GET /api/stream
Status: 200 (pending)
Type: text/event-stream

Messages received:
- stage_start
- file_complete (×100)
- stage_progress (×10)
```

---

## 🎯 Real-World Example

### Scenario: Denoise 500 audio files

**Timeline:**

| Time | Event | Database | Dashboard Display |
|------|-------|----------|-------------------|
| 10:00:00 | Stage starts | `stage_start` inserted | Total: 500, Processed: 0 |
| 10:00:01 | File 1 done | `file_complete` | Total: 500, Processed: 1 |
| 10:00:02 | File 2 done | `file_complete` | Total: 500, Processed: 2 |
| ... | ... | ... | ... |
| 10:00:10 | 10 files done | `stage_progress` (checkpoint) | Total: 500, Processed: 10 |
| ... | ... | ... | ... |
| 10:01:40 | 100 files done | `stage_progress` (checkpoint) | Total: 500, Processed: 100 ✅ |
| ... | ... | ... | ... |
| 10:08:20 | 500 files done | `stage_complete` | Total: 500, Processed: 500, Complete! |

**What You See in Dashboard:**
```
At 10:01:40 (100 files processed):

┌─────────────────────────────────────────┐
│ 🔇 Denoise            [Processing] ⏳   │
├─────────────────────────────────────────┤
│ [████████░░░░░░░░░░░░░░░░░░] 20%       │
│ 100/500 files                           │
├─────────────────────────────────────────┤
│ Total: 500 | Processed: 100 | Errors: 5│
├─────────────────────────────────────────┤
│ Recent Events:                          │
│ [10:01:40] 📄 audio100.wav: ✅ Complete│
│ [10:01:39] 📄 audio099.wav: ✅ Complete│
│ [10:01:38] 📄 audio098.wav: ✅ Complete│
│ [10:01:37] 📄 audio097.wav: ✅ Complete│
│ [10:01:36] ❌ audio096.wav: Error      │
└─────────────────────────────────────────┘
```

---

## ⚙️ Configuration Options

### Adjust Progress Update Interval

**File:** `cofi-service/src/pipeline/base.py`

```python
# Line ~106
progress_interval = 10  # Change from 10 to your preference

# Options:
# - 1: Update after every file (most real-time, more DB writes)
# - 10: Update every 10 files (balanced)
# - 50: Update every 50 files (less frequent)
# - 100: Update every 100 files (minimal updates)
```

**Recommendation:**
- Small batches (< 100 files): `progress_interval = 5`
- Medium batches (100-1000 files): `progress_interval = 10`
- Large batches (> 1000 files): `progress_interval = 50`

---

## 🚨 Troubleshooting

### Problem: Dashboard shows 0/500 but files are processing

**Cause:** SSE connection not established or events not being logged

**Solution:**
1. Check browser console for SSE connection
2. Verify events in database:
   ```sql
   SELECT COUNT(*) FROM batchExecutionLog WHERE batchId = 123;
   ```
3. Restart dashboard if SSE disconnected

### Problem: Progress stuck at old number (e.g., 50/500)

**Cause:** SSE connection dropped

**Solution:**
- Refresh browser page (SSE auto-reconnects every 5 seconds)
- Check dashboard logs for "sse_client_disconnected"

### Problem: Progress jumps (e.g., 10 → 50 → 100)

**Cause:** Missed intermediate file_complete events (normal behavior)

**Explanation:** stage_progress events provide checkpoints every N files, so you might see jumps instead of continuous increments.

**This is expected and correct!**

---

## 📊 Performance Considerations

### Database Load

**Current Implementation:**
- 1 `stage_start` event
- 500 `file_complete` events (one per file)
- 50 `stage_progress` events (every 10 files)
- 1 `stage_complete` event

**Total: ~552 INSERT operations per stage**

**Optimization:**
- Progress updates every 10 files reduces checkpoint spam
- Individual file events still logged for detailed tracking
- SSE polling every 2 seconds (minimal DB load)

### Browser Memory

**Event Storage:**
- Frontend keeps last 20 events per stage (configurable)
- Older events automatically removed
- Full event history in database

---

## ✅ Summary

**How Dashboard Knows Progress:**

1. **Stage Starts** → Total files set (e.g., 500)
2. **Files Complete** → Counter increments (1, 2, 3... 100)
3. **Periodic Checkpoints** → Bulk updates (10, 20, 30... 100)
4. **Stage Completes** → Final count confirmed (495 success, 5 errors)

**What You See:**
```
"100 out of 500 files processed" = 20% progress bar
```

**How It's Calculated:**
- **Total**: From `stage_start` event's `totalFiles` field
- **Processed**: Count of `file_complete` events OR latest `processedFiles` from `stage_progress`
- **Percentage**: (processed / total) × 100

**Update Frequency:**
- **Real-time**: Every file completion (~1-2 seconds per file)
- **Checkpoints**: Every 10 files
- **SSE Polling**: Every 2 seconds

**This gives you complete real-time visibility into every stage!** 🎯
