# LLM2 Skip Questions Feature - Implementation Plan

## Goal
Allow skipping certain audit questions in LLM2 stage based on question names configured in environment variable.

---

## Environment Variable

```env
# Comma-separated list of question names to skip
LLM2_SKIP_QUESTIONS=question_name_1,question_name_2,trade_confirmation
```

---

## Implementation Steps

### 1. config.py
- Add `llm2_skip_questions: str = Field(default="")` 
- Add property to parse into list: `llm2_skip_question_list`

### 2. llm2_stage.py
- Load skip questions list from config
- When iterating audit form questions:
  - Check if `question['name']` in skip list
  - If yes: skip calling NLP API, mark answer as "Skipped" or don't insert
  - If no: process normally

---

## Code Change Locations

| File | Changes |
|------|---------|
| `config.py` | Add `llm2_skip_questions` field |
| `.env.example` | Add `LLM2_SKIP_QUESTIONS=` |
| `llm2_stage.py` | Add skip logic in question loop |

---

## Logic Flow

```
For each question in audit_form:
    │
    ├── IF question['name'] in skip_list:
    │       └── Log "skipping question X"
    │       └── Continue to next question
    │
    └── ELSE:
            └── Call NLP API
            └── Store answer
```

---

## Task List

- [ ] Add `LLM2_SKIP_QUESTIONS` to config.py
- [ ] Add `LLM2_SKIP_QUESTIONS=` to .env.example  
- [ ] Update llm2_stage.py to check skip list before processing each question
- [ ] Test with sample skip questions
