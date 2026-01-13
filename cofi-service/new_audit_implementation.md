# New Audit API - Implementation Plan

> [!NOTE]
> This is a **future implementation** - not coded yet.

## Use Case
Client uploads new audio files via API for audit processing through LID → STT → LLM1 → LLM2.

---

## API Specification

### 1. Upload Files Endpoint

```
POST http://localhost:5064/audit/upload

Request: multipart/form-data
- files: audio file(s)
- batch_id: optional (creates new if not provided)
- process_id: required
- category_mapping_id: optional (default: 1)

Response:
{
  "status": "queued",
  "task_id": "uuid",
  "batch_id": 123,
  "files_uploaded": 5,
  "files": ["file1.wav", "file2.wav", ...]
}
```

### 2. Check Status Endpoint

```
GET http://localhost:5064/audit/status/{task_id}

Response:
{
  "task_id": "uuid",
  "status": "processing|completed|failed",
  "progress": {
    "lid": {"total": 5, "done": 5},
    "stt": {"total": 5, "done": 3},
    "llm1": {"total": 5, "done": 0},
    "llm2": {"total": 5, "done": 0}
  }
}
```

---

## File Storage Flow

> [!IMPORTANT]
> Files are stored locally first (mandatory), then distributed to GPUs.

```
1. Upload API receives files
           │
           ▼
2. Save to LOCAL storage (mandatory)
   └── Path from env: CLIENT_VOLUME (e.g., /client_volume/uploads/)
           │
           ▼
3. Distribute to GPUs (round-robin like batch)
   ├── GPU1: file1.wav, file4.wav
   ├── GPU2: file2.wav, file5.wav
   └── GPU3: file3.wav
           │
           ▼
4. Upload files to respective GPUs via mediator
           │
           ▼
5. Create fileDistribution records
```

---

## Workflow

```
Upload API Request
    │
    ▼
Save files to LOCAL storage (mandatory)
    │
    ▼
Distribute files to GPUs (reuse file_manager.py logic)
    │
    ▼
Create fileDistribution + Call records
    │
    ▼
Background Task: LID → STT → LLM1 (if enabled) → LLM2
    │
    ▼
Mark task as Complete
```

---

## Stage Configuration

| Stage | Controlled By | Behavior |
|-------|--------------|----------|
| LID | Always runs | Language detection |
| STT | Always runs | Transcription |
| LLM1 | `LLM1_ENABLED` env | Skip if disabled |
| LLM2 | `LLM2_ENABLED` env | Skip if disabled |

---

## GPU Distribution Options

| Mode | Description |
|------|-------------|
| **Round-robin** | Files distributed across multiple GPUs (default, like batch) |
| **Single GPU** | All files sent to one GPU |
| **Auto** | Select GPU with least load |

Configure via request param: `gpu_mode: "single|round-robin|auto"`

---

## Files to Create

| File | Purpose |
|------|---------|
| `api.py` | FastAPI endpoints |
| `audit_pipeline.py` | New audit processing pipeline |
| Reuse `file_manager.py` | For GPU distribution logic |
| Reuse `mediator_client.py` | For file upload to GPUs |

---

## Database Changes

- Create `auditTask` table for tracking:
  ```sql
  CREATE TABLE auditTask (
    id INT PRIMARY KEY AUTO_INCREMENT,
    taskId VARCHAR(36),
    batchId INT,
    status ENUM('queued', 'processing', 'completed', 'failed'),
    totalFiles INT,
    createdAt DATETIME,
    completedAt DATETIME
  )
  ```

---

## Implementation Steps

1. Create `/audit/upload` endpoint
2. Implement local file storage
3. Reuse `file_manager.py` for GPU distribution
4. Reuse `mediator_client.py` for GPU file upload
5. Create `auditTask` table
6. Create background task runner
7. Integrate existing stages (LID, STT, LLM1 if enabled, LLM2 if enabled)
8. Create `/audit/status` endpoint
9. Test with single and multiple files
