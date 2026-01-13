# LLM2 Speech Parameter Questions - Implementation Plan

## Goal
Handle audit questions with `attribute='speech_parameter'` by calling a specialized STT API instead of the standard NLP API.

---

## Question Type Comparison

| Type | Attribute | API Endpoint | Payload |
|------|-----------|--------------|---------|
| **Standard** | `attribute != 'speech_parameter'` | NLP API `/extract_information` | Text + prompts |
| **Speech Parameter** | `attribute = 'speech_parameter'` | GPU STT `/file_stt_features` (port 4030) | Audio + transcripts |

---

## API Configuration

**Endpoint:** `/file_stt_features` (already configured as `LID_API_ENDPOINT`)

**Port:** 4030 (already configured as `LID_PORT`)

**Access:** Via GPU mediator (like LID/STT stages)

> [!NOTE]
> Speech parameter questions reuse the existing LID endpoint configuration. No new environment variables needed.

---

## Implementation Steps

### 1. llm2_stage.py

**No config.py or .env changes needed** - uses existing `LID_PORT` and `LID_API_ENDPOINT`

#### New Method: `_build_transcript_chunks(call_id)`
```python
def _build_transcript_chunks(self, call_id: int) -> List[Dict]:
    """Build transcript chunks in required format."""
    transcripts = self.transcript_repo.get_by_call_id(call_id)
    all_chunks = []
    for row in transcripts:
        chunk = {
            'start_time': row['startTime'],
            'end_time': row['endTime'],
            'speaker': row['speaker'],
            'transcript': row['text']
        }
        all_chunks.append(chunk)
    return all_chunks
```

#### New Method: `answer_speech_parameter_question(call_record, question)`
```python
async def answer_speech_parameter_question(
    self, 
    call_record: Dict, 
    question: Dict,
    gpu_ip: str
) -> str:
    """Answer speech parameter question via GPU STT API."""
    
    # Build payload
    payload = {
        "file_name": call_record['audioName'],
        "file_url": call_record.get('audioUrl', ''),
        "entity": question.get('intents', ''),
        "response": self._build_transcript_chunks(call_record['id'])
    }
    
    # Call GPU via mediator
    response = await self.mediator.call_api(
        gpu_ip,
        self.settings.lid_port,  # Port 4030
        self.settings.lid_api_endpoint,  # /file_stt_features
        payload
    )
    
    # Extract result
    if 'data' in response:
        result = response['data']['derived_value'][0]['results']
        return result if result else 'NA'
    
    return 'NA'
```

> [!IMPORTANT]
> Uses `mediator_client.call_api()` to route through GPU mediator, same as LID/STT stages.

#### Update `process_call()` loop:
```python
# Get GPU IP for this call (from fileDistribution or call record)
gpu_ip = call_record.get('ip', self.settings.gpu_machine_list[0])

for question in audit_form_questions:
    question_name = question.get('name', '')
    attribute = question.get('attribute', '')
    
    # Check skip
    if question_name in skip_list:
        continue
    
    # Check NA
    if question_name in na_list:
        answer = 'NA'
    # Check speech parameter
    elif attribute == 'speech_parameter':
        answer = await self.answer_speech_parameter_question(
            call_record, 
            question, 
            gpu_ip
        )
    # Standard question
    else:
        answer = await self.answer_question(transcript_text, language, question)
    
    # ... build and insert answer_record
```

---

## Data Flow Diagram

```
Question Processing
    │
    ├── Skip? → Continue
    │
    ├── NA? → answer = 'NA'
    │
    ├── attribute = 'speech_parameter'?
    │       │
    │       ├── Build transcript chunks
    │       ├── Build GPU API payload
    │       ├── Call via mediator → GPU:4030/file_stt_features
    │       └── Extract result → answer
    │
    └── Standard question?
            │
            ├── Call NLP API
            └── Extract result → answer
```

---

## Payload Structure

### Standard Question (NLP API)
```json
{
  "text": "transcript_text",
  "text_language": "hi",
  "prompts": [...],
  "additional_params": {}
}
```

### Speech Parameter Question (GPU STT API)
```json
{
  "file_name": "audio.wav",
  "file_url": "http://example.com/audio.wav",
  "entity": "emotion_detection",
  "response": [
    {
      "start_time": 0.0,
      "end_time": 2.5,
      "speaker": "Speaker 1",
      "transcript": "Hello"
    }
  ]
}
```

**Routed via mediator to:** `http://<gpu_ip>:4030/file_stt_features`

---

## Task List

- [ ] Add `mediator_client` to LLM2Stage.__init__()
- [ ] Create `_build_transcript_chunks()` method
- [ ] Create `answer_speech_parameter_question()` method
- [ ] Update `process_call()` to check `attribute='speech_parameter'`
- [ ] Get GPU IP from call record
- [ ] Test with speech parameter questions
