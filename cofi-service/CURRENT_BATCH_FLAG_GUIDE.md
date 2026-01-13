# Current Batch Flag - Implementation Guide

## Overview

To ensure the dashboard always monitors the correct batch, you should set the `currentBatch` flag in the `batchStatus` table.

---

## The currentBatch Flag

**Field:** `currentBatch` tinyint(1)
- **Value 1** = This is the currently processing batch (active)
- **Value 0** = This batch is not active (historical)

**Rule:** Only **ONE** batch should have `currentBatch = 1` at any time.

---

## Implementation in cofi-service

### Step 1: Set currentBatch = 1 When Starting a New Batch

In `cofi-service/src/main.py`, when creating or resuming a batch:

```python
def get_or_create_batch(self) -> dict:
    """Get existing batch or create new one."""
    batch = self.batch_repo.get_by_date_and_number(
        self.settings.batch_date,
        self.settings.current_batch
    )

    if batch:
        logger.info("batch_found", batch_id=batch['id'])
        # IMPORTANT: Set this batch as current
        self.batch_repo.set_as_current_batch(batch['id'])
        return batch

    # Create new batch
    batch_id = self.batch_repo.create(
        self.settings.batch_date,
        self.settings.current_batch
    )
    logger.info("batch_created", batch_id=batch_id)

    # IMPORTANT: Set new batch as current
    self.batch_repo.set_as_current_batch(batch_id)

    return self.batch_repo.get_by_date_and_number(
        self.settings.batch_date,
        self.settings.current_batch
    )
```

### Step 2: Add Repository Method

In `cofi-service/src/database.py`, add to `BatchStatusRepo`:

```python
class BatchStatusRepo:
    """Repository for batchStatus table operations."""

    def __init__(self, db: Database):
        self.db = db

    # ... existing methods ...

    def set_as_current_batch(self, batch_id: int):
        """
        Set a batch as the current active batch.
        Sets currentBatch = 1 for this batch and 0 for all others.
        """
        # First, unset all other batches
        query = "UPDATE batchStatus SET currentBatch = 0"
        self.db.execute_update(query)

        # Then set this batch as current
        query = "UPDATE batchStatus SET currentBatch = 1 WHERE id = %s"
        self.db.execute_update(query, (batch_id,))

        logger.info("current_batch_flag_set", batch_id=batch_id)

    def unset_current_batch(self, batch_id: int):
        """
        Unset the currentBatch flag for a specific batch.
        Call this when batch processing completes.
        """
        query = "UPDATE batchStatus SET currentBatch = 0 WHERE id = %s"
        self.db.execute_update(query, (batch_id,))
        logger.info("current_batch_flag_unset", batch_id=batch_id)
```

### Step 3: Unset Flag When Batch Completes

In `cofi-service/src/main.py`, at the end of the pipeline:

```python
async def run(self):
    """Run the complete pipeline with resume support."""
    logger.info("cofi_service_starting", batch_date=self.settings.batch_date)

    # 1. Get or create batch (sets currentBatch = 1)
    batch = self.get_or_create_batch()
    batch_id = batch['id']

    try:
        # ... all pipeline stages ...

        # Mark batch complete
        self.update_batch_status(batch_id, "Completed")

        # IMPORTANT: Unset currentBatch flag
        self.batch_repo.unset_current_batch(batch_id)

        logger.info("pipeline_completed", batch_id=batch_id)

    except Exception as e:
        logger.error("pipeline_failed", batch_id=batch_id, error=str(e))
        # Keep currentBatch = 1 so user can see failed batch in dashboard
        raise
```

---

## Alternative: Update Existing Batches Manually

If you don't want to modify cofi-service code right now, you can manually set the flag:

### SQL Command:

```sql
-- Set batch #123 as current
UPDATE batchStatus SET currentBatch = 0;  -- Unset all first
UPDATE batchStatus SET currentBatch = 1 WHERE id = 123;
```

### Quick Script:

```bash
# Set the most recent batch as current
mysql -u root -p testDb -e "
    UPDATE batchStatus SET currentBatch = 0;
    UPDATE batchStatus SET currentBatch = 1
    WHERE id = (SELECT id FROM (SELECT id FROM batchStatus ORDER BY id DESC LIMIT 1) AS tmp);
"
```

---

## Dashboard Behavior

With the `currentBatch` flag properly set:

✅ **Dashboard automatically shows the active batch**
```
http://localhost:5066
```

✅ **Priority 1:** Looks for `currentBatch = 1` first
✅ **Priority 2:** Falls back to InProgress stages if flag not set
✅ **Priority 3:** Shows incomplete batches
✅ **Priority 4:** Shows most recent batch as last resort

---

## Best Practices

### ✅ DO:
- Set `currentBatch = 1` when starting a new batch
- Ensure only ONE batch has `currentBatch = 1`
- Unset flag when batch completes successfully
- Keep flag set (= 1) if batch fails (so you can debug via dashboard)

### ❌ DON'T:
- Have multiple batches with `currentBatch = 1`
- Forget to unset flag after completion
- Manually change the flag while processing is active

---

## Verification

Check which batch is marked as current:

```sql
-- See current batch
SELECT id, batchDate, currentBatch, batchStatus
FROM batchStatus
WHERE currentBatch = 1;

-- See all batches
SELECT id, batchDate, currentBatch, batchStatus
FROM batchStatus
ORDER BY id DESC
LIMIT 10;
```

---

## Troubleshooting

### Multiple batches have currentBatch = 1

**Fix:**
```sql
UPDATE batchStatus SET currentBatch = 0;
UPDATE batchStatus SET currentBatch = 1 WHERE id = <correct_batch_id>;
```

### Dashboard shows wrong batch

1. Check currentBatch flag: `SELECT * FROM batchStatus WHERE currentBatch = 1;`
2. If incorrect, manually update: `UPDATE batchStatus SET currentBatch = 1 WHERE id = XXX;`
3. Or add batch_id parameter: `http://localhost:5066?batch_id=XXX`

### No batch has currentBatch = 1

Dashboard will fall back to:
- InProgress stages (Priority 2)
- Incomplete batches (Priority 3)
- Most recent batch (Priority 4)

---

## Summary

The `currentBatch` flag is the **most reliable way** to tell the dashboard which batch to monitor.

**Implementation:**
1. Add `set_as_current_batch()` method to BatchStatusRepo
2. Call it in `get_or_create_batch()`
3. Call `unset_current_batch()` when pipeline completes

**This ensures perfect dashboard integration!** 🎯
