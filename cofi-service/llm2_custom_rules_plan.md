# LLM2 Custom Rules Feature - Implementation Plan

## Goal
Create a client-specific custom rules file where you can hardcode question names and define custom logic (either database queries OR custom NLP API handling).

---

## Use Cases

### Case 1: Database Logic (No NLP API)
- **Question:** "Is the price below 15 or quantity above 25000 highlighted and flagged?"
- **Logic:** Query `callConversation` table, check conditions
- **Answer:** YES/NO based on DB data

### Case 2: Custom NLP API Call
- **Question:** "Was there proper greeting?"
- **Logic:** Call NLP API with custom prompt/parameters
- **Answer:** Process response with custom rules

**Key Point:** The custom file allows you to override default behavior for specific client questions.

---

## Architecture

### File Structure
```
cofi-service/src/
├── pipeline/
│   ├── llm2_stage.py
│   └── llm2_custom_rules.py  # ← New file
```

### Custom Rules File (`llm2_custom_rules.py`)

```python
"""Custom rules for client-specific LLM2 questions."""
from typing import Dict, Optional
import structlog

logger = structlog.get_logger()

class CallConversationRepo:
    """Repository for callConversation table."""
    
    def __init__(self, db):
        self.db = db
    
    def get_by_call_id(self, call_id: int):
        """Get call conversation records."""
        query = "SELECT lotQuantity, tradePrice FROM callConversation WHERE callId = %s"
        return self.db.execute_query(query, (call_id,))


class CustomRuleExecutor:
    """Execute custom rules for specific questions."""
    
    def __init__(self, db, nlp_caller):
        self.db = db
        self.nlp_caller = nlp_caller  # Reference to LLM2Stage for NLP calls
        self.call_conv_repo = CallConversationRepo(db)
        
        # Map question names to custom rule functions
        self.custom_rules = {
            # Database logic rules
            "Is the price below 15 or quantity above 25000 highlighted and flagged?": self.quantity_check,
            "What type of trade was discussed?": self.trade_type_check,  # Options/Futures/Equity
            
            # Custom NLP rule (can add more)
            # "Was there proper greeting?": self.custom_nlp_check,
        }
    
    def has_custom_rule(self, question_name: str) -> bool:
        """Check if question has a custom rule."""
        return question_name in self.custom_rules
    
    async def execute(self, question_name: str, call_record: Dict, question: Dict, transcript_text: str, language: str) -> Optional[str]:
        """Execute custom rule and return answer."""
        if question_name not in self.custom_rules:
            return None
        
        try:
            rule_func = self.custom_rules[question_name]
            # Rules can be sync (DB) or async (NLP)
            if asyncio.iscoroutinefunction(rule_func):
                return await rule_func(call_record, question, transcript_text, language)
            else:
                return rule_func(call_record['id'])
        except Exception as e:
            logger.error("custom_rule_failed", question=question_name, error=str(e))
            return 'NA'
    
    # Example: Database logic rule 1
    def quantity_check(self, call_id: int) -> str:
        """Check if quantity >= 25000 or price < 5."""
        records = self.call_conv_repo.get_by_call_id(call_id)
        
        if not records:
            return 'NA'
        
        try:
            for row in records:
                lot_quantity = row.get('lotQuantity', 0)
                trade_price = row.get('tradePrice', 0)
                
                if int(lot_quantity) >= 25000 or int(trade_price) < 5:
                    return 'YES'
            
            return 'NO'
        except Exception as e:
            logger.error("quantity_check_failed", call_id=call_id, error=str(e))
            return 'NA'
    
    # Example: Database logic rule 2
    def trade_type_check(self, call_id: int) -> str:
        """Determine trade type: Options, Futures, or Equity/Cash."""
        query = """
            SELECT optionType, lotQuantity, strikePrice, expiryDate, 
                   tradeDate, tradePrice, buySell 
            FROM callConversation 
            WHERE callId = %s
        """
        records = self.db.execute_query(query, (call_id,))
        
        if not records:
            return 'NA'
        
        try:
            for row in records:
                option_type = row.get('optionType', '')
                lot_quantity = row.get('lotQuantity', '')
                strike_price = row.get('strikePrice', '')
                expiry_date = row.get('expiryDate', '')
                trade_date = row.get('tradeDate', '')
                trade_price = row.get('tradePrice', '')
                buy_sell = row.get('buySell', '')
                
                # Helper to check if field is valid
                def is_valid(field):
                    return field and str(field) not in ['', 'None', 'none', 'NA', 'na']
                
                # Check for Options: optionType + lotQuantity + strikePrice + expiryDate
                if is_valid(option_type) and is_valid(lot_quantity) and is_valid(strike_price) and is_valid(expiry_date):
                    return 'Options'
                
                # Check for Futures: lotQuantity + expiryDate (no optionType, no strikePrice)
                elif not is_valid(option_type) and is_valid(lot_quantity) and not is_valid(strike_price) and is_valid(expiry_date):
                    return 'Futures'
                
                # Check for Equity/Cash: tradeDate or tradePrice or buySell
                elif is_valid(trade_date) or is_valid(trade_price) or is_valid(buy_sell):
                    return 'Equity/Cash'
            
            return 'NA'
        except Exception as e:
            logger.error("trade_type_check_failed", call_id=call_id, error=str(e))
            return 'NA'
    
    # Example: Custom NLP rule (commented - add as needed)
    # async def custom_nlp_check(self, call_record: Dict, question: Dict, transcript_text: str, language: str) -> str:
    #     """Custom NLP logic with specific prompt handling."""
    #     # Can call NLP API with custom parameters
    #     result = await self.nlp_caller.call_nlp_api({
    #         "text": transcript_text,
    #         "text_language": language,
    #         "prompts": [{"entity": "custom", "prompts": ["Custom prompt"], "type": "multiple"}]
    #     })
    #     
    #     # Custom response processing
    #     if 'data' in result:
    #         # Your custom logic here
    #         return 'YES'
    #     return 'NO'
```

## LLM2 Stage Updates

### In `__init__()`:
```python
from .llm2_custom_rules import CustomRuleExecutor

def __init__(self):
    # ... existing code ...
    self.custom_rules = CustomRuleExecutor(self.db, self)  # Pass self for NLP access
```

### In `process_call()` loop:
```python
for question in audit_form_questions:
    question_name = question.get('name', '')
    attribute = question.get('attribute', '')
    
    # Check skip
    if question_name in skip_list:
        continue
    
    # Check NA
    if question_name in na_list:
        answer = 'NA'
    # Check custom rules (can be DB or NLP)
    elif self.custom_rules.has_custom_rule(question_name):
        logger.info("executing_custom_rule", question_name=question_name)
        answer = await self.custom_rules.execute(
            question_name, 
            call_record,
            question,
            transcript_text,
            language
        )
    # Check speech parameter
    elif attribute == 'speech_parameter':
        answer = await self.answer_speech_parameter_question(...)
    # Standard question
    else:
        answer = await self.answer_question(...)
    
    # Build answer_record...
```

---

## Question Processing Order

```
For each question:
    │
    ├── 1. Skip? → Continue (no record)
    │
    ├── 2. NA? → answer = 'NA'
    │
    ├── 3. Custom Rule? → Execute custom function
    │
    ├── 4. Speech Parameter? → GPU API
    │
    └── 5. Standard? → NLP API
```

---

## Benefits

✅ **Client-specific logic** - Isolated in one file
✅ **No NLP API calls** - Direct database queries
✅ **Easy to extend** - Just add to `custom_rules` dict
✅ **Type safety** - Structured repository pattern
✅ **Maintainable** - Clear separation of concerns

---

## Adding New Custom Rules

1. Add function to `CustomRuleExecutor` class
2. Map question name to function in `custom_rules` dict
3. No changes to main pipeline code!

Example:
```python
self.custom_rules = {
    "Question 1": self.quantity_check,
    "Question 2": self.new_rule_function,  # ← Add here
}

def new_rule_function(self, call_id: int) -> str:
    # Custom logic here
    return 'YES' or 'NO'
```

---

## Implementation Steps

1. Create `llm2_custom_rules.py` with:
   - `CallConversationRepo`
   - `CustomRuleExecutor` class
   - `quantity_check` function

2. Update `llm2_stage.py`:
   - Import `CustomRuleExecutor`
   - Initialize in `__init__()`
   - Add custom rule check in question loop

3. Test with quantity check question

---

## Task List

- [ ] Create `llm2_custom_rules.py`
- [ ] Add `CallConversationRepo` 
- [ ] Add `CustomRuleExecutor` class
- [ ] Implement `quantity_check` rule
- [ ] Update `llm2_stage.py` imports
- [ ] Add custom rule check in loop
- [ ] Test with sample data
