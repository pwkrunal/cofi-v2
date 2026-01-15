# Rule Engine Step 2 Integration Plan

## Date: January 16, 2026
## Status: 📋 Planning Phase

---

## Overview

Integrate the existing `rule_engine_step2.py` module into the main batch processing pipeline at the Rule Engine Step 2 stage (currently marked as TODO). The module performs post-LLM trade-audio matching refinement using conversation data from LLM1 to validate script names, prices, and quantities.

**Key Constraint:** Do NOT modify `rule_engine_step2.py` - use it as-is.

---

## Current State

### Location in Pipeline
**File:** `cofi-service/src/main.py`
**Line:** ~390 (Rule Engine Step 2 section)

```python
# Stage: Rule Engine Step 2 (TODO: implement full logic)
if self.settings.rule_engine_enabled:
    if batch.get('triagingStep2Status') != 'Complete':
        logger.info("rule_engine_step2_starting")
        self.batch_repo.set_stage_start_time(batch_id, "triaging_step2")
        # TODO: Add Rule Engine Step 2 implementation here
        self.batch_repo.update_triaging_step2_status(batch_id, "Complete")
        self.batch_repo.set_stage_end_time(batch_id, "triaging_step2")
        logger.info("rule_engine_step2_done")
```

### Existing Module Analysis

**File:** `cofi-service/src/rule_engine_step2.py`

**Entry Point:**
- `process_rule_engine(current_date, batch_id)` - Main function to call

**Function Signature:**
```python
def process_rule_engine(current_date, batch_id):
    # Returns: True (boolean)
```

**What It Does:**
1. Loads data from multiple tables into memory (callMetadata, call, tradeMetadata, tradeAudioMapping, callConversation, lotQuantityMapping)
2. Processes trades marked as 'Non observatory call' from tradeMetadata
3. Matches trades with audio conversations using fuzzy matching and business rules
4. Validates script names, prices, and quantities against conversation data
5. Updates tradeAudioMapping with matching flags (isScript, isPrice, isQuantity)
6. Updates tradeMetadata with final matching results
7. Updates auditAnswer table with results

**Dependencies Identified:**
- `mysql.connector` - Direct MySQL connections (not using our Database class)
- `rapidfuzz` - Fuzzy string matching
- `datetime`, `timedelta` - Date/time operations
- `time` - Sleep operations for batch processing
- `re` - Regular expressions
- `collections.defaultdict` - Data structures

**Database Connection:**
- Uses its own hardcoded config dictionary
- Creates separate connections (doesn't use our connection pool)
- Has hardcoded host/credentials in lines 10-18

---

## Integration Steps

### Step 1: Update requirements.txt

**File:** `cofi-service/requirements.txt`

**Dependencies to Add:**
```
rapidfuzz==3.6.1
```

**Note:** 
- `mysql-connector-python` likely already exists (check first)
- Other dependencies (datetime, time, re, collections) are Python built-ins

**Action:**
1. Check if `mysql-connector-python` is already in requirements.txt
2. Add `rapidfuzz` with version specification
3. If mysql-connector missing, add: `mysql-connector-python==8.2.0`

---

### Step 2: Import Rule Engine Step 2 in main.py

**File:** `cofi-service/src/main.py`

**Add Import:**
- Location: Top of file with other imports (after line 17)
- Import: `from .rule_engine_step2 import process_rule_engine`

**Updated Imports Section:**
```python
from .rule_engine import RuleEngineStep1
from .rule_engine_step2 import process_rule_engine  # NEW
```

---

### Step 3: Integrate Function Call in Pipeline

**File:** `cofi-service/src/main.py`

**Location:** Lines 386-398 (Rule Engine Step 2 section)

**Implementation Plan:**

#### 3.1 Prepare Parameters
- **current_date:** Use `self.settings.batch_date` (format: "DD-MM-YYYY")
- **batch_id:** Use existing `batch_id` variable (integer)

#### 3.2 Wrap in Try-Except
- Rule engine step 2 should NOT crash entire pipeline
- Catch exceptions and log them
- Even if it fails, mark stage as complete (or add error status)

#### 3.3 Add Event Logging
- `EventLogger.stage_start()` before calling
- `EventLogger.stage_complete()` after success
- `EventLogger.file_error()` on failure

#### 3.4 Integration Pattern
```
Pseudocode:
1. Check if triagingStep2Status != 'Complete'
2. Log "rule_engine_step2_starting"
3. Set stage start time
4. Log EventLogger.stage_start
5. Try:
   a. Call process_rule_engine(batch_date, batch_id)
   b. Log success
   c. EventLogger.stage_complete
6. Except:
   a. Log error details
   b. EventLogger.file_error
7. Finally:
   a. Update triagingStep2Status = 'Complete'
   b. Set stage end time
8. Log "rule_engine_step2_done"
```

---

### Step 4: Configuration Considerations

**Issue:** `rule_engine_step2.py` has hardcoded database config

**Lines 10-18 in rule_engine_step2.py:**
```python
config = {
    'user': 'root',
    'password': 'smtb123',
    'host': '10.125.9.151',
    'database': 'auditNexDb'
}
```

**Options:**

#### Option A: Use Environment Variables (Recommended)
**Problem:** Can't modify rule_engine_step2.py
**Workaround:** 
- The script reads from `config` dict
- Since we can't modify the file, we must ensure the hardcoded values match production environment
- **Document this as a deployment requirement**

#### Option B: Create Wrapper (If Modification Allowed Later)
**Not applicable** - User said don't modify the file

#### Option C: Accept As-Is
**Decision:** 
- Use the file as-is for now
- Add to deployment checklist: "Ensure rule_engine_step2.py config matches environment"
- Create issue/ticket for future refactoring to use config.py

**Recommendation:** Option C (Accept As-Is) + Document limitation

---

### Step 5: Error Handling Strategy

**Considerations:**

1. **Long Running Process:**
   - The function processes trades in batches
   - Has sleep(10) calls between batches
   - Could take significant time for large datasets

2. **Database Operations:**
   - Performs many UPDATE queries
   - Uses separate connections (not pooled)
   - Has commit() calls throughout

3. **Failure Scenarios:**
   - Database connection failure
   - Timeout issues
   - Data inconsistencies
   - Memory issues with large datasets

**Error Handling Plan:**

#### 5.1 Timeout Protection
- Add timeout wrapper if possible
- Consider asyncio timeout (but function is synchronous)
- **Decision:** Let it run without timeout (may take hours for large batches)

#### 5.2 Exception Handling
- Catch all exceptions
- Log full traceback
- Don't let it crash main pipeline
- Mark stage as complete even on error (with error logged)

#### 5.3 Retry Logic
- **Don't retry** - if it fails once, likely to fail again
- Log error and continue pipeline
- Can be manually re-run later if needed

---

### Step 6: Logging Integration

**Add Structured Logging:**

#### 6.1 Before Execution
- `logger.info("rule_engine_step2_starting", batch_id=batch_id, batch_date=batch_date)`
- `EventLogger.stage_start(batch_id, 'triaging_step2', metadata={'batch_date': batch_date})`

#### 6.2 After Success
- `logger.info("rule_engine_step2_completed", batch_id=batch_id, duration=duration)`
- `EventLogger.stage_complete(batch_id, 'triaging_step2', success_count, error_count, metadata={...})`

#### 6.3 On Error
- `logger.error("rule_engine_step2_failed", batch_id=batch_id, error=str(e), traceback=...)`
- `EventLogger.file_error(batch_id, 'triaging_step2', 'rule_engine_step2', str(e))`

#### 6.4 Progress Logging (Optional)
- The function has internal print statements
- Could redirect or capture these for better monitoring
- **Decision:** Leave as-is (prints will appear in logs)

---

### Step 7: Testing Strategy

#### 7.1 Unit Test
**Not Required** - Function is provided as-is and should not be modified

#### 7.2 Integration Test
**Required:**
1. Small batch test (10 files with trades)
2. Verify function is called
3. Verify database updates occur
4. Verify pipeline continues after completion

#### 7.3 Test Scenarios

**Test 1: Happy Path**
- Batch with trade metadata
- Should complete successfully
- Verify tradeAudioMapping updated
- Verify auditAnswer updated

**Test 2: No Trade Data**
- Batch without trade metadata
- Should complete quickly (no work to do)
- Should not crash

**Test 3: Error Scenario**
- Database unavailable during step 2
- Should log error
- Should continue to batch completion

**Test 4: Large Batch**
- Batch with 10,000 trades
- Monitor execution time
- Verify memory usage acceptable
- Verify progress logs

---

### Step 8: Performance Considerations

#### 8.1 Expected Duration
- Function has batching logic (batch_size=10000)
- Has sleep(10) between batches
- Processes trades sequentially
- **Estimate:** 
  - 1000 trades: ~5-10 minutes
  - 10000 trades: ~30-60 minutes
  - 50000 trades: ~2-4 hours

#### 8.2 Resource Usage
- Loads entire datasets into memory (callMetadata, callsData, etc.)
- For 10,000 files: ~100MB-500MB memory
- **Monitor:** Memory usage during execution
- **Mitigation:** Already uses batch processing in the function

#### 8.3 Database Load
- Many UPDATE queries
- Separate connections (not pooled)
- Single commit per batch
- **Impact:** Moderate database load
- **Mitigation:** Already built into function (batch updates)

---

### Step 9: Monitoring and Observability

#### 9.1 Metrics to Track
- Execution time (start to end)
- Number of trades processed
- Number of updates performed
- Error count (if any)

#### 9.2 Dashboard Updates
**Not Required Initially** - Can be added later

#### 9.3 Alerts
- If execution time > expected threshold
- If error occurs
- If no trades processed (unexpected)

---

### Step 10: Deployment Checklist

#### Pre-Deployment
- [ ] Add `rapidfuzz` to requirements.txt
- [ ] Verify `mysql-connector-python` in requirements.txt
- [ ] Import `process_rule_engine` in main.py
- [ ] Add function call in Rule Engine Step 2 section
- [ ] Add error handling (try-except)
- [ ] Add EventLogger integration
- [ ] Update stage timestamps (already in place)

#### Configuration Verification
- [ ] Verify database config in rule_engine_step2.py matches environment
- [ ] Confirm hardcoded credentials are acceptable for deployment
- [ ] Document configuration limitation for future refactoring

#### Testing
- [ ] Install dependencies: `pip install rapidfuzz`
- [ ] Test import: `from .rule_engine_step2 import process_rule_engine`
- [ ] Run small batch (10 files) - verify completion
- [ ] Run medium batch (100 files) - verify performance
- [ ] Test error scenario (mock DB failure)

#### Deployment
- [ ] Update requirements.txt in repository
- [ ] Rebuild Docker image with new dependencies
- [ ] Deploy to staging environment
- [ ] Run test batch on staging
- [ ] Monitor logs for Rule Engine Step 2 execution
- [ ] Deploy to production
- [ ] Monitor first production batch

#### Post-Deployment
- [ ] Verify Rule Engine Step 2 executes successfully
- [ ] Check tradeAudioMapping updates
- [ ] Check auditAnswer updates
- [ ] Monitor execution time
- [ ] Review logs for any warnings/errors

---

## Implementation Details

### Function Call Pattern

**Location in Pipeline:**
- After LLM2 stage completes
- Before batch completion
- Only if rule_engine_enabled = True

**Execution Flow:**
```
LLM2 Complete → Stop Containers → Rule Engine Step 2 → Batch Complete
```

**Conditional Execution:**
- Check: `self.settings.rule_engine_enabled`
- Check: `batch.get('triagingStep2Status') != 'Complete'`
- Both must be True to execute

---

## Code Structure (Pseudocode)

```
# In main.py, around line 390

if self.settings.rule_engine_enabled:
    if batch.get('triagingStep2Status') != 'Complete':
        # 1. Log start
        logger.info("rule_engine_step2_starting")
        
        # 2. Set timestamp
        self.batch_repo.set_stage_start_time(batch_id, "triaging_step2")
        
        # 3. Event log start
        EventLogger.stage_start(batch_id, 'triaging_step2', metadata={
            'batch_date': self.settings.batch_date
        })
        
        # 4. Execute function
        try:
            result = process_rule_engine(
                current_date=self.settings.batch_date,
                batch_id=batch_id
            )
            
            # 5. Log success
            logger.info("rule_engine_step2_success", result=result)
            EventLogger.stage_complete(batch_id, 'triaging_step2', 
                                      success_count=1, failed_count=0)
        
        except Exception as e:
            # 6. Log error
            logger.error("rule_engine_step2_failed", error=str(e))
            EventLogger.file_error(batch_id, 'triaging_step2', 
                                  'rule_engine_step2', str(e))
        
        finally:
            # 7. Mark complete
            self.batch_repo.update_triaging_step2_status(batch_id, "Complete")
            self.batch_repo.set_stage_end_time(batch_id, "triaging_step2")
            logger.info("rule_engine_step2_done")
```

---

## Known Limitations and Workarounds

### Limitation 1: Hardcoded Database Config
**Issue:** Database credentials hardcoded in rule_engine_step2.py
**Impact:** Cannot use different DB per environment without file modification
**Workaround:** Ensure hardcoded values match production environment
**Future:** Refactor to use config.py (separate ticket)

### Limitation 2: Synchronous Execution
**Issue:** Function is synchronous, blocks pipeline
**Impact:** Long execution times for large batches
**Workaround:** Accept it - function already has internal batching
**Future:** Consider making it async (separate ticket)

### Limitation 3: Separate DB Connections
**Issue:** Doesn't use connection pool from database.py
**Impact:** Additional DB connections created
**Workaround:** Function manages its own connections
**Future:** Refactor to use Database class (separate ticket)

### Limitation 4: Print Statements
**Issue:** Uses print() instead of structured logging
**Impact:** Logs are not structured, harder to parse
**Workaround:** Redirect stdout to logs (Docker handles this)
**Future:** Refactor to use logger (separate ticket)

### Limitation 5: No Return Value Metadata
**Issue:** Function returns only `True` (boolean)
**Impact:** Cannot track how many trades were processed
**Workaround:** Parse logs or query database after completion
**Future:** Enhance return value (separate ticket)

---

## Risk Assessment

### High Risk
**None identified** - Function is already working in production elsewhere

### Medium Risk
1. **Long Execution Time**
   - **Mitigation:** Already has batching + progress logs
   - **Fallback:** Can be interrupted and resumed (idempotent)

2. **Database Load**
   - **Mitigation:** Function uses batch updates + commits
   - **Fallback:** Monitor database performance

### Low Risk
1. **Memory Usage**
   - **Mitigation:** Loads data once per batch
   - **Fallback:** Monitor memory during large batches

2. **Import Errors**
   - **Mitigation:** Test imports before deployment
   - **Fallback:** Pipeline will fail early (before processing)

---

## Dependencies

### Python Packages to Add

**requirements.txt:**
```
rapidfuzz==3.6.1
mysql-connector-python==8.2.0  # (if not already present)
```

### System Dependencies
**None** - All Python packages

### External Services
- MySQL database (already required)
- No additional services needed

---

## Validation and Testing

### Pre-Integration Testing
1. **Import Test:**
   ```python
   from src.rule_engine_step2 import process_rule_engine
   # Should import without errors
   ```

2. **Function Signature Test:**
   ```python
   # Verify function accepts correct parameters
   # process_rule_engine(current_date: str, batch_id: int) -> bool
   ```

### Post-Integration Testing
1. **Small Batch (10 files):**
   - Run complete pipeline
   - Verify Rule Engine Step 2 executes
   - Check logs for "rule_engine_step2_starting" and "rule_engine_step2_done"
   - Verify batchStatus.triagingStep2Status = 'Complete'
   - Verify timestamps set

2. **Medium Batch (100 files):**
   - Verify execution time reasonable
   - Check database updates
   - Monitor memory usage

3. **Error Handling Test:**
   - Temporarily break database connection
   - Verify pipeline continues after error
   - Verify error logged properly

### Acceptance Criteria
- ✅ Rule Engine Step 2 executes after LLM2
- ✅ Function completes without crashing pipeline
- ✅ tradeAudioMapping table updated
- ✅ auditAnswer table updated  
- ✅ Timestamps recorded in batchStatus
- ✅ EventLogger entries created
- ✅ Pipeline continues to completion

---

## Timeline Estimate

| Task | Duration | Dependencies |
|------|----------|--------------|
| Update requirements.txt | 10 mins | None |
| Add import to main.py | 5 mins | requirements.txt |
| Integrate function call | 30 mins | Import |
| Add error handling | 20 mins | Function call |
| Add logging integration | 20 mins | Error handling |
| Testing (small batch) | 30 mins | Integration |
| Testing (medium batch) | 1 hour | Small batch test |
| Documentation | 30 mins | Testing |
| **Total** | **3.5 hours** | - |

---

## Rollback Plan

### If Integration Fails:

1. **Immediate Rollback:**
   - Remove function call from main.py
   - Keep import (harmless)
   - Redeploy

2. **Partial Rollback:**
   - Comment out function call
   - Let pipeline skip Rule Engine Step 2
   - Investigate issue

3. **Data Rollback:**
   - If corrupted data: restore from backup
   - If incomplete: re-run manually

**Rollback Time:** < 5 minutes

---

## Future Enhancements

### Phase 2 (After Initial Deployment)
1. Refactor to use config.py for database connection
2. Replace print() with structured logging
3. Make function async for better performance
4. Add detailed return metadata (counts, errors)
5. Use Database class connection pool

### Phase 3 (Long Term)
1. Break function into smaller components
2. Add unit tests
3. Improve error handling granularity
4. Add progress callbacks for dashboard
5. Optimize memory usage for very large batches

---

## Documentation Updates Needed

### Files to Update:
1. **FINAL_IMPLEMENTATION_SUMMARY.md**
   - Add Rule Engine Step 2 to batch pipeline flow
   - Update database operations summary

2. **DEPLOYMENT_CHECKLIST.md**
   - Add dependency installation step
   - Add configuration verification step

3. **README.md** (if exists)
   - Document Rule Engine Step 2 stage
   - Document dependencies

---

## Success Criteria

✅ **Implementation Complete When:**
1. `rapidfuzz` added to requirements.txt
2. `process_rule_engine` imported in main.py
3. Function called in Rule Engine Step 2 section
4. Error handling implemented
5. EventLogger integration added
6. Timestamps updated (already in place)
7. Small batch test passes
8. Documentation updated

✅ **Production Ready When:**
1. All tests pass on staging
2. Performance acceptable on 1000 file batch
3. No errors in logs
4. Database updates verified
5. Monitoring confirms successful execution

---

## Contact and Support

### For Issues:
- Check logs for detailed error messages
- Verify database connectivity
- Confirm dependencies installed
- Review configuration in rule_engine_step2.py

### For Questions:
- How long should Rule Engine Step 2 take?
  - **Answer:** 5-10 minutes per 1000 trades
  
- What if it fails?
  - **Answer:** Pipeline continues; can be re-run manually
  
- Can it be skipped?
  - **Answer:** Yes, set rule_engine_enabled=False in config

---

**Document Version:** 1.0  
**Status:** Ready for Implementation  
**Estimated Effort:** 3.5 hours  
**Priority:** Medium  
**Complexity:** Low-Medium  
**Risk Level:** Low
