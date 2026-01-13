# LLM2 NA Questions Feature - Implementation Plan

## Goal
Allow certain audit questions to have a straight "NA" answer in LLM2 stage, without calling the NLP API.

---

## Difference from Skip Questions

| Feature | Behavior |
|---------|----------|
| **Skip Questions** | No record inserted, question completely ignored |
| **NA Questions** | Record inserted with answer = 'NA', no API call |

---

## Environment Variable

```env
# Comma-separated list of question names to mark as NA
LLM2_NA_QUESTIONS=question_name_1,question_name_2
```

---

## Implementation Steps

### 1. config.py
- Add `llm2_na_questions: str = Field(default="")`
- Add property: `llm2_na_question_list`

### 2. .env.example
- Add `LLM2_NA_QUESTIONS=`

### 3. llm2_stage.py
- Load NA questions list from config
- In question loop (trade case):
  - Check if `question['name']` in skip_list → continue (skip)
  - Check if `question['name']` in na_list → answer = 'NA' (no API call)
  - Else → call NLP API as normal

---

## Code Change Locations

| File | Changes |
|------|---------|
| `config.py` | Add `llm2_na_questions` field + property |
| `.env.example` | Add `LLM2_NA_QUESTIONS=` |
| `llm2_stage.py` | Add NA check logic in question loop |

---

## Logic Flow

```
For each question in audit_form:
    │
    ├── IF question['name'] in skip_list:
    │       └── Continue (no record)
    │
    ├── ELIF question['name'] in na_list:
    │       └── answer = 'NA' (insert record, no API call)
    │
    └── ELSE:
            └── Call NLP API → get answer
            └── Insert record
```

---

## Task List

- [ ] Add `LLM2_NA_QUESTIONS` to config.py
- [ ] Add `LLM2_NA_QUESTIONS=` to .env.example
- [ ] Update llm2_stage.py with NA logic
- [ ] Test with sample NA questions
