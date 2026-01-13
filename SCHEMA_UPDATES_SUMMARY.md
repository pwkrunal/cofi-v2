# Dashboard Updates Based on Actual Schema

## Changes Made

I've updated the cofi-dashboard to match your **actual batchStatus schema**, which includes the very useful `currentBatch` flag!

---

## What Was Updated

### 1. Batch Detection Logic ✅

**Updated File:** `cofi-dashboard/src/database.py`

**New Priority System (4 tiers):**
```python
Priority 1: currentBatch = 1         # ⭐⭐⭐ Most reliable
Priority 2: Any stage = InProgress   # ⭐⭐ Good fallback
Priority 3: batchStatus != Complete  # ⭐ Incomplete batches
Priority 4: Most recent batch        # Fallback
```

**Key Change:**
```python
# Priority 1: Check currentBatch flag
query = "SELECT * FROM batchStatus WHERE currentBatch = 1"
```

### 2. API Response Format ✅

**Updated File:** `cofi-dashboard/src/app.py`

**Changes:**
- Fixed field name: `status` → `batchStatus`
- Removed: `batchNumber` (doesn't exist in your schema)
- Added: `current_batch` boolean flag
- Added: Timing fields (`start_time`, `end_time` per stage)
- Fixed: `callmetadataStatus` and `trademetadataStatus` as boolean (0/1)

**New Response:**
```json
{
  "batch_id": 123,
  "batch_date": "15-12-2024",
  "current_batch": true,
  "status": "InProgress",
  "batch_start_time": "2024-12-15 10:00:00",
  "batch_end_time": null,
  "stages": {
    "lid": {
      "status": "Complete",
      "start_time": "2024-12-15 10:05:00",
      "end_time": "2024-12-15 10:15:00",
      "total": 50,
      "processed": 50,
      "errors": 0
    },
    ...
  }
}
```

### 3. Frontend Display ✅

**Updated File:** `cofi-dashboard/src/static/index.html`

**Changes:**
- Replaced "Batch Number" with "Batch ID"
- Added "Is Current" badge (shows Yes/No)

**Updated File:** `cofi-dashboard/src/static/app.js`

**Changes:**
- Updated to use `batch_id` instead of `batch_number`
- Added display for `current_batch` flag with color-coded badge

### 4. Documentation ✅

**Updated File:** `cofi-dashboard/HOW_BATCH_DETECTION_WORKS.md`

**Changes:**
- Added Priority 1: currentBatch flag
- Updated field names to match actual schema
- Added timing field documentation

**New File:** `cofi-service/CURRENT_BATCH_FLAG_GUIDE.md`

Complete guide on how to set the `currentBatch` flag in cofi-service.

---

## Your Schema vs Original Assumptions

| Feature | Original Assumption | Actual Schema | Status |
|---------|---------------------|---------------|--------|
| Overall status | `status` | `batchStatus` | ✅ Fixed |
| Batch identifier | `batchNumber` | Only `batchDate` | ✅ Fixed |
| Current batch flag | ❌ Not assumed | ✅ `currentBatch` tinyint(1) | ✅ Implemented |
| Metadata status | ENUM | tinyint(1) 0/1 | ✅ Fixed |
| Timing tracking | ❌ Not tracked | ✅ Start/End times per stage | ✅ Added to API |
| TriagingStep2 | ❌ Not included | ✅ `triagingStep2Status` | ✅ Added |

---

## How to Use the currentBatch Flag

### Option 1: Automatic (Recommended)

Implement in `cofi-service/src/database.py`:

```python
def set_as_current_batch(self, batch_id: int):
    """Set batch as current (only one at a time)."""
    # Unset all first
    self.db.execute_update("UPDATE batchStatus SET currentBatch = 0")
    # Set this batch as current
    self.db.execute_update("UPDATE batchStatus SET currentBatch = 1 WHERE id = %s", (batch_id,))
```

Call when starting a batch:
```python
batch = self.get_or_create_batch()
self.batch_repo.set_as_current_batch(batch['id'])
```

### Option 2: Manual SQL

For immediate testing without code changes:

```sql
-- Set batch #123 as current
UPDATE batchStatus SET currentBatch = 0;  -- Unset all
UPDATE batchStatus SET currentBatch = 1 WHERE id = 123;  -- Set current
```

---

## Testing the Dashboard

### Test 1: With currentBatch Flag Set

```sql
-- Set most recent batch as current
UPDATE batchStatus SET currentBatch = 1 WHERE id = (SELECT MAX(id) FROM batchStatus);
```

Open dashboard:
```
http://localhost:5066
```

✅ Should show the batch you marked with `currentBatch = 1`

### Test 2: Without currentBatch Flag

```sql
-- Unset all currentBatch flags
UPDATE batchStatus SET currentBatch = 0;
```

Dashboard will fall back to:
- InProgress stages (if any)
- Incomplete batches
- Most recent batch

### Test 3: Specific Batch

```
http://localhost:5066?batch_id=123
```

✅ Shows batch #123 regardless of flags

---

## Benefits of currentBatch Flag

### ✅ Advantages:

1. **Instant Detection** - No need to check stage statuses
2. **Explicit Control** - You decide which batch is current
3. **Reliable** - Works even if stages haven't started yet
4. **Simple** - Single field, boolean logic
5. **Fast Queries** - Direct index lookup

### 🎯 Perfect For:

- Single active batch at a time (your use case)
- Resuming interrupted batches
- Testing/debugging specific batches
- Historical batch review

---

## Migration Checklist

To fully leverage the `currentBatch` flag:

### Phase 1: Dashboard (✅ Already Done)
- [x] Update query logic to check `currentBatch = 1` first
- [x] Fix field name mappings (`status` → `batchStatus`)
- [x] Remove `batchNumber` references
- [x] Add timing field support
- [x] Update documentation

### Phase 2: Cofi Service (📝 TODO)
- [ ] Add `set_as_current_batch()` to BatchStatusRepo
- [ ] Call it in `get_or_create_batch()`
- [ ] Call `unset_current_batch()` when complete
- [ ] Test with manual SQL first (quick validation)

### Phase 3: Validation (📝 TODO)
- [ ] Run batch processing
- [ ] Verify dashboard shows correct batch
- [ ] Test batch completion (flag unset)
- [ ] Test new batch start (flag set)

---

## Quick Start (No Code Changes Required)

You can test the dashboard immediately without modifying cofi-service:

### Step 1: Manually Set Flag
```sql
-- Find your latest batch
SELECT id, batchDate, batchStatus FROM batchStatus ORDER BY id DESC LIMIT 5;

-- Set it as current (replace 123 with your batch ID)
UPDATE batchStatus SET currentBatch = 0;
UPDATE batchStatus SET currentBatch = 1 WHERE id = 123;
```

### Step 2: Start Dashboard
```bash
cd cofi-dashboard
python -m uvicorn src.app:app --host 0.0.0.0 --port 5066
```

### Step 3: Open Browser
```
http://localhost:5066
```

✅ Dashboard should show your batch with "Is Current: Yes" badge!

---

## Summary

**What Changed:**
- Dashboard now uses `currentBatch` flag as primary detection method
- Fixed all field name mismatches
- Added timing information support
- Improved batch detection priority system

**What's Perfect:**
- Your schema with `currentBatch` flag is ideal for this use case
- Dashboard works immediately (just set the flag manually)
- Full backward compatibility (falls back to other detection methods)

**Next Step:**
- Test with manual SQL flag setting
- Optionally add flag management to cofi-service
- Enjoy real-time monitoring! 🎉

---

## Files Modified

1. ✅ `cofi-dashboard/src/database.py` - Added currentBatch priority
2. ✅ `cofi-dashboard/src/app.py` - Fixed field names, added timing
3. ✅ `cofi-dashboard/src/static/index.html` - Updated header display
4. ✅ `cofi-dashboard/src/static/app.js` - Updated batch info rendering
5. ✅ `cofi-dashboard/HOW_BATCH_DETECTION_WORKS.md` - Updated docs
6. ✅ `cofi-service/CURRENT_BATCH_FLAG_GUIDE.md` - New implementation guide
7. ✅ `SCHEMA_UPDATES_SUMMARY.md` - This file

**Dashboard is ready to use with your actual schema!** 🚀
