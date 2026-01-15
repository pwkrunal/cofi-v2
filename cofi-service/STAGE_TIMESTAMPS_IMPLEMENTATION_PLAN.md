# Stage Timestamps Implementation Plan

## Date: January 15, 2026
## Status: 📋 Planning Phase

---

## Overview

Implement automatic tracking of start and end times for each pipeline stage in the `batchStatus` table to enable:
- Performance monitoring per stage
- Stage duration analysis
- Bottleneck identification
- Progress tracking with time estimates
- Historical performance trends

**Total Stages Tracked:** 13 stages (including triaging step 2)
**Total Timestamp Columns:** 26 (13 stages × 2 timestamps)

---

## Current State Analysis

### Likely Existing Columns in `batchStatus` Table

**Metadata Stages:**
- `callmetadataStartTime`, `callmetadataEndTime`
- `trademetadataStartTime`, `trademetadataEndTime`

**Pipeline Stages:**
- `denoiseStartTime`, `denoiseEndTime`
- `ivrStartTime`, `ivrEndTime`
- `lidStartTime`, `lidEndTime`
- `sttStartTime`, `sttEndTime`
- `llm1StartTime`, `llm1EndTime`
- `llm2StartTime`, `llm2EndTime`

**Rule Engine:**
- `triagingStartTime`, `triagingEndTime`
- `triagingStep2StartTime`, `triagingStep2EndTime`

### Current Status Fields (Already Implemented)
- `dbInsertionStatus`, `denoiseStatus`, `ivrStatus`, `lidStatus`, `sttStatus`, `llm1Status`, `llm2Status`, `triagingStatus`
- These track: 'Pending' → 'InProgress' → 'Complete'

### Current Issue
- **Timestamps likely exist but are NOT being updated** by the current pipeline code
- Status fields are updated, but corresponding timestamp fields are ignored

---

## Proposed Solution

### Step 1: Database Schema Verification

**Action Required:**
1. Read `schema.txt` or query the database to confirm all timestamp columns exist
2. Identify if any timestamp columns are missing
3. Create migration script if columns need to be added

**Expected Columns (13 stages × 2 timestamps = 26 columns):**
- File Distribution: `dbInsertionStartTime`, `dbInsertionEndTime`
- Call Metadata: `callmetadataStartTime`, `callmetadataEndTime`
- Trade Metadata: `trademetadataStartTime`, `trademetadataEndTime`
- Denoise: `denoiseStartTime`, `denoiseEndTime`
- IVR: `ivrStartTime`, `ivrEndTime`
- LID: `lidStartTime`, `lidEndTime`
- Triaging Step 1: `triagingStartTime`, `triagingEndTime`
- Triaging Step 2: `triagingStep2StartTime`, `triagingStep2EndTime`
- STT: `sttStartTime`, `sttEndTime`
- LLM1: `llm1StartTime`, `llm1EndTime`
- LLM2: `llm2StartTime`, `llm2EndTime`

---

## Step 2: Update BatchStatusRepo Class

**File:** `cofi-service/src/database.py`

### Add New Methods:

#### Method 1: `set_stage_start_time(batch_id, stage_name)`
- Map stage_name to corresponding startTime column
- Update: `UPDATE batchStatus SET <stage>StartTime = NOW() WHERE id = ?`
- Called when stage begins

#### Method 2: `set_stage_end_time(batch_id, stage_name)`
- Map stage_name to corresponding endTime column
- Update: `UPDATE batchStatus SET <stage>EndTime = NOW() WHERE id = ?`
- Called when stage completes

#### Method 3: `get_stage_duration(batch_id, stage_name)` (Optional)
- Calculate duration between start and end times
- Return duration in seconds
- Useful for monitoring queries

### Stage Name Mapping:
```
{
    'file_distribution': ('dbInsertionStartTime', 'dbInsertionEndTime'),
    'callmetadata': ('callmetadataStartTime', 'callmetadataEndTime'),
    'trademetadata': ('trademetadataStartTime', 'trademetadataEndTime'),
    'denoise': ('denoiseStartTime', 'denoiseEndTime'),
    'ivr': ('ivrStartTime', 'ivrEndTime'),
    'lid': ('lidStartTime', 'lidEndTime'),
    'triaging': ('triagingStartTime', 'triagingEndTime'),
    'triaging_step2': ('triagingStep2StartTime', 'triagingStep2EndTime'),
    'stt': ('sttStartTime', 'sttEndTime'),
    'llm1': ('llm1StartTime', 'llm1EndTime'),
    'llm2': ('llm2StartTime', 'llm2EndTime')
}
```

---

## Step 3: Update Pipeline Stages

### 3.1 Batch Processing Pipeline

**File:** `cofi-service/src/main.py`

**Updates Required:**

#### File Distribution Stage:
- **Before:** `self.batch_repo.update_db_insertion_status(batch_id, 'InProgress')`
- **Add:** `self.batch_repo.set_stage_start_time(batch_id, 'file_distribution')`
- **After completion:** `self.batch_repo.set_stage_end_time(batch_id, 'file_distribution')`

#### Call Metadata Stage:
- **Before:** Start processing callMetadata.csv
- **Add:** `self.batch_repo.set_stage_start_time(batch_id, 'callmetadata')`
- **After completion:** `self.batch_repo.set_stage_end_time(batch_id, 'callmetadata')`

#### Trade Metadata Stage:
- **Before:** Start processing tradeMetadata.csv
- **Add:** `self.batch_repo.set_stage_start_time(batch_id, 'trademetadata')`
- **After completion:** `self.batch_repo.set_stage_end_time(batch_id, 'trademetadata')`

#### Denoise Stage:
- **Before:** `self.batch_repo.update_denoise_status(batch_id, 'InProgress')`
- **Add:** `self.batch_repo.set_stage_start_time(batch_id, 'denoise')`
- **After completion:** `self.batch_repo.set_stage_end_time(batch_id, 'denoise')`

#### IVR Stage:
- **Before:** `self.batch_repo.update_ivr_status(batch_id, 'InProgress')`
- **Add:** `self.batch_repo.set_stage_start_time(batch_id, 'ivr')`
- **After completion:** `self.batch_repo.set_stage_end_time(batch_id, 'ivr')`

#### LID Stage:
- **Before:** `self.batch_repo.update_lid_status(batch_id, 'InProgress')`
- **Add:** `self.batch_repo.set_stage_start_time(batch_id, 'lid')`
- **After completion:** `self.batch_repo.set_stage_end_time(batch_id, 'lid')`

#### Triaging/Rule Engine Stage (Step 1):
- **Before:** `self.batch_repo.update_triaging_status(batch_id, 'InProgress')`
- **Add:** `self.batch_repo.set_stage_start_time(batch_id, 'triaging')`
- **After completion:** `self.batch_repo.set_stage_end_time(batch_id, 'triaging')`

#### Triaging/Rule Engine Stage (Step 2):
- **Before:** Start of triaging step 2 (trade-audio mapping refinement or second pass)
- **Add:** `self.batch_repo.set_stage_start_time(batch_id, 'triaging_step2')`
- **After completion:** `self.batch_repo.set_stage_end_time(batch_id, 'triaging_step2')`
- **Note:** This stage typically runs after LLM1 to:
  - Refine trade-audio mappings with NLP data
  - Apply additional business rules
  - Perform post-LLM validation
  - Handle edge cases or corrections

#### STT Stage:
- **Before:** `self.batch_repo.update_stt_status(batch_id, 'InProgress')`
- **Add:** `self.batch_repo.set_stage_start_time(batch_id, 'stt')`
- **After completion:** `self.batch_repo.set_stage_end_time(batch_id, 'stt')`

#### LLM1 Stage:
- **Before:** `self.batch_repo.update_llm1_status(batch_id, 'InProgress')`
- **Add:** `self.batch_repo.set_stage_start_time(batch_id, 'llm1')`
- **After completion:** `self.batch_repo.set_stage_end_time(batch_id, 'llm1')`

#### LLM2 Stage:
- **Before:** `self.batch_repo.update_llm2_status(batch_id, 'InProgress')`
- **Add:** `self.batch_repo.set_stage_start_time(batch_id, 'llm2')`
- **After completion:** `self.batch_repo.set_stage_end_time(batch_id, 'llm2')`

### 3.2 New Audit Upload Pipeline

**File:** `cofi-service/src/audit_pipeline.py`

**Updates Required:**

#### File Distribution:
- **Add:** `self.batch_repo.set_stage_start_time(batch_id, 'file_distribution')`
- **After completion:** `self.batch_repo.set_stage_end_time(batch_id, 'file_distribution')`

#### LID Stage:
- **Before:** `self.batch_repo.update_lid_status(batch_id, 'InProgress')`
- **Add:** `self.batch_repo.set_stage_start_time(batch_id, 'lid')`
- **After completion:** `self.batch_repo.set_stage_end_time(batch_id, 'lid')`

#### STT Stage:
- **Before:** `self.batch_repo.update_stt_status(batch_id, 'InProgress')`
- **Add:** `self.batch_repo.set_stage_start_time(batch_id, 'stt')`
- **After completion:** `self.batch_repo.set_stage_end_time(batch_id, 'stt')`

#### LLM1 Stage:
- **Before:** `self.batch_repo.update_llm1_status(batch_id, 'InProgress')`
- **Add:** `self.batch_repo.set_stage_start_time(batch_id, 'llm1')`
- **After completion:** `self.batch_repo.set_stage_end_time(batch_id, 'llm1')`

#### LLM2 Stage:
- **Before:** `self.batch_repo.update_llm2_status(batch_id, 'InProgress')`
- **Add:** `self.batch_repo.set_stage_start_time(batch_id, 'llm2')`
- **After completion:** `self.batch_repo.set_stage_end_time(batch_id, 'llm2')`

### 3.3 Reaudit Pipeline

**File:** `cofi-service/src/reaudit_pipeline.py`

**Special Consideration:**
- Reaudit does NOT update `batchStatus` (operates on existing batches)
- **Decision Required:** Should reaudit update timestamps?

**Options:**
1. **Option A - Don't Update (Recommended):**
   - Preserve original batch timestamps
   - Reaudit is a "redo", not part of original batch flow
   - Avoids confusion in reporting

2. **Option B - Update Timestamps:**
   - Overwrite timestamps for reprocessed stages
   - Shows when stages were last run
   - May confuse batch completion time reporting

**Recommendation:** Skip timestamp updates for reaudit pipeline (Option A)

---

## Step 4: Error Handling

### Considerations:

1. **Stage Failures:**
   - If stage fails, should endTime still be set?
   - **Recommendation:** Yes - set endTime even on failure (shows time spent before failure)

2. **Partial Completion:**
   - If 1000/10000 files processed then crash
   - On resume, startTime already set, don't overwrite
   - **Logic:** Only set startTime if NULL

3. **Resume Logic:**
```
if batch_repo.get_stage_start_time(batch_id, stage) is None:
    batch_repo.set_stage_start_time(batch_id, stage)
```

4. **End Time on Completion:**
   - Always set endTime when stage completes (successful or with errors)
   - Even if some files failed, stage is "complete"

---

## Step 5: Recovery and Resume Behavior

### Scenario: Pipeline Crashes Mid-Stage

**Current State:**
- `lidStatus = 'InProgress'`
- `lidStartTime = '2026-01-15 10:00:00'`
- `lidEndTime = NULL`

**On Resume:**
1. Check if `lidStartTime` is already set → Yes
2. **Don't overwrite** startTime (preserves original start)
3. Continue processing
4. Set `lidEndTime` when complete

**Result:**
- Total stage duration includes time before crash
- Accurately reflects total time taken (including interruption)

### Alternative Approach (If Desired):

**Track Actual Processing Time (Excluding Downtime):**
- Would require additional columns: `<stage>ProcessingSeconds`
- Accumulate actual processing time across resumes
- More complex, may not be worth it

**Recommendation:** Use simple start/end timestamps (includes downtime in duration)

---

## Step 6: Monitoring and Reporting Enhancements

### New SQL Queries Available After Implementation:

#### Query 1: Stage Durations for a Batch
```sql
SELECT 
    id,
    batchDate,
    batchNumber,
    TIMESTAMPDIFF(SECOND, denoiseStartTime, denoiseEndTime) as denoise_duration_sec,
    TIMESTAMPDIFF(SECOND, ivrStartTime, ivrEndTime) as ivr_duration_sec,
    TIMESTAMPDIFF(SECOND, lidStartTime, lidEndTime) as lid_duration_sec,
    TIMESTAMPDIFF(SECOND, triagingStartTime, triagingEndTime) as triaging_duration_sec,
    TIMESTAMPDIFF(SECOND, triagingStep2StartTime, triagingStep2EndTime) as triaging_step2_duration_sec,
    TIMESTAMPDIFF(SECOND, sttStartTime, sttEndTime) as stt_duration_sec,
    TIMESTAMPDIFF(SECOND, llm1StartTime, llm1EndTime) as llm1_duration_sec,
    TIMESTAMPDIFF(SECOND, llm2StartTime, llm2EndTime) as llm2_duration_sec,
    TIMESTAMPDIFF(SECOND, dbInsertionStartTime, llm2EndTime) as total_duration_sec
FROM batchStatus
WHERE id = <BATCH_ID>;
```

#### Query 2: Average Stage Duration (Last 30 Days)
```sql
SELECT 
    AVG(TIMESTAMPDIFF(SECOND, denoiseStartTime, denoiseEndTime)) as avg_denoise_sec,
    AVG(TIMESTAMPDIFF(SECOND, lidStartTime, lidEndTime)) as avg_lid_sec,
    AVG(TIMESTAMPDIFF(SECOND, triagingStartTime, triagingEndTime)) as avg_triaging_sec,
    AVG(TIMESTAMPDIFF(SECOND, triagingStep2StartTime, triagingStep2EndTime)) as avg_triaging_step2_sec,
    AVG(TIMESTAMPDIFF(SECOND, sttStartTime, sttEndTime)) as avg_stt_sec,
    AVG(TIMESTAMPDIFF(SECOND, llm1StartTime, llm1EndTime)) as avg_llm1_sec,
    AVG(TIMESTAMPDIFF(SECOND, llm2StartTime, llm2EndTime)) as avg_llm2_sec
FROM batchStatus
WHERE batchDate >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
  AND status = 'Completed';
```

#### Query 3: Identify Bottlenecks
```sql
SELECT 
    'denoise' as stage,
    AVG(TIMESTAMPDIFF(SECOND, denoiseStartTime, denoiseEndTime)) as avg_duration
FROM batchStatus WHERE denoiseEndTime IS NOT NULL
UNION ALL
SELECT 'lid', AVG(TIMESTAMPDIFF(SECOND, lidStartTime, lidEndTime))
FROM batchStatus WHERE lidEndTime IS NOT NULL
UNION ALL
SELECT 'triaging', AVG(TIMESTAMPDIFF(SECOND, triagingStartTime, triagingEndTime))
FROM batchStatus WHERE triagingEndTime IS NOT NULL
UNION ALL
SELECT 'triaging_step2', AVG(TIMESTAMPDIFF(SECOND, triagingStep2StartTime, triagingStep2EndTime))
FROM batchStatus WHERE triagingStep2EndTime IS NOT NULL
UNION ALL
SELECT 'stt', AVG(TIMESTAMPDIFF(SECOND, sttStartTime, sttEndTime))
FROM batchStatus WHERE sttEndTime IS NOT NULL
UNION ALL
SELECT 'llm1', AVG(TIMESTAMPDIFF(SECOND, llm1StartTime, llm1EndTime))
FROM batchStatus WHERE llm1EndTime IS NOT NULL
UNION ALL
SELECT 'llm2', AVG(TIMESTAMPDIFF(SECOND, llm2StartTime, llm2EndTime))
FROM batchStatus WHERE llm2EndTime IS NOT NULL
ORDER BY avg_duration DESC;
```

#### Query 4: Current Stage Progress (For Running Batches)
```sql
SELECT 
    id,
    batchNumber,
    status,
    CASE 
        WHEN llm2StartTime IS NOT NULL THEN 'LLM2'
        WHEN llm1StartTime IS NOT NULL THEN 'LLM1'
        WHEN sttStartTime IS NOT NULL THEN 'STT'
        WHEN triagingStep2StartTime IS NOT NULL THEN 'Triaging Step 2'
        WHEN triagingStartTime IS NOT NULL THEN 'Triaging'
        WHEN lidStartTime IS NOT NULL THEN 'LID'
        WHEN denoiseStartTime IS NOT NULL THEN 'Denoise'
        ELSE 'File Distribution'
    END as current_stage,
    TIMESTAMPDIFF(MINUTE, 
        COALESCE(llm2StartTime, llm1StartTime, sttStartTime, triagingStep2StartTime, 
                 triagingStartTime, lidStartTime, denoiseStartTime, dbInsertionStartTime),
        NOW()
    ) as stage_running_minutes
FROM batchStatus
WHERE status != 'Completed' AND status != 'Failed'
ORDER BY id DESC;
```

#### Query 5: Performance Comparison by Batch Size
```sql
SELECT 
    totalFiles,
    COUNT(*) as batch_count,
    AVG(TIMESTAMPDIFF(SECOND, dbInsertionStartTime, llm2EndTime) / 60) as avg_total_minutes,
    MIN(TIMESTAMPDIFF(SECOND, dbInsertionStartTime, llm2EndTime) / 60) as min_total_minutes,
    MAX(TIMESTAMPDIFF(SECOND, dbInsertionStartTime, llm2EndTime) / 60) as max_total_minutes
FROM batchStatus
WHERE status = 'Completed'
  AND dbInsertionStartTime IS NOT NULL
  AND llm2EndTime IS NOT NULL
GROUP BY 
    CASE 
        WHEN totalFiles <= 100 THEN '1-100'
        WHEN totalFiles <= 1000 THEN '101-1000'
        WHEN totalFiles <= 5000 THEN '1001-5000'
        ELSE '5000+'
    END
ORDER BY totalFiles;
```

---

## Step 7: Dashboard Integration

### Dashboard Updates Needed

**File:** `cofi-dashboard/src/app.py` (or equivalent)

#### New API Endpoint: `/api/batch/{batch_id}/timing`

**Response:**
```json
{
    "batch_id": 123,
    "stages": [
        {
            "name": "file_distribution",
            "start_time": "2026-01-15T10:00:00",
            "end_time": "2026-01-15T10:15:00",
            "duration_seconds": 900,
            "status": "Complete"
        },
        {
            "name": "lid",
            "start_time": "2026-01-15T10:15:00",
            "end_time": "2026-01-15T10:45:00",
            "duration_seconds": 1800,
            "status": "Complete"
        },
        {
            "name": "llm2",
            "start_time": "2026-01-15T12:00:00",
            "end_time": null,
            "duration_seconds": null,
            "status": "InProgress"
        }
    ],
    "total_elapsed_seconds": 7200,
    "estimated_remaining_seconds": 3600  // Based on historical averages
}
```

#### Dashboard Visualizations:

1. **Timeline Chart:**
   - Horizontal bar chart showing each stage
   - X-axis: Time
   - Visual representation of when each stage ran

2. **Stage Duration Pie Chart:**
   - Show percentage of time spent in each stage
   - Identify bottlenecks visually

3. **Progress Indicator:**
   - "Currently processing LLM2 (started 15 minutes ago)"
   - "Estimated time remaining: 45 minutes"

4. **Performance Trends:**
   - Line chart: average stage durations over time
   - Identify if performance is degrading

---

## Step 8: Testing Strategy

### Unit Tests Required:

1. **Test BatchStatusRepo Methods:**
   - `test_set_stage_start_time()` - Verify timestamp is set
   - `test_set_stage_end_time()` - Verify timestamp is set
   - `test_stage_name_mapping()` - Verify all stage names map correctly
   - `test_get_stage_duration()` - Verify duration calculation

2. **Test Pipeline Integration:**
   - `test_batch_pipeline_sets_timestamps()` - Run small batch, verify all timestamps
   - `test_audit_pipeline_sets_timestamps()` - Upload files, verify timestamps
   - `test_resume_preserves_start_time()` - Crash and resume, verify startTime unchanged

3. **Test Edge Cases:**
   - `test_stage_with_no_files()` - Should still set timestamps
   - `test_stage_with_all_failures()` - Should set endTime
   - `test_disabled_stage()` - Timestamps should remain NULL

### Integration Testing:

1. **Small Batch (10 files):**
   - Run complete pipeline
   - Verify all 10 stage timestamps are set
   - Verify durations are reasonable

2. **Large Batch (1000 files):**
   - Verify performance impact is negligible
   - Check timestamp accuracy

3. **Resume Test:**
   - Start batch, kill process mid-stage
   - Resume
   - Verify startTime preserved, endTime set on completion

4. **Audit Upload Test:**
   - Upload 5 files
   - Verify timestamps for LID, STT, LLM1, LLM2

---

## Step 9: Migration Script

### If Columns Don't Exist

**File:** `database/migrations/add_stage_timestamps.sql`

```sql
-- Add timestamp columns to batchStatus table
ALTER TABLE batchStatus
ADD COLUMN IF NOT EXISTS dbInsertionStartTime DATETIME DEFAULT NULL,
ADD COLUMN IF NOT EXISTS dbInsertionEndTime DATETIME DEFAULT NULL,
ADD COLUMN IF NOT EXISTS callmetadataStartTime DATETIME DEFAULT NULL,
ADD COLUMN IF NOT EXISTS callmetadataEndTime DATETIME DEFAULT NULL,
ADD COLUMN IF NOT EXISTS trademetadataStartTime DATETIME DEFAULT NULL,
ADD COLUMN IF NOT EXISTS trademetadataEndTime DATETIME DEFAULT NULL,
ADD COLUMN IF NOT EXISTS denoiseStartTime DATETIME DEFAULT NULL,
ADD COLUMN IF NOT EXISTS denoiseEndTime DATETIME DEFAULT NULL,
ADD COLUMN IF NOT EXISTS ivrStartTime DATETIME DEFAULT NULL,
ADD COLUMN IF NOT EXISTS ivrEndTime DATETIME DEFAULT NULL,
ADD COLUMN IF NOT EXISTS lidStartTime DATETIME DEFAULT NULL,
ADD COLUMN IF NOT EXISTS lidEndTime DATETIME DEFAULT NULL,
ADD COLUMN IF NOT EXISTS triagingStartTime DATETIME DEFAULT NULL,
ADD COLUMN IF NOT EXISTS triagingEndTime DATETIME DEFAULT NULL,
ADD COLUMN IF NOT EXISTS triagingStep2StartTime DATETIME DEFAULT NULL,
ADD COLUMN IF NOT EXISTS triagingStep2EndTime DATETIME DEFAULT NULL,
ADD COLUMN IF NOT EXISTS sttStartTime DATETIME DEFAULT NULL,
ADD COLUMN IF NOT EXISTS sttEndTime DATETIME DEFAULT NULL,
ADD COLUMN IF NOT EXISTS llm1StartTime DATETIME DEFAULT NULL,
ADD COLUMN IF NOT EXISTS llm1EndTime DATETIME DEFAULT NULL,
ADD COLUMN IF NOT EXISTS llm2StartTime DATETIME DEFAULT NULL,
ADD COLUMN IF NOT EXISTS llm2EndTime DATETIME DEFAULT NULL;

-- Add index for performance queries
CREATE INDEX idx_batch_timestamps ON batchStatus(batchDate, status);
```

---

## Step 10: Performance Considerations

### Database Impact:

**Additional DB Operations per Batch:**
- ~26 UPDATE queries (2 per stage × 13 stages)
- Negligible impact (timestamp updates are fast)
- No additional SELECT queries needed

**Storage Impact:**
- 26 DATETIME columns × 8 bytes = 208 bytes per batch
- For 1000 batches = 208 KB
- Negligible storage impact

### Query Performance:

- Timestamp comparisons are very fast
- Add indexes if querying by date range frequently
- No impact on file processing performance

---

## Implementation Checklist

### Phase 1: Investigation (1 hour)
- [ ] Read schema.txt to confirm timestamp columns exist
- [ ] Query database to check actual column names
- [ ] Document any missing columns
- [ ] Create migration script if needed

### Phase 2: Database Updates (2 hours)
- [ ] Run migration script (if needed)
- [ ] Add `set_stage_start_time()` to BatchStatusRepo
- [ ] Add `set_stage_end_time()` to BatchStatusRepo
- [ ] Add `get_stage_duration()` to BatchStatusRepo (optional)
- [ ] Implement stage name mapping dictionary
- [ ] Add unit tests for new methods

### Phase 3: Pipeline Updates (3 hours)
- [ ] Update main.py batch pipeline (11 stages - includes triaging step 2)
- [ ] Update audit_pipeline.py (4 stages)
- [ ] Add resume logic (don't overwrite startTime if set)
- [ ] Add error handling (set endTime even on failure)
- [ ] Test with small batch

### Phase 4: Testing (2 hours)
- [ ] Unit tests for BatchStatusRepo
- [ ] Integration test: batch pipeline
- [ ] Integration test: audit pipeline
- [ ] Integration test: resume functionality
- [ ] Performance test: 1000 files batch

### Phase 5: Documentation (1 hour)
- [ ] Update FINAL_IMPLEMENTATION_SUMMARY.md
- [ ] Add monitoring queries document
- [ ] Update deployment checklist
- [ ] Add to support documentation

### Phase 6: Dashboard Enhancement (Optional, 4 hours)
- [ ] Add timing API endpoint
- [ ] Create timeline visualization
- [ ] Add stage duration charts
- [ ] Add performance trends

---

## Benefits

### Operational Benefits:
1. **Performance Monitoring:** Track which stages are slow
2. **Capacity Planning:** Know how long batches take
3. **SLA Tracking:** Measure against time commitments
4. **Bottleneck Identification:** Find optimization opportunities
5. **Progress Estimation:** Show users "time remaining"

### Troubleshooting Benefits:
1. **Identify Stuck Stages:** Stage started but not ended
2. **Historical Analysis:** Compare batch performance over time
3. **Regression Detection:** Alert if stages suddenly slow down
4. **Resource Planning:** Schedule batches during off-peak based on duration

### Business Benefits:
1. **Customer Reporting:** Show processing time per batch
2. **Cost Analysis:** Time = compute cost
3. **Improvement Tracking:** Show optimization impact (before/after)
4. **Predictability:** Estimate completion times accurately

---

## Risks and Mitigations

### Risk 1: Timestamp Columns Don't Exist
- **Impact:** Medium
- **Mitigation:** Migration script ready, easy to add

### Risk 2: Performance Impact
- **Impact:** Low
- **Mitigation:** Timestamp updates are very fast, negligible impact

### Risk 3: Resume Logic Complexity
- **Impact:** Medium
- **Mitigation:** Simple NULL check before setting startTime

### Risk 4: Timezone Issues
- **Impact:** Low
- **Mitigation:** Use MySQL NOW() function (server timezone consistent)

---

## Alternative Approaches Considered

### Alternative 1: Store Timestamps in batchExecutionLog
**Pros:**
- Already logging events there
- No schema changes needed

**Cons:**
- Requires queries to calculate durations
- Not as efficient for reporting
- Harder to query "all batch durations"

**Decision:** Rejected - dedicated columns are cleaner and faster

### Alternative 2: Add processingSeconds Column
**Pros:**
- Excludes downtime from duration
- More accurate "processing time"

**Cons:**
- More complex to implement
- Requires timer logic in code
- Doesn't show actual wall-clock time

**Decision:** Rejected - simple start/end timestamps sufficient

### Alternative 3: Track Only Total Batch Time
**Pros:**
- Simpler implementation
- Only 2 columns needed

**Cons:**
- Can't identify which stage is slow
- Less useful for optimization
- Missing granular insights

**Decision:** Rejected - per-stage timestamps provide more value

---

## Success Criteria

✅ **Implementation Complete When:**
1. All timestamp columns verified/added to database
2. BatchStatusRepo has timestamp update methods
3. All 10 stages in batch pipeline update timestamps
4. All 4 stages in audit pipeline update timestamps
5. Resume logic preserves original startTime
6. Unit tests pass (90%+ coverage on new methods)
7. Integration test: 100 file batch completes with all timestamps set
8. Documentation updated
9. No performance regression (< 1% overhead)

✅ **Acceptance Criteria:**
1. Query any batch and see duration for each stage
2. Dashboard shows current stage and elapsed time
3. Reporting queries work for average durations
4. Resume after crash works correctly (startTime preserved)

---

## Timeline Estimate

| Phase | Duration | Dependencies |
|-------|----------|--------------|
| Investigation | 1 hour | None |
| Database Updates | 2 hours | Investigation |
| Pipeline Updates | 3 hours | Database Updates |
| Testing | 2 hours | Pipeline Updates |
| Documentation | 1 hour | Testing |
| Dashboard (Optional) | 4 hours | Testing |
| **Total (Core)** | **9 hours** | - |
| **Total (with Dashboard)** | **13 hours** | - |

---

## Next Steps

1. **Review this plan** with team
2. **Verify schema** - confirm timestamp columns exist
3. **Create migration** if columns missing
4. **Implement in phases** (database → pipeline → testing → dashboard)
5. **Deploy to staging** and test with real data
6. **Deploy to production** with monitoring

---

## Questions to Resolve

1. **Do timestamp columns already exist in `batchStatus` table?**
   - Need to check schema.txt or query database

2. **Should reaudit pipeline update timestamps?**
   - Recommendation: No (preserves original batch timing)

3. **Should we track time excluding downtime?**
   - Recommendation: No (simple start/end is sufficient)

4. **Dashboard integration priority?**
   - Recommendation: Medium (can be done after core implementation)

5. **Should we alert if stage exceeds threshold?**
   - Recommendation: Yes, but separate feature (future enhancement)

---

**Document Version:** 1.0  
**Status:** Ready for Implementation  
**Estimated Effort:** 9 hours (core) / 13 hours (with dashboard)  
**Priority:** Medium-High  
**Complexity:** Low-Medium
