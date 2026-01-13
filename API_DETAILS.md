# API Documentation

This document lists all external API endpoints used in `cofi_app_v2.py` and `stt_wrapper.py`, including their HTTP methods, payloads, and response structures.

---

## Table of Contents

1. [Cofi Service APIs](#1-cofi-service-apis)
2. [Denoise API](#2-denoise-api)
3. [IVR API](#3-ivr-api)
4. [LID API (Language Identification)](#4-lid-api-language-identification)
5. [STT API (Speech-to-Text)](#5-stt-api-speech-to-text)
6. [LLM API (NLP/Text Extraction)](#6-llm-api-nlptext-extraction)
7. [Metadata Upload APIs](#7-metadata-upload-apis)
8. [Container Management APIs](#8-container-management-apis)
9. [File Management APIs](#9-file-management-apis)

---

## 1. Cofi Service APIs

**Purpose:** Main FastAPI service for managing audio audit processing workflows.

**Base URL:** `http://localhost:5064` (configurable)

---

### 1.1 Health Check

**Purpose:** Verify that the cofi-service is running and healthy.

#### Endpoint

```
GET /health
```

#### Method: `GET`

#### Request

No parameters required.

#### Response

```json
{
    "status": "healthy"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | Service health status |

---

### 1.2 Upload Audio Files for Audit

**Purpose:** Upload audio files for audit processing through the complete pipeline (LID → STT → LLM1 → LLM2).

#### Endpoint

```
POST /audit/upload
```

#### Method: `POST`

#### Request

**Content-Type:** `multipart/form-data`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `files` | file[] | Yes | Audio files to process (multiple files supported) |
| `process_id` | integer | Yes | Process ID for categorizing the audit |
| `category_mapping_id` | integer | No | Category mapping ID (default: 1) |

#### Response

```json
{
    "status": "queued",
    "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "files_uploaded": 3,
    "files": [
        "audio1.wav",
        "audio2.wav",
        "audio3.wav"
    ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | Task status (`"queued"`) |
| `task_id` | string | Unique UUID for tracking this audit task |
| `files_uploaded` | integer | Number of files successfully uploaded |
| `files` | array | List of uploaded file names |

#### Notes

- Processing happens asynchronously in the background
- Only one audit upload can be processed at a time (returns 409 if another is in progress)
- Files are distributed across GPU machines using round-robin
- Use the `task_id` to check processing status via `/audit/status/{task_id}`

#### Error Responses

**409 Conflict** - Another audit upload is already being processed:
```json
{
    "detail": "Another audit upload is already being processed. Please wait for it to complete."
}
```

**400 Bad Request** - No files provided:
```json
{
    "detail": "No files provided"
}
```

---

### 1.3 Get Audit Task Status

**Purpose:** Check the progress of an audit task.

#### Endpoint

```
GET /audit/status/{task_id}
```

#### Method: `GET`

#### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `task_id` | string | Yes | UUID of the audit task |

#### Response

```json
{
    "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "status": "processing",
    "total_files": 3,
    "progress": {
        "lid": {
            "total": 3,
            "done": 3
        },
        "stt": {
            "total": 3,
            "done": 2
        },
        "llm1": {
            "total": 3,
            "done": 0
        },
        "llm2": {
            "total": 3,
            "done": 0
        }
    }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `task_id` | string | UUID of the audit task |
| `status` | string | Overall task status (`"queued"`, `"processing"`, `"completed"`, `"failed"`) |
| `total_files` | integer | Total number of files in this task |
| `progress` | object | Progress breakdown by pipeline stage |
| `progress.{stage}.total` | integer | Total files for this stage |
| `progress.{stage}.done` | integer | Completed files for this stage |

#### Pipeline Stages

| Stage | Description |
|-------|-------------|
| `lid` | Language Identification |
| `stt` | Speech-to-Text transcription |
| `llm1` | First LLM extraction (if enabled) |
| `llm2` | Second LLM extraction (if enabled) |

#### Error Responses

**404 Not Found** - Task ID not found:
```json
{
    "detail": "Task not found"
}
```

---

### 1.4 Reaudit Existing Files

**Purpose:** Reprocess existing audio files through specified pipeline stages.

#### Endpoint

```
POST /reaudit
```

#### Method: `POST`

#### Request Payload

```json
{
    "audio_names": [
        "audio1.wav",
        "audio2.wav"
    ],
    "stages": ["stt", "llm2"]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `audio_names` | array | Yes | List of audio file names to reprocess |
| `stages` | array | No | Pipeline stages to run (default: `["lid", "stt", "llm1", "llm2"]`) |

#### Valid Stages

| Stage | Description | Data Cleanup |
|-------|-------------|--------------|
| `lid` | Language Identification | Resets LID status |
| `stt` | Speech-to-Text | Deletes existing transcripts |
| `llm1` | First LLM extraction | - |
| `llm2` | Second LLM extraction | Deletes existing auditAnswer records |

#### Response

```json
{
    "status": "processing",
    "task_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
    "files_queued": 2
}
```

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | Task status (`"processing"`) |
| `task_id` | string | Unique UUID for tracking this reaudit task |
| `files_queued` | integer | Number of files queued for reprocessing |

#### Notes

- Processing happens asynchronously in the background
- Only one reaudit can be processed at a time (returns 409 if another is in progress)
- Stages are executed in order: lid → stt → llm1 → llm2
- Data cleanup happens automatically based on selected stages
- Use the `task_id` to check processing status via `/audit/status/{task_id}`

#### Error Responses

**409 Conflict** - Another reaudit is already in progress:
```json
{
    "detail": "Another reaudit is already in progress. Please wait for it to complete."
}
```

**400 Bad Request** - No audio names provided:
```json
{
    "detail": "No audio names provided"
}
```

**400 Bad Request** - Invalid stage specified:
```json
{
    "detail": "Invalid stage: invalid_stage_name"
}
```

---

## 2. Denoise API

**Purpose:** Remove background noise from audio files to improve audio quality before processing.

### Endpoint

| Environment Variable | Default Example |
|---------------------|-----------------|
| `DENOISE_API_URL` | `http://localhost:5010/process` |

### Method: `POST`

### Request Payload

```json
{
    "file_name": "audio_file.wav"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `file_name` | string | Name of the audio file to denoise |

### Response

```json
{
    "status": "success",
    "message": "Audio denoised successfully",
    "output_path": "/path/to/denoised_audio.wav",
    "original_duration_sec": 120.0,
    "processed_duration_sec": 120.0
}
```

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | Processing status (`"success"` or `"error"`) |
| `message` | string | Status message |
| `output_path` | string | Path to the denoised audio file |
| `original_duration_sec` | float | Original audio duration |
| `processed_duration_sec` | float | Duration after denoising |

### Notes

- Denoise API should be called **before** IVR detection
- Improves audio quality for better transcription accuracy
- Processing is typically fast (near real-time)

---

## 3. IVR API

**Purpose:** Detect and clean IVR (Interactive Voice Response) segments from audio files.

### Endpoint

| Environment Variable | Default Example |
|---------------------|-----------------|
| `IVR_API_URL` | `http://localhost:4080/file_ivr_clean` |

### Method: `POST`

### Request Payload

```json
{
    "file_name": "audio_file.wav"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `file_name` | string | Name of the audio file to process |

### Response

```json
{
    "ivr_detected": true,
    "ivr_end_sec": 15.5,
    "original_duration_sec": 120.0,
    "trimmed_duration_sec": 104.5,
    "output_path": "/path/to/trimmed_audio.wav"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `ivr_detected` | boolean | Whether IVR was detected |
| `ivr_end_sec` | float | End time of IVR segment in seconds |
| `original_duration_sec` | float | Original audio duration |
| `trimmed_duration_sec` | float | Duration after IVR trimming |
| `output_path` | string | Path to the processed audio file |

---

## 4. LID API (Language Identification)

**Purpose:** Identify the language spoken in an audio file.

### Endpoint

| Environment Variable | Default Example |
|---------------------|-----------------|
| `LID_API_URL` | Configured via env |
| `STT_API_URL` | Configured via env |
| `LID_ENDPOINT` | Configured via env |

### Method: `POST`

### Request Payload

```json
{
    "file_name": "audio_file.wav",
    "entity": "LID",
    "response": ""
}
```

| Field | Type | Description |
|-------|------|-------------|
| `file_name` | string | Name of the audio file |
| `entity` | string | Always `"LID"` for language identification |
| `response` | string | Empty string (placeholder) |

### Response

```json
{
    "data": {
        "derived_value": [
            {
                "results": ["hi"],
                "audio_duration": 120.5
            }
        ]
    }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `data.derived_value[0].results[0]` | string | Detected language code (`"en"`, `"hi"`, `"hinglish"`, etc.) |
| `data.derived_value[0].audio_duration` | float | Audio duration in seconds |

### Language Codes

| Code | Language |
|------|----------|
| `en` | English |
| `hi` | Hindi |
| `hinglish` | Hindi-English mix |

---

## 5. STT API (Speech-to-Text)

**Purpose:** Convert speech audio to text transcription.

### Endpoint

| Environment Variable | Default Example |
|---------------------|-----------------|
| `STT_URL` | Configured via env |
| `STT_API_URL` | Configured via env |
| `STT_ENDPOINTS` | Comma-separated list of endpoints |

### Method: `POST`

### Request Payload

```json
{
    "file_name": "audio_file.wav",
    "no_of_speakers": 2,
    "audio_language": "hi",
    "post_processing": true,
    "use_ivr": true,
    "use_time_based": false
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file_name` | string | Yes | Name of the audio file |
| `no_of_speakers` | integer | Yes | Expected number of speakers (default: 2, set to 0 when `use_time_based=true`) |
| `audio_language` | string | Yes | Language code (`"en"`, `"hi"`) |
| `post_processing` | boolean | No | Enable post-processing of transcripts (default: `true`) |
| `use_ivr` | boolean | No | Enable IVR detection and processing (default: based on config) |
| `use_time_based` | boolean | No | Enable time-based automatic diarization (default: `false`). When `true`, set `no_of_speakers=0` |

#### Diarization Modes

- **Manual Diarization** (`use_time_based=false`): Specify exact number of speakers via `no_of_speakers` (typically 2)
- **Automatic Diarization** (`use_time_based=true`): Set `no_of_speakers=0` for automatic speaker detection

### Response

The transcription is stored in the database (`transcript` table) with the following structure:

```json
{
    "callId": 123,
    "languageId": 1,
    "startTime": 0.5,
    "endTime": 3.2,
    "speaker": "Speaker 1",
    "text": "Hello, how can I help you?",
    "rateOfSpeech": "Good",
    "confidence": 90.0
}
```

| Field | Type | Description |
|-------|------|-------------|
| `callId` | integer | Call identifier |
| `languageId` | integer | Language ID |
| `startTime` | float | Start time in seconds |
| `endTime` | float | End time in seconds |
| `speaker` | string | Speaker identifier |
| `text` | string | Transcribed text |
| `rateOfSpeech` | string | Speech rate assessment |
| `confidence` | float | Confidence score |

---

## 6. LLM API (NLP/Text Extraction)

**Purpose:** Extract information and analyze text using LLM prompts.

### Endpoint

| Environment Variable | Default Example |
|---------------------|-----------------|
| `NLP_API` | Configured via env |

### Method: `POST`

### Endpoint Path: `/extract_information`

### Request Payload

```json
{
    "text": "Transcript text here...",
    "text_language": "hi",
    "prompts": [
        {
            "entity": "trade_classify",
            "prompts": ["Your prompt instruction here..."],
            "type": "multiple"
        }
    ],
    "additional_params": {}
}
```

| Field | Type | Description |
|-------|------|-------------|
| `text` | string | Full transcript text to analyze |
| `text_language` | string | Language of the text (`"hi"`, `"en"`) |
| `prompts` | array | List of prompt configurations |
| `prompts[].entity` | string | Entity name being extracted |
| `prompts[].prompts` | array | List of prompt instructions |
| `prompts[].type` | string | Prompt type (`"multiple"`) |
| `additional_params` | object | Additional parameters (usually empty) |

### Response

```json
{
    "data": {
        "derived_value": [
            {
                "result": "trade"
            }
        ]
    }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `data.derived_value[0].result` | string/object | Extracted result based on the prompt |

### Common Entity Types

| Entity | Description | Expected Result |
|--------|-------------|-----------------|
| `trade_classify` | Classify as trade/non-trade | `"trade"` or `"non-trade"` |
| `trade_extraction` | Extract trade details | JSON array of trade objects |
| `speech_parameter` | Analyze speech patterns | Various |

### Trade Extraction Response Example

```json
{
    "data": {
        "derived_value": [
            {
                "result": [
                    {
                        "scriptName": "NIFTY",
                        "optionType": "call",
                        "lot/quantity": "50",
                        "strikePrice": "18500",
                        "tradePrice": "150.50",
                        "buySell": "Buy",
                        "expiryDate": "28-Dec-2025"
                    }
                ]
            }
        ]
    }
}
```

---

### LLM1 - Trade Extraction API

**Purpose:** Extract trade information from transcripts using LLM1 (used in `llm1_stage.py`).

#### Endpoint

| Environment Variable | Default Example |
|---------------------|-----------------|
| `NLP_API_Q1` | `http://localhost:7063` |

#### Method: `POST`

#### Endpoint Path: `/extract_information`

#### Request Payload

```json
{
    "text": "Speaker 0: I want to buy 100 shares of Reliance at 2500.\nSpeaker 1: Sure, let me place the order.",
    "text_language": "hi",
    "prompts": [""],
    "additional_params": {
        "trade_details": [
            {
                "symbol": "RELIANCE",
                "strikePrice": 2500,
                "tradeQuantity": 100,
                "tradePrice": 2500,
                "buySell": "Buy",
                "scripName": "Reliance Industries"
            }
        ]
    }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `text` | string | Full transcript text with speaker labels |
| `text_language` | string | Language of the text (`"hi"`, `"en"`) |
| `prompts` | array | Empty string array `[""]` for LLM1 |
| `additional_params.trade_details` | array | Trade details from `tradeAudioMapping` table |
| `trade_details[].symbol` | string | Stock symbol |
| `trade_details[].strikePrice` | number | Strike price |
| `trade_details[].tradeQuantity` | number | Trade quantity |
| `trade_details[].tradePrice` | number | Trade price |
| `trade_details[].buySell` | string | Buy or Sell |
| `trade_details[].scripName` | string | Script name |

#### Response

```json
{
    "data": {
        "derived_value": [
            {
                "result": [
                    {
                        "scriptName": "RELIANCE",
                        "optionType": "equity",
                        "lot/quantity": "100",
                        "strikePrice": "2500",
                        "tradePrice": "2500.50",
                        "buySell": "Buy",
                        "expiryDate": "NA",
                        "tradeDate": "13-01-2026",
                        "currentMarket": "2510"
                    }
                ]
            }
        ]
    }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `data.derived_value[0].result` | array | Array of extracted trade objects |
| `result[].scriptName` | string | Extracted script/stock name |
| `result[].optionType` | string | Option type (equity, call, put, etc.) |
| `result[].lot/quantity` | string | Lot or quantity (converted to int) |
| `result[].strikePrice` | string | Strike price (converted to float) |
| `result[].tradePrice` | string | Trade price (converted to float) |
| `result[].buySell` | string | Buy or Sell |
| `result[].expiryDate` | string | Expiry date (DD-MM-YYYY format) |
| `result[].tradeDate` | string | Trade date (DD-MM-YYYY format) |
| `result[].currentMarket` | string | Current market price (converted to float) |

#### Usage Notes

- The `prompts` field is always an empty string array `[""]` for LLM1
- Trade details come from the `tradeAudioMapping` table based on audio file name
- Results are stored in the `callConversation` table
- Call status is updated from `TranscriptDone` to `AuditDone` after processing
- NA values in the response are handled gracefully (converted to 0 or empty string)
- Used in the LLM1 pipeline stage for trade-related audio files

---

### LLM2 - Question Answering API

**Purpose:** Answer audit questions using LLM2 (used in `llm2_stage.py` `answer_question` method).

#### Endpoint

| Environment Variable | Default Example |
|---------------------|-----------------|
| `NLP_API_Q2` | `http://localhost:7062` |

#### Method: `POST`

#### Endpoint Path: `/extract_information`

#### Request Payload

```json
{
    "text": "Speaker 0: Hello, I want to buy 100 shares of Reliance.\nSpeaker 1: Sure, let me place the order for you.",
    "text_language": "hi",
    "prompts": [
        {
            "entity": "greeting",
            "prompts": ["Did the dealer greet the client? Answer in YES or NO."],
            "type": "multiple"
        }
    ],
    "additional_params": {}
}
```

| Field | Type | Description |
|-------|------|-------------|
| `text` | string | Full transcript text with speaker labels |
| `text_language` | string | Language of the text (`"hi"`, `"en"`) |
| `prompts[].entity` | string | Question attribute/entity name |
| `prompts[].prompts` | array | Question intent/instruction |
| `prompts[].type` | string | Prompt type (`"multiple"`) |
| `additional_params` | object | Additional parameters (usually empty) |

#### Response

```json
{
    "data": {
        "derived_value": [
            {
                "result": "yes"
            }
        ]
    }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `data.derived_value[0].result` | string | Answer result (normalized via mappings) |

#### Answer Normalization Mappings

The LLM2 stage applies the following normalizations to API responses:

| Raw Response | Normalized Answer |
|--------------|-------------------|
| `yes` | `YES` |
| `no` | `NO` |
| `na` | `NA` |
| `dealer` | `Dealer` |
| `client` | `Client` |
| `both` | `Both client & dealer` |
| `anger` | `YES` |
| `disgust` | `YES` |

#### Usage Notes

- The `entity` field should match the question's `attribute` field from the database
- The `prompts` array should contain the question's `intent` (English) or `hindiIntent` (Hindi)
- Responses are automatically normalized using the mappings above
- Used for answering individual audit form questions in the LLM2 pipeline stage

---

## 7. Metadata Upload APIs

### 7.1 Upload Trade Metadata

**Purpose:** Upload trade metadata CSV file.

### Endpoint

| Environment Variable | Path |
|---------------------|------|
| `COFI_URL` | `/api/v1/upload_trademetadata` |

### Method: `POST`

### Request

- **Content-Type:** `multipart/form-data`

```
file: trade_metadata_DD-MM-YYYY.csv
```

### Response

```json
{
    "status": true,
    "message": "Data uploaded successfully"
}
```

---

### 7.2 Upload Call Metadata

**Purpose:** Upload call metadata CSV file.

### Endpoint

| Environment Variable | Path |
|---------------------|------|
| `COFI_URL` | `/api/v1/upload_callmetadata` |

### Method: `POST`

### Request

- **Content-Type:** `multipart/form-data`

```
file: call_metadata_DD-MM-YYYY.csv
```

**OR JSON:**

```json
{
    "data": [
        {
            "clientCode": "ABC123",
            "sClientName": "John Doe",
            ...
        }
    ]
}
```

### Response

```json
{
    "status": true,
    "message": "Data uploaded successfully"
}
```

---

## 8. Container Management APIs

**Purpose:** Start/stop Docker containers for various services.

### Base URL

| Environment Variable | Description |
|---------------------|-------------|
| `SPLIT_BASE_URL` | Base URL for container management |

### 8.1 Start Container

### Endpoint: `/start_container`

### Method: `POST`

### Request Payload

```json
{
    "container_name": "auditnex-stt-inference-1"
}
```

### Response

```json
{
    "status": "started",
    "container_name": "auditnex-stt-inference-1"
}
```

---

### 8.2 Stop Container

### Endpoint: `/stop_container`

### Method: `POST`

### Request Payload

```json
{
    "container_name": "auditnex-stt-inference-1"
}
```

### Response

```json
{
    "status": "stopped",
    "container_name": "auditnex-stt-inference-1"
}
```

---

### 8.3 Check Service Status

### Endpoint: `/is_service_running`

### Method: `POST`

### Request Payload

```json
{
    "service_name": "auditnex-llm-extraction-1"
}
```

### Response

```json
{
    "is_running": true,
    "service_name": "auditnex-llm-extraction-1"
}
```

---

## 9. File Management APIs

### 9.1 Upload File for STT Processing

**Purpose:** Upload/copy audio file for STT processing.

### Endpoint: `/upload_file_stt`

### Method: `POST`

### Request Payload

```json
{
    "file_url": "http://server/audios/28-07-2025/audio_file.wav",
    "ivr_enabled": 1
}
```

| Field | Type | Description |
|-------|------|-------------|
| `file_url` | string | URL to download the audio file |
| `ivr_enabled` | integer | `1` = IVR processing enabled, `0` = disabled |

### Response

```json
{
    "message": "File uploaded successfully",
    "status": true
}
```

---

### 9.2 Delete File

### Endpoint: `/delete_file_stt`

### Method: `POST`

### Request Payload

```json
{
    "file_name": "audio_file.wav"
}
```

### Response

```json
{
    "status": "deleted",
    "file_name": "audio_file.wav"
}
```

---

## Environment Variables Summary

| Variable | Description |
|----------|-------------|
| `COFI_URL` | Base URL for COFI API |
| `STT_URL` | STT service URL |
| `STT_API_URL` | STT API URL |
| `STT_ENDPOINTS` | Comma-separated STT endpoints |
| `NLP_API` | NLP/LLM API URL |
| `LID_API_URL` | Language identification API URL |
| `LID_ENDPOINT` | LID endpoint(s) |
| `IVR_API_URL` | IVR detection API URL |
| `DENOISE_API_URL` | Audio denoising API URL |
| `SPLIT_BASE_URL` | Container management base URL |
| `AUDIO_ENDPOINT` | Audio file serving endpoint |
| `AUDITNEX_API` | AuditNex main API |
| `CALLBACK_URL` | Callback URL for async responses |
| `SOURCE` | Source files base path |
| `STORAGE_PATH` | Local storage path for audio files |
| `DESTINATION_LID` | LID processed files destination |

---

## Common HTTP Headers

```
Content-Type: application/json
```

---

## Error Responses

Most APIs return errors in this format:

```json
{
    "status": false,
    "message": "Error description",
    "error": "Detailed error message"
}
```

| HTTP Status | Description |
|-------------|-------------|
| 200 | Success |
| 400 | Bad Request - Missing or invalid parameters |
| 500 | Internal Server Error |

---

## Notes

1. **Timeouts:** Most API calls use a timeout of 50-600 seconds depending on the operation.
2. **Parallel Processing:** LID and IVR APIs support parallel processing with multiple endpoints.
3. **File Paths:** Audio files are typically stored in `{STORAGE_PATH}/{filename}` or `{SOURCE}/{date}/{filename}`.
4. **Date Format:** Dates are typically in `DD-MM-YYYY` format (e.g., `21-09-2025`).
