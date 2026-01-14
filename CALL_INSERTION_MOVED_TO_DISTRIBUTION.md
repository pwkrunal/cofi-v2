# Call Record Insertion Moved to File Distribution Stage

## Overview

Call records are now created during the **file distribution stage** instead of after LID completion. This provides better tracking of which files have been successfully distributed, especially important for large batches (10,000+ files).

---

## What Changed

### Previous Flow

```
1. File Distribution
   └─ Files uploaded to GPU machines
   └─ fileDistribution records created

2. LID Stage
   └─ Language identification runs
   └─ lidStatus records created

3. insert_calls_from_lid()
   └─ call records created with full info
```

### New Flow

```
1. File Distribution
   └─ Files uploaded to GPU machines
   └─ fileDistribution records created
   └─ call records created ✅ (with placeholder language data)

2. LID Stage
   └─ Language identification runs
   └─ lidStatus records created

3. update_calls_from_lid()
   └─ call records updated ✅ (with actual language data)
```

---

## Benefits

### 1. **Better Tracking**
- ✅ Can query `call` table to see which files were distributed
- ✅ If distribution fails at file 5,000/10,000, you can see exactly which files made it
- ✅ Call records exist from the start of processing

### 2. **Early Status Tracking**
- ✅ All distributed files have `status='Pending'` immediately
- ✅ Pipeline stages can query pending calls right away
- ✅ Better visibility into batch progress

### 3. **Resilience**
- ✅ If LID fails, call records still exist
- ✅ Can retry LID stage without losing distribution data
- ✅ Easier debugging and recovery

---

## Database Changes

### New Method: `CallRepo.insert_from_distribution()`

Creates call record during file distribution with placeholder values:

```python
def insert_from_distribution(
    audio_name: str,
    batch_id: int,
    ip: str,
    process_id: int,
    category_mapping_id: int,
    audio_endpoint: str,
    audit_form_id: Optional[int]
) -> int
```

**Initial Values:**
- `audioDuration`: `0` (updated after LID)
- `lang`: `'unknown'` (updated after LID)
- `languageId`: `NULL` (updated after LID)
- `status`: `'Pending'`
- `userId`: `1` (default)
- `audioUrl`: Built from `audio_endpoint + audio_name`
- `type`: `'Call'`

### New Method: `CallRepo.update_lid_info()`

Updates call record with LID results:

```python
def update_lid_info(
    audio_name: str,
    batch_id: int,
    language_id: Optional[int],
    lang_code: str,
    audio_duration: float
)
```

**Updates:**
- `languageId`: Set from LID results
- `lang`: Set from LID results (e.g., 'en', 'hi', 'hinglish')
- `audioDuration`: Set from LID results (seconds)

---

## Code Changes

### 1. Database Layer (`cofi-service/src/database.py`)

**Added methods to `CallRepo`:**

```python
def insert_from_distribution(...):
    """Insert call record during file distribution stage."""
    # Creates call with placeholder language data

def update_lid_info(...):
    """Update language_id, lang, and audio_duration from LID results."""
    # Updates call with actual language data
```

### 2. Main Orchestrator (`cofi-service/src/main.py`)

**Modified `distribute_files()` method:**

```python
# After successful file upload
self.file_dist_repo.insert(file_name, gpu_ip, batch_id)

# NEW: Create call record immediately
audit_form_id = self.process_repo.get_audit_form_id(self.settings.process_id)
self.call_repo.insert_from_distribution(
    audio_name=file_name,
    batch_id=batch_id,
    ip=gpu_ip,
    process_id=self.settings.process_id,
    category_mapping_id=self.settings.category_mapping_id,
    audio_endpoint=self.settings.audio_endpoint,
    audit_form_id=audit_form_id
)
```

**Renamed method:** `insert_calls_from_lid()` → `update_calls_from_lid()`

```python
def update_calls_from_lid(batch_id: int):
    """Update Call records with language info from LID results."""
    lid_records = self.lid_repo.get_by_batch(batch_id)

    for record in lid_records:
        lang_code = record.get('language', 'unknown')
        lang_record = self.language_repo.get_by_code(lang_code)
        language_id = lang_record['id'] if lang_record else None

        # Update existing call record
        self.call_repo.update_lid_info(
            audio_name=record['file'],
            batch_id=batch_id,
            language_id=language_id,
            lang_code=lang_code,
            audio_duration=record.get('duration', 0)
        )
```

### 3. Audit Pipeline (`cofi-service/src/audit_pipeline.py`)

**Modified `_distribute_files()` method:**

```python
# After successful file upload
self.file_dist_repo.insert(file_name, gpu_ip, batch_id)

# NEW: Create call record immediately
self.call_repo.insert_from_distribution(
    audio_name=file_name,
    batch_id=batch_id,
    ip=gpu_ip,
    process_id=self.process_id,
    category_mapping_id=self.category_mapping_id,
    audio_endpoint=self.settings.audio_endpoint,
    audit_form_id=audit_form_id
)
```

**Renamed method:** `_create_calls_from_lid()` → `_update_calls_from_lid()`

Similar implementation to main orchestrator's `update_calls_from_lid()`.

---

## Usage Examples

### Query Distributed Files

```sql
-- Check which files were distributed for a batch
SELECT audioName, ip, status, lang, audioDuration
FROM `call`
WHERE batchId = 123
ORDER BY id;

-- Before LID runs:
-- audioName: 'file001.wav', ip: '192.168.1.10', status: 'Pending', lang: 'unknown', audioDuration: 0

-- After LID runs:
-- audioName: 'file001.wav', ip: '192.168.1.10', status: 'Pending', lang: 'en', audioDuration: 45.3
```

### Check Distribution Progress

```sql
-- Count distributed files
SELECT COUNT(*) as distributed_files
FROM `call`
WHERE batchId = 123;

-- Count files with LID data
SELECT COUNT(*) as lid_processed
FROM `call`
WHERE batchId = 123
  AND lang != 'unknown';

-- Distribution progress
SELECT
    COUNT(*) as total,
    SUM(CASE WHEN lang = 'unknown' THEN 1 ELSE 0 END) as pending_lid,
    SUM(CASE WHEN lang != 'unknown' THEN 1 ELSE 0 END) as lid_complete
FROM `call`
WHERE batchId = 123;
```

---

## Backward Compatibility

✅ **Fully backward compatible**

- Existing batches already have call records
- New batches create call records during distribution
- STT, LLM1, LLM2 stages work the same way
- No changes needed to pipeline stages

---

## Testing Scenarios

### Scenario 1: Normal Flow

```bash
# 1. Start batch processing
python -m src.main

# 2. Check calls after distribution
SELECT COUNT(*) FROM `call` WHERE batchId = X AND lang = 'unknown';
# Should return total distributed files

# 3. Check calls after LID
SELECT COUNT(*) FROM `call` WHERE batchId = X AND lang != 'unknown';
# Should return total processed by LID
```

### Scenario 2: Distribution Failure

```bash
# If distribution fails at file 5,000/10,000:

# Query shows exactly which files made it
SELECT audioName FROM `call` WHERE batchId = X;
# Returns 5,000 records

# Can resume distribution from where it stopped
```

### Scenario 3: LID Failure

```bash
# If LID fails after processing 3,000/10,000 files:

# Calls exist with placeholder data
SELECT COUNT(*) FROM `call` WHERE batchId = X AND lang = 'unknown';
# Returns 7,000 (files not yet processed by LID)

# Can retry LID stage
# update_calls_from_lid() will update the 7,000 remaining files
```

---

## Migration Notes

### For Existing Batches

No migration needed! Existing batches already have call records created.

### For New Development

If you're adding new stages or modifying the pipeline:
- Call records are created during file distribution
- Use `CallRepo.get_by_status()` to query pending calls
- Language data is available after LID stage

---

## Performance Impact

### Before (Insert After LID)

```
File Distribution: 10,000 files × (upload + fileDistribution INSERT)
LID Stage: 10,000 files × (process + lidStatus INSERT)
insert_calls_from_lid: 10,000 × call INSERT
Total: 10,000 file uploads + 20,000 DB INSERTs
```

### After (Insert During Distribution)

```
File Distribution: 10,000 files × (upload + fileDistribution INSERT + call INSERT)
LID Stage: 10,000 files × (process + lidStatus INSERT)
update_calls_from_lid: 10,000 × call UPDATE
Total: 10,000 file uploads + 20,000 DB INSERTs + 10,000 DB UPDATEs
```

**Impact:**
- ➕ 10,000 additional UPDATEs (after LID)
- ✅ Better tracking and resilience
- ✅ Minimal performance impact (UPDATEs are fast)
- ✅ Overall benefit outweighs small overhead

---

## Summary

| Aspect | Before | After |
|--------|--------|-------|
| **Call creation** | After LID | During distribution ✅ |
| **Language data** | Available immediately | Updated after LID ✅ |
| **Tracking** | Only after LID | From distribution start ✅ |
| **Resilience** | LID failure = no calls | Calls exist regardless ✅ |
| **Distribution visibility** | ❌ No | ✅ Yes |
| **Query by status** | After LID only | Immediately ✅ |

**Key Benefits:**
- ✅ Better tracking of file distribution progress
- ✅ Can see which files were successfully distributed
- ✅ Early status tracking for all distributed files
- ✅ Improved resilience and recovery
- ✅ No breaking changes to existing code

The new approach provides significantly better visibility and tracking for large batch processing! 🎉
