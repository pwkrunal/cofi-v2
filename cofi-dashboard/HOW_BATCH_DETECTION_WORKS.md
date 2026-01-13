# How Cofi Dashboard Detects the Current Batch

## Overview

The dashboard uses an **intelligent 4-tier priority system** to determine which batch to monitor, leveraging the `currentBatch` flag in your `batchStatus` table.

---

## Method 1: Automatic Detection (Default)

When you open the dashboard without any parameters:
```
http://localhost:5066
```

The dashboard automatically detects the current batch using this **priority logic**:

### Priority 1: Current Batch Flag ⭐⭐⭐ (Highest Priority)
```sql
SELECT * FROM batchStatus
WHERE currentBatch = 1
ORDER BY id DESC
LIMIT 1
```

**Explanation:** The `currentBatch` flag is the most reliable indicator. Your cofi-service should set this to `1` for the active batch and `0` for all others.

### Priority 2: In-Progress Batch ⭐⭐
```sql
SELECT * FROM batchStatus
WHERE dbInsertionStatus = 'InProgress'
   OR denoiseStatus = 'InProgress'
   OR ivrStatus = 'InProgress'
   OR lidStatus = 'InProgress'
   OR sttStatus = 'InProgress'
   OR llm1Status = 'InProgress'
   OR llm2Status = 'InProgress'
   OR triagingStatus = 'InProgress'
ORDER BY id DESC
LIMIT 1
```

**Explanation:** Finds any batch that has at least one stage currently processing.

### Priority 3: Non-Completed Batch ⭐
```sql
SELECT * FROM batchStatus
WHERE batchStatus != 'Complete'
ORDER BY id DESC
LIMIT 1
```

**Explanation:** If no stages are "InProgress", finds the most recent batch that hasn't finished yet.

### Priority 4: Most Recent Batch (Fallback)
```sql
SELECT * FROM batchStatus
ORDER BY id DESC
LIMIT 1
```

**Explanation:** If all batches are completed, shows the most recent one (useful for reviewing past runs).

---

## Method 2: Specific Batch ID (URL Parameter)

To monitor a **specific batch**, pass the batch ID as a URL parameter:

```
http://localhost:5066?batch_id=123
```

### Example Use Cases:

**Review a completed batch:**
```
http://localhost:5066?batch_id=42
```

**Monitor a specific batch when multiple batches exist:**
```
http://localhost:5066?batch_id=100
```

**Compare two batches (open in separate tabs):**
- Tab 1: `http://localhost:5066?batch_id=99`
- Tab 2: `http://localhost:5066?batch_id=100`

---

## Method 3: API Query

Programmatically get batch information via the API:

### Get current batch (automatic detection):
```bash
curl http://localhost:5066/api/current-batch
```

### Get specific batch:
```bash
curl http://localhost:5066/api/current-batch?batch_id=123
```

### Response example:
```json
{
  "batch_id": 123,
  "batch_date": "15-12-2024",
  "batch_number": 1,
  "status": "sttDone",
  "total_files": 50,
  "processed_files": 45,
  "stages": {
    "file_distribution": {
      "status": "Complete",
      "total": 50,
      "processed": 50,
      "errors": 0
    },
    "lid": {
      "status": "Complete",
      "total": 50,
      "processed": 50,
      "errors": 0
    },
    "stt": {
      "status": "InProgress",
      "total": 50,
      "processed": 30,
      "errors": 2
    },
    ...
  }
}
```

---

## How It Works in Practice

### Scenario 1: Single Active Batch (Most Common)
```
Dashboard opens → Checks for InProgress stages → Finds Batch #123 → Monitors Batch #123
```

### Scenario 2: Multiple Historical Batches
```
Dashboard opens → No InProgress batches → Finds most recent incomplete → Batch #125
```

### Scenario 3: All Batches Completed
```
Dashboard opens → No active batches → Shows latest completed → Batch #130
```

### Scenario 4: Specific Batch Requested
```
User opens ?batch_id=100 → Skips automatic detection → Directly monitors Batch #100
```

---

## Batch Status Tracking

The dashboard monitors these status fields in `batchStatus` table:

| Field | Type | Values | Meaning |
|-------|------|--------|---------|
| **`currentBatch`** | tinyint(1) | 0, 1 | **⭐ Primary indicator** - 1 = active batch, 0 = inactive |
| `batchStatus` | ENUM | Pending, InProgress, Complete | Overall batch progress |
| `dbInsertionStatus` | ENUM | Pending, InProgress, Complete | File distribution stage |
| `denoiseStatus` | ENUM | Pending, InProgress, Complete | Denoise stage |
| `ivrStatus` | ENUM | Pending, InProgress, Complete | IVR stage |
| `lidStatus` | ENUM | Pending, InProgress, Complete | LID stage |
| `triagingStatus` | ENUM | Pending, InProgress, Complete | Rule Engine Step 1 |
| `triagingStep2Status` | ENUM | Pending, InProgress, Complete | Rule Engine Step 2 |
| `sttStatus` | ENUM | Pending, InProgress, Complete | STT stage |
| `llm1Status` | ENUM | Pending, InProgress, Complete | LLM1 stage |
| `llm2Status` | ENUM | Pending, InProgress, Complete | LLM2 stage |
| `callmetadataStatus` | tinyint(1) | 0, 1 | Call metadata processed (1 = yes) |
| `trademetadataStatus` | tinyint(1) | 0, 1 | Trade metadata processed (1 = yes) |

### Timing Fields (per stage):
Each stage has `{stage}StartTime` and `{stage}EndTime` varchar(100) fields for duration tracking.

**Detection Logic:**
1. **Best:** `currentBatch = 1` (most reliable)
2. **Good:** Any stage status = 'InProgress'
3. **Fallback:** `batchStatus != 'Complete'`
4. **Last Resort:** Most recent batch by ID

---

## Real-Time Event Streaming

Once the batch is determined, the SSE (Server-Sent Events) connection streams events for that specific batch:

```javascript
// Frontend connects to SSE
const eventSource = new EventSource('/api/stream?batch_id=123');

// Backend streams events
SELECT * FROM batchExecutionLog
WHERE batchId = 123 AND id > {last_event_id}
ORDER BY id ASC
LIMIT 50
```

The dashboard polls for new events **every 2 seconds**.

---

## Implementation Details

### Backend Logic (Python)

**File:** `cofi-dashboard/src/database.py`

```python
def get_current_batch(self) -> Optional[Dict]:
    """Priority-based batch detection."""

    # Priority 1: Any InProgress stage
    query = """
        SELECT * FROM batchStatus
        WHERE dbInsertionStatus = 'InProgress'
           OR denoiseStatus = 'InProgress'
           ... (all other stages)
        ORDER BY id DESC
        LIMIT 1
    """
    batch = self.db.execute_one(query)
    if batch:
        return batch

    # Priority 2: Non-completed batch
    query = """
        SELECT * FROM batchStatus
        WHERE status != 'Completed'
        ORDER BY id DESC
        LIMIT 1
    """
    batch = self.db.execute_one(query)
    if batch:
        return batch

    # Priority 3: Most recent batch
    query = """
        SELECT * FROM batchStatus
        ORDER BY id DESC
        LIMIT 1
    """
    return self.db.execute_one(query)
```

### Frontend Logic (JavaScript)

**File:** `cofi-dashboard/src/static/app.js`

```javascript
// Check URL for batch_id parameter
function getBatchIdFromUrl() {
    const params = new URLSearchParams(window.location.search);
    return params.get('batch_id');
}

// Load batch data
async function loadCurrentBatch() {
    const batchId = getBatchIdFromUrl();
    const url = batchId
        ? `/api/current-batch?batch_id=${batchId}`
        : '/api/current-batch';

    const response = await fetch(url);
    const data = await response.json();
    // ... update UI
}

// Connect to SSE stream
async function connectSSE() {
    const batchId = getBatchIdFromUrl();
    const sseUrl = batchId
        ? `/api/stream?batch_id=${batchId}`
        : '/api/stream';

    const eventSource = new EventSource(sseUrl);
    // ... handle events
}
```

---

## Troubleshooting

### Dashboard shows wrong batch

**Cause:** Multiple batches with InProgress status

**Solution:**
1. Check database: `SELECT * FROM batchStatus WHERE status != 'Completed';`
2. Manually specify batch: `http://localhost:5066?batch_id=XXX`
3. Clean up old batches: Update completed batches to have all stages as 'Complete'

### Dashboard shows "No active batch found"

**Cause:** No batches in database

**Solution:**
1. Verify batchStatus table has records: `SELECT COUNT(*) FROM batchStatus;`
2. Start cofi-service batch processing to create a batch
3. Check that batch creation is working in main.py

### Events not updating for current batch

**Cause:** SSE connected to wrong batch

**Solution:**
1. Check browser DevTools → Network tab → SSE connection
2. Verify batch_id in SSE request matches expected batch
3. Check batchExecutionLog for events: `SELECT * FROM batchExecutionLog WHERE batchId = XXX;`

---

## Best Practices

### For Single Batch Processing (Current Use Case)
✅ **Just open the dashboard** - automatic detection works perfectly
```
http://localhost:5066
```

### For Multiple Concurrent Batches (Future)
✅ **Use batch_id parameter** to monitor specific batches
```
http://localhost:5066?batch_id=123
```

### For Historical Review
✅ **Pass completed batch ID**
```
http://localhost:5066?batch_id=100
```

### For Monitoring Multiple Batches Simultaneously
✅ **Open multiple browser tabs with different batch_ids**
```
Tab 1: http://localhost:5066?batch_id=123
Tab 2: http://localhost:5066?batch_id=124
Tab 3: http://localhost:5066?batch_id=125
```

---

## Summary

**How Dashboard Detects Current Batch:**

1. **Automatic (Default):**
   - Looks for batches with InProgress stages
   - Falls back to incomplete batches
   - Shows most recent if all completed

2. **Manual (URL Parameter):**
   - `?batch_id=XXX` to monitor specific batch
   - Useful for historical review or multiple batches

3. **Priority Order:**
   - InProgress > Incomplete > Most Recent

**This intelligent system ensures you're always monitoring the right batch!** 🎯
