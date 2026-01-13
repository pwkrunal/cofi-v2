"""Custom rules for client-specific LLM2 audit questions."""
from typing import Dict, Optional
import asyncio
import structlog

logger = structlog.get_logger()


class CallConversationRepo:
    """Repository for callConversation table operations."""
    
    def __init__(self, db):
        self.db = db
    
    def get_by_call_id(self, call_id: int):
        """Get call conversation records for a call."""
        query = """
            SELECT optionType, lotQuantity, strikePrice, expiryDate, 
                   tradeDate, tradePrice, buySell 
            FROM callConversation 
            WHERE callId = %s
        """
        return self.db.execute_query(query, (call_id,))


class CustomRuleExecutor:
    """
    Execute custom rules for specific audit questions.
    
    Supports both database logic and custom NLP API calls.
    Add new rules by adding entries to the custom_rules dictionary.
    """
    
    def __init__(self, db, nlp_caller):
        self.db = db
        self.nlp_caller = nlp_caller  # Reference to LLM2Stage for NLP API access
        self.call_conv_repo = CallConversationRepo(db)
        
        # Map question names to custom rule functions
        self.custom_rules = {
            # Database logic rules
            "Is the price below 15 or quantity above 25000 highlighted and flagged?": self.quantity_check,
            "What type of trade was discussed?": self.trade_type_check,
            
            # Custom NLP rules can be added here
            # "Question name": self.custom_nlp_function,
        }
    
    def has_custom_rule(self, question_name: str) -> bool:
        """Check if a question has a custom rule defined."""
        return question_name in self.custom_rules
    
    async def execute(
        self, 
        question_name: str, 
        call_record: Dict, 
        question: Dict, 
        transcript_text: str, 
        language: str
    ) -> Optional[str]:
        """
        Execute custom rule and return answer.
        
        Supports both sync (database) and async (NLP) rule functions.
        """
        if question_name not in self.custom_rules:
            return None
        
        try:
            rule_func = self.custom_rules[question_name]
            
            # Check if function is async (NLP) or sync (DB)
            if asyncio.iscoroutinefunction(rule_func):
                return await rule_func(call_record, question, transcript_text, language)
            else:
                return rule_func(call_record['id'])
                
        except Exception as e:
            logger.error("custom_rule_execution_failed", 
                        question=question_name, 
                        call_id=call_record.get('id'),
                        error=str(e))
            return 'NA'
    
    # ===== DATABASE LOGIC RULES =====
    
    def quantity_check(self, call_id: int) -> str:
        """
        Check if quantity >= 25000 or price < 5.
        
        Returns: 'YES' if condition met, 'NO' otherwise
        """
        records = self.call_conv_repo.get_by_call_id(call_id)
        
        if not records:
            return 'NA'
        
        try:
            for row in records:
                lot_quantity = row.get('lotQuantity', 0)
                trade_price = row.get('tradePrice', 0)
                
                # Convert to int for comparison
                try:
                    qty = int(lot_quantity) if lot_quantity else 0
                    price = int(trade_price) if trade_price else 0
                    
                    if qty >= 25000 or price < 5:
                        return 'YES'
                except (ValueError, TypeError):
                    continue
            
            return 'NO'
            
        except Exception as e:
            logger.error("quantity_check_failed", call_id=call_id, error=str(e))
            return 'NA'
    
    def trade_type_check(self, call_id: int) -> str:
        """
        Determine trade type based on callConversation data.
        
        Returns: 'Options', 'Futures', 'Equity/Cash', or 'NA'
        """
        records = self.call_conv_repo.get_by_call_id(call_id)
        
        if not records:
            return 'NA'
        
        def is_valid(field) -> bool:
            """Check if field has a valid value."""
            if not field:
                return False
            field_str = str(field).strip().lower()
            return field_str not in ['', 'none', 'na']
        
        try:
            for row in records:
                option_type = row.get('optionType', '')
                lot_quantity = row.get('lotQuantity', '')
                strike_price = row.get('strikePrice', '')
                expiry_date = row.get('expiryDate', '')
                trade_date = row.get('tradeDate', '')
                trade_price = row.get('tradePrice', '')
                buy_sell = row.get('buySell', '')
                
                # Check for Options: optionType + lotQuantity + strikePrice + expiryDate
                if (is_valid(option_type) and is_valid(lot_quantity) and 
                    is_valid(strike_price) and is_valid(expiry_date)):
                    return 'Options'
                
                # Check for Futures: lotQuantity + expiryDate (no optionType, no strikePrice)
                elif (not is_valid(option_type) and is_valid(lot_quantity) and 
                      not is_valid(strike_price) and is_valid(expiry_date)):
                    return 'Futures'
                
                # Check for Equity/Cash: tradeDate OR tradePrice OR buySell
                elif is_valid(trade_date) or is_valid(trade_price) or is_valid(buy_sell):
                    return 'Equity/Cash'
            
            return 'NA'
            
        except Exception as e:
            logger.error("trade_type_check_failed", call_id=call_id, error=str(e))
            return 'NA'
    
    # ===== CUSTOM NLP RULES (EXAMPLES) =====
    
    # Uncomment and modify as needed for custom NLP logic
    
    # async def custom_nlp_check(
    #     self, 
    #     call_record: Dict, 
    #     question: Dict, 
    #     transcript_text: str, 
    #     language: str
    # ) -> str:
    #     """
    #     Example custom NLP rule with custom prompt handling.
    #     """
    #     try:
    #         # Call NLP API with custom parameters
    #         result = await self.nlp_caller.call_nlp_api({
    #             "text": transcript_text,
    #             "text_language": language,
    #             "prompts": [{
    #                 "entity": "custom_entity",
    #                 "prompts": ["Your custom prompt here"],
    #                 "type": "multiple"
    #             }],
    #             "additional_params": {}
    #         })
    #         
    #         # Custom response processing
    #         if 'data' in result and 'derived_value' in result['data']:
    #             custom_result = result['data']['derived_value'][0]['result']
    #             
    #             # Your custom logic here
    #             if custom_result:
    #                 return 'YES'
    #         
    #         return 'NO'
    #         
    #     except Exception as e:
    #         logger.error("custom_nlp_check_failed", error=str(e))
    #         return 'NA'
