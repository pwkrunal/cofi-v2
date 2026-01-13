# Reaudit API - Implementation Plan

> [!NOTE]
> This is a **future implementation** - not coded yet.

## API Specification

```
POST http://localhost:5064/reaudit

Request:
{
  "audio_names": ["file1.wav", "file2.wav", ...],
  "stages": ["lid", "stt", "llm1", "llm2"]  // optional, default all
}

Response (immediate):
{
  "status": "processing",
  "task_id": "uuid",
  "files_queued": 50
}
```

## Behavior

- **Async**: Returns immediately, processes in background
- **Stages**: lid → stt → llm1 → llm2 (only specified stages run)
- **Data cleanup**:
  - If `stt` in stages: delete existing transcripts
  - If `llm2` in stages: delete existing auditAnswer records
- **Status reset**: Call status reset based on earliest stage

## Files to Create

| File | Purpose |
|------|---------|
| `api.py` | FastAPI server on port 5064 |
| `reaudit_pipeline.py` | Background task processing |

## Database Methods Needed

- `CallRepo.reset_status_by_names(audio_names, new_status)`
- `TranscriptRepo.delete_by_call_ids(call_ids)`
- `AuditAnswerRepo.delete_by_call_ids(call_ids)`

## Implementation Steps

1. Add FastAPI dependency to requirements.txt
2. Create `api.py` with `/reaudit` endpoint
3. Create `reaudit_pipeline.py` with async processing
4. Add database cleanup methods to `database.py`
5. Update `docker-compose.yml` to expose port 5064
6. Test with sample audio files
