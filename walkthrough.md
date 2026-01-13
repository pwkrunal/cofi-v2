# Cofi Service Implementation Walkthrough

## Overview

Implemented a FastAPI-based audio processing service with distributed GPU processing capabilities:

| Service | Role | Location |
|---------|------|----------|
| **cofi-service** | FastAPI server + CPU orchestrator | `cofi-service/` |
| **cofi-mediator-service** | GPU helper service | `cofi-mediator-service/` |

---

## Project Structure

```
auditnex-cofi-2026/
├── cofi-service/
│   ├── src/
│   │   ├── api.py               # FastAPI endpoints (audit/reaudit)
│   │   ├── main.py              # Batch pipeline orchestrator
│   │   ├── audit_pipeline.py    # New audit upload pipeline
│   │   ├── reaudit_pipeline.py  # Reaudit pipeline
│   │   ├── config.py            # Pydantic settings
│   │   ├── database.py          # mysql.connector repositories
│   │   ├── file_manager.py      # File distribution
│   │   ├── mediator_client.py   # GPU HTTP client
│   │   ├── metadata_manager.py  # CSV upload
│   │   ├── rule_engine.py       # Trade-audio mapping
│   │   └── pipeline/
│   │       ├── base.py
│   │       ├── denoise_stage.py    # NEW: Audio denoising
│   │       ├── ivr_stage.py
│   │       ├── lid_stage.py
│   │       ├── stt_stage.py
│   │       ├── llm1_stage.py       # Trade extraction
│   │       ├── llm2_stage.py       # Question answering
│   │       └── llm2_custom_rules.py
│   ├── Dockerfile, docker-compose.yml, requirements.txt, .env.example
│
├── cofi-mediator-service/
│   ├── app.py                   # FastAPI endpoints
│   ├── docker_service.py        # Docker SDK wrapper
│   ├── Dockerfile, docker-compose.yml, requirements.txt
│
├── API_DETAILS.md               # Complete API documentation
└── cofi-service-postman-collection.json  # 17 API requests
```

---

## Complete Pipeline Flow

### New Audit Upload (`POST /audit/upload`)

1. **File Distribution** → Upload audio files to GPUs
2. **Denoise** (optional) → Remove background noise (port 5010)
3. **IVR** (optional) → IVR detection and trimming (port 4080)
4. **LID** → Language identification (port 4070)
5. **Create Call Records** → Insert into `call` table from LID results
6. **STT** → Speech-to-text transcription (port 4030)
7. **LLM1** (optional) → Trade extraction (port 7063)
8. **LLM2** (optional) → Audit question answering (port 7062)

### Reaudit (`POST /reaudit`)

- Reprocess existing audio files through selected stages
- Configurable stages: `["lid", "stt", "llm1", "llm2"]`
- Automatic data cleanup (deletes transcripts for STT, audit answers for LLM2)
- Concurrency lock prevents multiple simultaneous reaudits

---

## Key Features

| Feature | Implementation |
|---------|----------------|
| **FastAPI Server** | New `api.py` with `/audit/upload`, `/audit/status`, `/reaudit` endpoints |
| **Async Processing** | Background tasks with progress tracking |
| **Concurrency Control** | Locks prevent multiple concurrent uploads/reaudits |
| **Resume Capability** | `fileDistribution` table tracks per-file stage completion |
| **Parallel GPU Calls** | `asyncio.gather()` in `mediator_client.py` |
| **Database** | mysql.connector with connection pooling |
| **Optional Stages** | Denoise, IVR, LLM1, LLM2 via env flags |
| **Answer Normalization** | LLM2 normalizes responses (yes→YES, dealer→Dealer, etc.) |
| **Custom Rules** | Client-specific question handling in LLM2 |

---

## New FastAPI Endpoints

### 1. Health Check
```
GET /health
```

### 2. Upload Audio Files for Audit
```
POST /audit/upload
Content-Type: multipart/form-data

files: [audio1.wav, audio2.wav]
process_id: 1
category_mapping_id: 1

Response:
{
  "status": "queued",
  "task_id": "uuid",
  "files_uploaded": 2,
  "files": ["audio1.wav", "audio2.wav"]
}
```

### 3. Get Audit Task Status
```
GET /audit/status/{task_id}

Response:
{
  "task_id": "uuid",
  "status": "processing",
  "total_files": 2,
  "progress": {
    "lid": {"total": 2, "done": 2},
    "stt": {"total": 2, "done": 1},
    "llm1": {"total": 2, "done": 0},
    "llm2": {"total": 2, "done": 0}
  }
}
```

### 4. Reaudit Existing Files
```
POST /reaudit
Content-Type: application/json

{
  "audio_names": ["audio1.wav", "audio2.wav"],
  "stages": ["lid", "stt", "llm1", "llm2"]
}

Response:
{
  "status": "processing",
  "task_id": "uuid",
  "files_queued": 2
}
```

---

## Environment Variables

### cofi-service (.env)

```env
# GPU Machines
GPU_MACHINES=192.168.1.10,192.168.1.11
MEDIATOR_PORT=5065

# Service Ports
IVR_PORT=4080
LID_PORT=4070
STT_PORT=4030
LLM1_PORT=7063
LLM2_PORT=7062

# Batch Config (for main.py batch execution)
CLIENT_VOLUME=/client_volume
BATCH_DATE=15-12-2024
CURRENT_BATCH=1

# Call Record Config
PROCESS_ID=1
CATEGORY_MAPPING_ID=1
AUDIO_ENDPOINT=http://localhost/audios

# Optional Stages
DENOISE_ENABLED=true
IVR_ENABLED=true
LLM1_ENABLED=true
LLM2_ENABLED=true
CALLMETADATA_ENABLED=true
TRADEMETADATA_ENABLED=true
RULE_ENGINE_ENABLED=true

# STT Config
DIARIZATION=0  # 0=manual (no_of_speakers=2), 1=automatic (no_of_speakers=0)

# Wait Times (seconds)
IVR_WAIT=60
LID_WAIT=60
STT_WAIT=180
LLM_WAIT=300

# Container Names
IVR_CONTAINER=auditnex-ivr-1
LID_CONTAINER=auditnex-lid-1
STT_CONTAINER=auditnex-stt-inference-1
LLM1_CONTAINER=auditnex-llm-extraction-1
LLM2_CONTAINER=auditnex-llm-extraction-2

# API Endpoints
IVR_API_ENDPOINT=/file_ivr_clean
LID_API_ENDPOINT=/file_stt_features
STT_API_ENDPOINT=/file_stt_transcript
LLM_API_ENDPOINT=/extract_information

# NLP API Base URLs
NLP_API_Q1=http://localhost:7063
NLP_API_Q2=http://localhost:7062

# MySQL
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=password
MYSQL_DATABASE=testDb

# LLM2 Configuration
LLM2_SKIP_QUESTIONS=  # Comma-separated question names to skip
LLM2_NA_QUESTIONS=    # Comma-separated question names to mark as NA
```

---

## Database Tables

| Table | Purpose |
|-------|---------|
| `batchStatus` | Batch processing status (with `denoiseStatus` column) |
| `fileDistribution` | File→GPU mapping, stage completion flags |
| `callMetadata` | Call metadata from CSV |
| `tradeMetadata` | Trade metadata from CSV |
| `tradeAudioMapping` | Trade-to-audio file mapping (Rule Engine Step 1) |
| `lidStatus` | Language identification results |
| `call` | Main call records with status transitions |
| `language` | Language lookup table |
| `process` | Process configuration (auditFormId) |
| `transcript` | STT transcription results |
| `callConversation` | LLM1 trade extraction results |
| `auditAnswer` | LLM2 audit question answers |
| `auditFormSectionQuestionMapping` | Audit form questions |

### Required Database Schema Updates

```sql
-- Add denoiseStatus column to batchStatus
ALTER TABLE batchStatus 
ADD COLUMN denoiseStatus ENUM('Pending', 'InProgress', 'Complete') DEFAULT 'Pending';
```

---

## Deployment

### 1. Deploy cofi-mediator-service (on each GPU)
```bash
cd cofi-mediator-service
cp .env.example .env
# Edit .env with STORAGE_PATH
docker-compose up -d
```

### 2. Deploy cofi-service (on CPU)
```bash
cd cofi-service
cp .env.example .env
# Edit .env with GPU_MACHINES, MySQL credentials, ports
docker-compose up -d
```

### 3. Start FastAPI Server
```bash
# Inside cofi-service container or locally
python -m src.api
# Server runs on port 5064
```

---

## API Documentation

Complete API documentation is available in:
- **[API_DETAILS.md](file:///c:/Users/kruna/auditnex-cofi-2026/API_DETAILS.md)** - 9 sections, all endpoints documented
- **[cofi-service-postman-collection.json](file:///c:/Users/kruna/auditnex-cofi-2026/cofi-service-postman-collection.json)** - 17 API requests ready to import

### Documented APIs:
1. **Cofi Service APIs** - 4 FastAPI endpoints
2. **Denoise API** - Audio denoising (port 5010)
3. **IVR API** - IVR detection (port 4080)
4. **LID API** - Language identification (port 4070)
5. **STT API** - Speech-to-text (port 4030)
6. **LLM API** - LLM1 Trade Extraction & LLM2 Question Answering
7. **Metadata Upload APIs** - Trade & call metadata
8. **Container Management APIs** - Start/stop containers
9. **File Management APIs** - Upload/delete files

---

## Usage Examples

### Upload Files for Audit
```bash
curl -X POST http://localhost:5064/audit/upload \
  -F "files=@audio1.wav" \
  -F "files=@audio2.wav" \
  -F "process_id=1" \
  -F "category_mapping_id=1"
```

### Check Audit Status
```bash
curl http://localhost:5064/audit/status/{task_id}
```

### Reaudit Files
```bash
curl -X POST http://localhost:5064/reaudit \
  -H "Content-Type: application/json" \
  -d '{
    "audio_names": ["audio1.wav", "audio2.wav"],
    "stages": ["stt", "llm2"]
  }'
```

---

## Summary of Latest Changes

- ✅ **New Audit API** - FastAPI endpoints for upload, status, and reaudit
- ✅ **Denoise Stage** - Audio denoising before IVR (port 5010)
- ✅ **Reaudit Pipeline** - Reprocess existing files with data cleanup
- ✅ **Concurrency Locks** - Prevent multiple concurrent operations
- ✅ **LLM2 Enhancements** - Custom rules, answer mappings, NA/skip questions
- ✅ **STT Enhancements** - Post-processing, IVR, time-based diarization options
- ✅ **Complete Documentation** - API_DETAILS.md with 9 sections
- ✅ **Postman Collection** - 17 requests covering all APIs
- ✅ **Pipeline Flexibility** - All stages configurable via environment variables

