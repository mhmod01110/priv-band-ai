# Error Handling Fix: Proper Task Failure Detection

## Problem
Celery tasks were sometimes completing with status "SUCCESS" even when they actually failed due to errors like:
- Out of Quota (429 errors)
- API authentication failures
- Service crashes
- Missing result data

This caused a contradiction where:
- Task status: `SUCCESS` (completed)
- Actual result: `None` or missing
- Frontend: Shows success but has no data to display

## Root Cause
1. **Exception Handling**: Exceptions were caught but tasks still returned `{'success': False, ...}` instead of raising exceptions
2. **Missing Validation**: `_build_final_result()` didn't validate that critical data (like `compliance_report`) existed before building the result
3. **Silent Failures**: Some stage failures were caught and logged but didn't properly fail the task

## Solution

### 1. **Error Tracking in StageContext**
Added error tracking fields:
```python
self.critical_error = None
self.error_type = None
self.failed_stages = []
```

### 2. **Enhanced Stage Error Handling**
- **Error Classification**: Detects quota, timeout, authentication errors
- **Required vs Optional Stages**: Required stage failures trigger task failure
- **Graceful Degradation**: Tries cached results before failing
- **Proper Exception Propagation**: Required stage failures raise exceptions

### 3. **Result Validation**
`_build_final_result()` now validates:
- `compliance_report` must exist (required)
- `match_result` must exist (required)
- Raises exception if validation fails (marks task as FAILURE)

### 4. **Proper Task Failure**
Main exception handler:
- **Raises exceptions** instead of returning `{'success': False}`
- This ensures Celery marks task as `FAILURE` not `SUCCESS`
- Error classification for better retry logic
- No retry for quota/auth errors (they won't fix themselves)

### 5. **Error Types Detected**
- `quota_exceeded`: 429, rate limit, billing errors
- `timeout`: Timeout errors
- `authentication`: 401, 403, API key errors
- `unknown`: Other errors

## Flow Diagram

```
Stage Execution
    ↓
Stage Fails?
    ↓ Yes
Is Required Stage?
    ↓ Yes
Try Graceful Degradation
    ↓
Fallback Found?
    ↓ No
Raise Exception → Task FAILURE
    ↓
Celery Marks as FAILURE
    ↓
API Returns status: "failed"
    ↓
Frontend Shows Error
```

## Changes Made

### `app/celery_app/tasks.py`

1. **StageContext** - Added error tracking
2. **StageExecutor.execute_all_stages()** - Enhanced error handling with classification
3. **handle_stage_2_compliance()** - Added validation and proper exception handling
4. **_build_final_result()** - Validates critical data before building result
5. **analyze_policy_task()** - Proper exception raising for task failure

## Testing Checklist

- [x] Quota exceeded errors properly fail task
- [x] Missing compliance_report fails task
- [x] Task status is FAILURE not SUCCESS on error
- [x] Frontend receives error status correctly
- [x] Error messages are properly formatted
- [x] Graceful degradation still works
- [x] Required vs optional stage handling works

## API Compatibility

✅ **No breaking changes** - API already handles FAILURE status correctly:
- SSE stream sends `status: "failed"` with error message
- Frontend `TaskMonitor` handles failed status
- Error messages displayed to user

## Result

Now when a task fails:
1. ✅ Exception is raised → Celery marks as `FAILURE`
2. ✅ API returns `status: "failed"` with error message
3. ✅ Frontend receives and displays error
4. ✅ No more "success with no data" contradictions

