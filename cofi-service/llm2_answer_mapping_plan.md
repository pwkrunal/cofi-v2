# LLM2 Answer Mapping Feature - Implementation Plan

## Goal
Add conditional answer mapping in LLM2 stage to normalize specific API responses into standardized answer formats.

---

## Use Case

When NLP API returns certain values, map them to standardized answers:
- `"dealer"` → `"Dealer"`
- `"client"` → `"Client"`
- `"both"` → `"Both client & dealer"`
- `"yes"` → `"YES"`
- `"no"` → `"NO"`
- `"na"` → `"NA"`

---

## Current Behavior

In `answer_question()` method, we only check for YES/NO/NA:
```python
result_lower = str(result).lower()

if result_lower == "yes":
    return 'YES'
elif result_lower == "no":
    return 'NO'
elif result_lower == "na":
    return 'NA'
else:
    return 'NA'  # Default
```

---

## Proposed Solution

### Option 1: Inline Mapping (Simple)
Extend the existing if-elif chain in `answer_question()`:

```python
result_lower = str(result).lower()

if result_lower == "yes":
    return 'YES'
elif result_lower == "no":
    return 'NO'
elif result_lower == "na":
    return 'NA'
elif result_lower == "dealer":
    return 'Dealer'
elif result_lower == "client":
    return 'Client'
elif result_lower == "both":
    return 'Both client & dealer'
else:
    return result  # Return original result if no mapping
```

**Pros:** Simple, no config needed
**Cons:** Hard-coded mappings

---

### Option 2: Configurable Mapping Dictionary (Flexible)

Add a mapping dictionary in the class:

```python
class LLM2Stage:
    
    def __init__(self):
        # ... existing init ...
        
        # Answer mappings
        self.answer_mappings = {
            'yes': 'YES',
            'no': 'NO',
            'na': 'NA',
            'dealer': 'Dealer',
            'client': 'Client',
            'both': 'Both client & dealer'
        }
    
    async def answer_question(...):
        # ... get result ...
        
        result_lower = str(result).lower()
        
        # Check mapping
        if result_lower in self.answer_mappings:
            return self.answer_mappings[result_lower]
        else:
            return result  # Return original if no mapping
```

**Pros:** Easy to extend, centralized
**Cons:** Still hard-coded in class

---

### Option 3: Environment Variable Mapping (Most Flexible)

Add to `.env`:
```env
LLM2_ANSWER_MAPPINGS=dealer:Dealer,client:Client,both:Both client & dealer
```

In `config.py`:
```python
llm2_answer_mappings: str = Field(default="")

@property
def llm2_answer_mapping_dict(self) -> Dict[str, str]:
    """Parse answer mappings."""
    mappings = {}
    if self.llm2_answer_mappings:
        for pair in self.llm2_answer_mappings.split(','):
            if ':' in pair:
                key, val = pair.split(':', 1)
                mappings[key.strip().lower()] = val.strip()
    # Add defaults
    mappings.update({
        'yes': 'YES',
        'no': 'NO',
        'na': 'NA'
    })
    return mappings
```

In `llm2_stage.py`:
```python
async def answer_question(...):
    # ... get result ...
    
    result_lower = str(result).lower()
    mappings = self.settings.llm2_answer_mapping_dict
    
    if result_lower in mappings:
        return mappings[result_lower]
    else:
        return result  # Return original
```

**Pros:** Fully configurable, no code changes for new mappings
**Cons:** More complex

---

## Recommended Approach

**Option 2** (Configurable Dictionary) - Good balance of flexibility and simplicity.

If more flexibility is needed later, can upgrade to Option 3.

---

## Implementation Steps

### Using Option 2:

1. **Update `LLM2Stage.__init__()`**
   - Add `self.answer_mappings` dictionary

2. **Update `answer_question()` method**
   - Replace if-elif chain with dictionary lookup
   - Return original result if no mapping found

3. **Test with various responses**
   - Test: "dealer", "client", "both", "yes", "no", "na"
   - Test: Unknown values (should return original)

---

## Code Changes

| File | Changes |
|------|---------|
| `llm2_stage.py` | Add answer_mappings dict, update answer_question() |

---

## Task List

- [ ] Add `answer_mappings` dictionary to `LLM2Stage.__init__()`
- [ ] Update `answer_question()` to use dictionary lookup
- [ ] Test with dealer/client/both responses
- [ ] Update documentation if needed
