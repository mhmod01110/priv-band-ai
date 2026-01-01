# Stage System Refactoring: OOP-Based Architecture

## Overview
Refactored the stage system from dictionary-based configuration to Object-Oriented Programming (OOP) with isolated stage classes.

## Architecture

### Base Class
**Location**: `app/celery_app/stages/base.py`

```python
class BaseStage(ABC):
    - name: str (property)
    - status_message: str (property)
    - required: bool (property)
    - execute(): async method
    - should_run(): bool method (optional conditional)
```

### Individual Stage Classes
Each stage is now in its own file:

1. **Stage 0**: `app/celery_app/stages/stage_0_validation.py`
   - `Stage0Validation` - Policy validation without AI

2. **Stage 1**: `app/celery_app/stages/stage_1_ai_match.py`
   - `Stage1AIMatch` - AI policy match (conditional)

3. **Stage 2**: `app/celery_app/stages/stage_2_compliance.py`
   - `Stage2Compliance` - Compliance analysis

4. **Stage 3**: `app/celery_app/stages/stage_3_regeneration.py`
   - `Stage3Regeneration` - Policy regeneration (conditional)

5. **Stage 4**: `app/celery_app/stages/stage_4_finalization.py`
   - `Stage4Finalization` - Finalization

### Stage Registration
**Location**: `app/celery_app/tasks.py`

```python
STAGE_CLASSES = [
    Stage0Validation,
    Stage1AIMatch,
    Stage2Compliance,
    Stage3Regeneration,
    Stage4Finalization,
]
```

## Benefits

1. **Isolation**: Each stage is in its own file - easier to maintain
2. **OOP**: Proper inheritance and encapsulation
3. **Type Safety**: Better IDE support and type checking
4. **Testability**: Each stage can be tested independently
5. **Extensibility**: Easy to add new stages by creating new classes
6. **Clean Code**: Clear separation of concerns

## How to Add a New Stage

1. **Create stage file**: `app/celery_app/stages/stage_X_name.py`
   ```python
   from app.celery_app.stages.base import BaseStage
   
   class StageXName(BaseStage):
       @property
       def name(self) -> str:
           return 'Stage Name'
       
       @property
       def status_message(self) -> str:
           return 'Status message...'
       
       @property
       def required(self) -> bool:
           return True  # or False
       
       def should_run(self) -> bool:
           # Optional: conditional logic
           return True
       
       async def execute(self) -> None:
           # Stage logic here
           pass
   ```

2. **Register in `__init__.py`**:
   ```python
   from app.celery_app.stages.stage_X_name import StageXName
   __all__ = [..., 'StageXName']
   ```

3. **Add to STAGE_CLASSES** in `tasks.py`:
   ```python
   from app.celery_app.stages import StageXName
   
   STAGE_CLASSES = [
       ...,
       StageXName,  # Add here
   ]
   ```

## How to Remove a Stage

1. Remove from `STAGE_CLASSES` in `tasks.py`
2. Remove from `__init__.py` exports
3. Optionally delete the stage file

## Stage Execution Flow

```
StageExecutor.__init__()
    ↓
Instantiate all stage classes with context
    ↓
For each stage:
    ↓
    Check should_run()
    ↓
    Update progress
    ↓
    Call stage.execute()
    ↓
    Handle errors
    ↓
Build final result
```

## Context Object

All stages receive a `StageContext` object containing:
- Task instance
- Shop information
- Policy data
- Stage results storage
- Error tracking
- Early exit flags

## Error Handling

- Each stage can raise exceptions
- Required stage failures trigger task failure
- Optional stage failures are logged and continue
- Graceful degradation is attempted before failing

## Compatibility

✅ **Fully compatible** with existing:
- Frontend JavaScript
- API endpoints
- SSE streaming
- Progress tracking
- Error handling

No breaking changes to external interfaces.

