"""LLM1 (First LLM extraction) processing stage."""
from typing import Dict, Any, List, Optional
import aiohttp
import asyncio
import json
import structlog

from ..config import get_settings
from ..database import CallRepo, TranscriptRepo, ProcessingLogRepo, FileDistributionRepo, get_database
from ..webhook_client import get_webhook_client
from ..event_logger import EventLogger

logger = structlog.get_logger()


def _safe_json_serialize(data: Any) -> Optional[str]:
    """Safely serialize data to JSON string, returning None on failure."""
    if data is None:
        return None
    try:
        return json.dumps(data, default=str)
    except (TypeError, ValueError):
        return str(data)


class TradeAudioMappingRepo:
    """Repository for reading tradeAudioMapping table."""
    
    def __init__(self, db):
        self.db = db
    
    def get_by_audio_file(self, audio_file_name: str) -> List[Dict]:
        """Get trade mappings for an audio file."""
        query = "SELECT * FROM tradeAudioMapping WHERE audioFileName = %s"
        return self.db.execute_query(query, (audio_file_name,))


class CallConversationRepo:
    """Repository for callConversation table operations."""
    
    def __init__(self, db):
        self.db = db
    
    def insert(
        self,
        call_id: int,
        script_name: str,
        option_type: str,
        lot_quantity: int,
        strike_price: float,
        trade_date: str,
        expiry_date: str,
        trade_price: float,
        buy_sell: str,
        current_market_price: float,
        batch_id: int
    ) -> int:
        """Insert a callConversation record."""
        query = """
            INSERT INTO callConversation (
                callId, scriptName, optionType, lotQuantity, strikePrice,
                tradeDate, expiryDate, tradePrice, buySell, currentMarketPrice, batchId
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        return self.db.execute_insert(query, (
            call_id, script_name, option_type, lot_quantity, strike_price,
            trade_date, expiry_date, trade_price, buy_sell, current_market_price, batch_id
        ))
    
    def insert_many(self, records: List[Dict]) -> int:
        """Insert multiple callConversation records."""
        if not records:
            return 0
        
        query = """
            INSERT INTO callConversation (
                callId, scriptName, optionType, lotQuantity, strikePrice,
                tradeDate, expiryDate, tradePrice, buySell, currentMarketPrice, batchId
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        params_list = []
        for r in records:
            params = (
                r.get('callId'),
                r.get('scriptName'),
                r.get('optionType'),
                r.get('lotQuantity', 0),
                r.get('strikePrice', 0),
                r.get('tradeDate'),
                r.get('expiryDate'),
                r.get('tradePrice', 0),
                r.get('buySell'),
                r.get('currentMarketPrice', 0),
                r.get('batchId')
            )
            params_list.append(params)
        
        return self.db.execute_many(query, params_list)


class LLM1Stage:
    """
    First LLM extraction stage - processes TranscriptDone calls.

    Calls NLP_API_Q1/extract_information with:
    - text: concatenated transcript from transcript table
    - text_language: from call table
    - prompts: [""]
    - additional_params.trade_details: from tradeAudioMapping table
    """

    stage_name = "LLM1"
    processing_log_stage = "llm1"  # For processing_logs table

    def __init__(self):
        self.settings = get_settings()
        self.db = get_database()
        self.call_repo = CallRepo(self.db)
        self.transcript_repo = TranscriptRepo(self.db)
        self.trade_audio_repo = TradeAudioMappingRepo(self.db)
        self.call_conversation_repo = CallConversationRepo(self.db)
        self.processing_log_repo = ProcessingLogRepo(self.db)
        self.file_dist_repo = FileDistributionRepo(self.db)

        # Build full API URL
        self.api_url = f"{self.settings.nlp_api_q1}/extract_information"
        self.timeout = aiohttp.ClientTimeout(total=600)

    def log_processing_failure(
        self,
        call_id: str,
        batch_id: int,
        error_message: str,
        input_payload: Optional[Dict] = None,
        output_payload: Optional[Dict] = None
    ):
        """Log failed processing to processing_logs table."""
        try:
            self.processing_log_repo.log_failure(
                call_id=call_id,
                batch_id=str(batch_id),
                stage_name=self.processing_log_stage,
                error_message=error_message,
                request_url=self.api_url,
                input_payload=_safe_json_serialize(input_payload),
                output_payload=_safe_json_serialize(output_payload)
            )
        except Exception as e:
            logger.error("processing_log_failed", stage=self.stage_name, call_id=call_id, error=str(e))
    
    def _get_transcript_text(self, call_id: int) -> str:
        """Get concatenated transcript text for a call."""
        transcripts = self.transcript_repo.get_by_call_id(call_id)
        
        # Concatenate all transcript text in order
        texts = []
        for t in transcripts:
            speaker = t.get('speaker', '')
            text = t.get('text', '')
            if text:
                texts.append(f"{speaker}: {text}")
        
        return "\n".join(texts)
    
    def _get_stock_details(self, audio_file_name: str) -> List[Dict]:
        """Get trade details for an audio file."""
        trades = self.trade_audio_repo.get_by_audio_file(audio_file_name)
        
        stock_details = []
        for trade in trades:
            stock_details.append({
                "symbol": trade.get('symbol'),
                "strikePrice": trade.get('strikePrice'),
                "tradeQuantity": trade.get('tradeQuantity'),
                "tradePrice": trade.get('tradePrice'),
                "buySell": trade.get('buySell'),
                "scripName": trade.get('scripName')
            })
        
        return stock_details
    
    def build_payload(self, call_record: Dict) -> Dict[str, Any]:
        """Build NLP API payload with transcript and trade details."""
        call_id = call_record['id']
        audio_name = call_record['audioName']
        language = call_record.get('lang', 'hi')
        
        # Get transcript text
        transcript_text = self._get_transcript_text(call_id)
        
        # Get trade details
        stock_details = self._get_stock_details(audio_name)
        
        payload = {
            "text": transcript_text,
            "text_language": language,
            "prompts": [""],
            "additional_params": {
                "trade_details": stock_details
            }
        }
        
        return payload
    
    async def call_nlp_api(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Call the NLP API directly (not via GPU mediator)."""
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            try:
                async with session.post(self.api_url, json=payload) as resp:
                    result = await resp.json()
                    logger.info("nlp_api_called", status=resp.status)
                    return result
            except Exception as e:
                logger.error("nlp_api_failed", error=str(e))
                raise
    
    def _safe_get_value(self, item: Dict, key: str, default=0):
        """Safely get value from dict, handling 'NA' strings."""
        value = item.get(key)
        if value is None or value == "NA" or value == "":
            return default
        return value
    
    def process_response(self, call_record: Dict, response: Dict[str, Any]):
        """
        Process LLM1 API response.
        Store extraction results in callConversation table.
        Update call table status from 'TranscriptDone' to 'AuditDone'.
        """
        audio_name = call_record['audioName']
        call_id = call_record['id']
        batch_id = call_record['batchId']
        
        try:
            # Parse NLP response
            if 'data' in response:
                derived_value = response.get("data", {}).get("derived_value", [])
                if derived_value and len(derived_value) > 0:
                    result = derived_value[0].get("result")
                    
                    if result and result != "NA" and isinstance(result, list):
                        records_to_insert = []
                        
                        for item in result:
                            # Extract fields with NA handling
                            script_name = self._safe_get_value(item, "scriptName", "")
                            option_type = self._safe_get_value(item, "optionType", "")
                            
                            # Handle lot/quantity
                            quantity = 0
                            if "lot/quantity" in item:
                                qty_val = item["lot/quantity"]
                                if qty_val and qty_val != "NA":
                                    try:
                                        quantity = int(qty_val)
                                    except (ValueError, TypeError):
                                        quantity = 0
                            
                            strike_price = self._safe_get_value(item, "strikePrice", 0)
                            if strike_price != 0:
                                try:
                                    strike_price = float(strike_price)
                                except (ValueError, TypeError):
                                    strike_price = 0
                            
                            trade_date = self._safe_get_value(item, "tradeDate", "")
                            expiry_date = self._safe_get_value(item, "expiryDate", "")
                            
                            trade_price = self._safe_get_value(item, "tradePrice", 0)
                            if trade_price != 0:
                                try:
                                    trade_price = float(trade_price)
                                except (ValueError, TypeError):
                                    trade_price = 0
                            
                            buy_sell = self._safe_get_value(item, "buySell", "")
                            
                            current_market_price = 0
                            if "currentMarket" in item:
                                cmp_val = item["currentMarket"]
                                if cmp_val and cmp_val != "NA":
                                    try:
                                        current_market_price = float(cmp_val)
                                    except (ValueError, TypeError):
                                        current_market_price = 0
                            
                            record = {
                                'callId': call_id,
                                'scriptName': script_name,
                                'optionType': option_type,
                                'lotQuantity': quantity,
                                'strikePrice': strike_price,
                                'tradeDate': trade_date,
                                'expiryDate': expiry_date,
                                'tradePrice': trade_price,
                                'buySell': buy_sell,
                                'currentMarketPrice': current_market_price,
                                'batchId': batch_id
                            }
                            records_to_insert.append(record)
                        
                        # Bulk insert
                        if records_to_insert:
                            count = self.call_conversation_repo.insert_many(records_to_insert)
                            logger.info("call_conversation_inserted", 
                                       file=audio_name, 
                                       count=count)
            
        except Exception as e:
            logger.error("process_response_failed", file=audio_name, error=str(e))
        
        # Update call status
        self.call_repo.update_status(audio_name, "TranscriptDone", "AuditDone")
        logger.info("llm1_status_updated", file=audio_name, new_status="AuditDone")

        # Send webhook notification
        try:
            webhook_client = get_webhook_client()
            webhook_client.notify_call_status(call_id, "AuditDone")
        except Exception as webhook_err:
            logger.error("webhook_failed", call_id=call_id, status="AuditDone", error=str(webhook_err))
    
    async def execute(self, batch_id: int, previous_container: Optional[str] = None):
        """
        Execute LLM1 stage with parallel API calls.

        Note: This stage calls external NLP API directly, not via GPU mediator.
        """
        logger.info("llm1_stage_starting", batch_id=batch_id)

        # Get calls with status='TranscriptDone'
        call_records = self.call_repo.get_by_status(batch_id, "TranscriptDone")

        if not call_records:
            logger.info("no_pending_calls_for_llm1")
            return

        total_files = len(call_records)
        logger.info("calls_to_process", count=total_files)

        # Log stage start
        EventLogger.stage_start(batch_id, 'llm1', total_files=total_files, metadata={
            'api_url': self.api_url,
            'max_concurrent': len(self.settings.gpu_machine_list)
        })

        # Semaphore to limit concurrent API calls based on GPU count
        max_concurrent = len(self.settings.gpu_machine_list)
        semaphore = asyncio.Semaphore(max_concurrent)

        async def process_single_call(call_record):
            """Process a single call with concurrency limit."""
            async with semaphore:
                audio_name = call_record['audioName']
                batch_id = call_record['batchId']
                payload = None
                response = None

                try:
                    # Build payload with transcript and trade details
                    payload = self.build_payload(call_record)

                    # Skip if no transcript
                    if not payload['text']:
                        logger.warning("no_transcript_skipping", file=audio_name)
                        self.log_processing_failure(
                            call_id=audio_name,
                            batch_id=batch_id,
                            error_message="No transcript found - skipping",
                            input_payload=payload
                        )
                        EventLogger.file_error(batch_id, 'llm1', audio_name, "No transcript found - skipping")
                        return False, audio_name

                    # Call NLP API
                    response = await self.call_nlp_api(payload)

                    # Process response
                    self.process_response(call_record, response)
                    EventLogger.file_complete(batch_id, 'llm1', audio_name, status='success')
                    return True, audio_name

                except Exception as e:
                    logger.error("llm1_processing_failed",
                               file=audio_name,
                               error=str(e))
                    # Log failure to processing_logs - continues without stopping
                    self.log_processing_failure(
                        call_id=audio_name,
                        batch_id=batch_id,
                        error_message=str(e),
                        input_payload=payload,
                        output_payload=response
                    )
                    EventLogger.file_error(batch_id, 'llm1', audio_name, str(e))
                    return False, audio_name

        # Create tasks for all calls
        tasks = [process_single_call(record) for record in call_records]

        # Execute all in parallel (with concurrency limit)
        logger.info("llm1_processing_parallel", max_concurrent=max_concurrent)
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Count successes and track successful files
        successful_files = []
        failed = 0
        
        for result in results:
            if isinstance(result, Exception):
                failed += 1
            elif isinstance(result, tuple):
                success, audio_name = result
                if success:
                    successful_files.append(audio_name)
                else:
                    failed += 1

        successful = len(successful_files)

        # Mark successful files as complete in fileDistribution
        if successful_files:
            self.file_dist_repo.mark_stage_done(successful_files, batch_id, 'llm1Done')
            logger.info("files_marked_llm1_complete", count=len(successful_files))

        # Log stage complete
        EventLogger.stage_complete(batch_id, 'llm1', successful, failed, metadata={
            'total_files': total_files
        })

        logger.info("llm1_stage_completed", successful=successful, failed=failed)
