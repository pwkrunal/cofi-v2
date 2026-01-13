"""Rule Engine Step 1 - Trade to Audio Mapping Stage."""
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import structlog

from .config import get_settings
from .database import get_database

logger = structlog.get_logger()


class TradeAudioMappingRepo:
    """Repository for tradeAudioMapping table operations."""
    
    def __init__(self, db):
        self.db = db
    
    def insert(self, record: Dict[str, Any]) -> int:
        """Insert a single tradeAudioMapping record."""
        query = """
            INSERT INTO tradeAudioMapping (
                tradeMetadataId, orderId, clientCode, regNumber, alNumber,
                tradeDate, orderPlacedTime, instType, expiryDate, optionType,
                symbol, comScriptCode, scripName, strikePrice, tradeQuantity,
                tradePrice, tradeValue, lotQty, voiceRecordingConfirmations,
                audioFileName, batchId
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """
        return self.db.execute_insert(query, (
            record.get('tradeMetadataId'),
            record.get('orderId'),
            record.get('clientCode'),
            record.get('regNumber'),
            record.get('alNumber'),
            record.get('tradeDate'),
            record.get('orderPlacedTime'),
            record.get('instType'),
            record.get('expiryDate'),
            record.get('optionType'),
            record.get('symbol'),
            record.get('comScriptCode'),
            record.get('scripName'),
            record.get('strikePrice'),
            record.get('tradeQuantity'),
            record.get('tradePrice'),
            record.get('tradeValue'),
            record.get('lotQty'),
            record.get('voiceRecordingConfirmations'),
            record.get('audioFileName'),
            record.get('batchId')
        ))
    
    def insert_many(self, records: List[Dict[str, Any]]) -> int:
        """Insert multiple tradeAudioMapping records."""
        if not records:
            return 0
        
        query = """
            INSERT INTO tradeAudioMapping (
                tradeMetadataId, orderId, clientCode, regNumber, alNumber,
                tradeDate, orderPlacedTime, instType, expiryDate, optionType,
                symbol, comScriptCode, scripName, strikePrice, tradeQuantity,
                tradePrice, tradeValue, lotQty, voiceRecordingConfirmations,
                audioFileName, batchId
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """
        
        params_list = []
        for record in records:
            params = (
                record.get('tradeMetadataId'),
                record.get('orderId'),
                record.get('clientCode'),
                record.get('regNumber'),
                record.get('alNumber'),
                record.get('tradeDate'),
                record.get('orderPlacedTime'),
                record.get('instType'),
                record.get('expiryDate'),
                record.get('optionType'),
                record.get('symbol'),
                record.get('comScriptCode'),
                record.get('scripName'),
                record.get('strikePrice'),
                record.get('tradeQuantity'),
                record.get('tradePrice'),
                record.get('tradeValue'),
                record.get('lotQty'),
                record.get('voiceRecordingConfirmations'),
                record.get('audioFileName'),
                record.get('batchId')
            )
            params_list.append(params)
        
        return self.db.execute_many(query, params_list)
    
    def get_count_by_batch(self, batch_id: int) -> int:
        """Get count of tradeAudioMapping records for a batch."""
        query = "SELECT COUNT(*) as count FROM tradeAudioMapping WHERE batchId = %s"
        result = self.db.execute_one(query, (batch_id,))
        return result['count'] if result else 0


class RuleEngineStep1:
    """
    Rule Engine Step 1: Trade to Audio Matching.
    
    Loops through tradeMetadata table and finds matching audio files
    from callMetadata based on:
    - alNumber / regNumber matching sClientMobileNumber
    - tradeDate matching callStartDate
    - orderPlacedTime within call start/end time window
    
    Results are inserted into tradeAudioMapping table.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.db = get_database()
        self.trade_audio_repo = TradeAudioMappingRepo(self.db)
        
        # Cache for call metadata
        self._call_metadata: List[Dict] = []
        self._unsupported_files: List[str] = []
    
    def _load_call_metadata(self, batch_id: int):
        """Load callMetadata for the batch with parsed date/time fields."""
        query = "SELECT * FROM callMetadata WHERE batchId = %s"
        rows = self.db.execute_query(query, (batch_id,))
        
        self._call_metadata = []
        for row in rows:
            # Parse callStartDate and callEndDate from dCallStartTime/dCallEndTime
            call_meta = dict(row)
            
            # Add parsed date/time if available
            if call_meta.get('dCallStartTime'):
                try:
                    dt = self._parse_datetime(str(call_meta['dCallStartTime']))
                    if dt:
                        call_meta['callStartDate'] = dt.strftime("%d-%m-%Y")
                        call_meta['callStartTime'] = dt.strftime("%H:%M:%S")
                except:
                    pass
            
            if call_meta.get('dCallEndTime'):
                try:
                    dt = self._parse_datetime(str(call_meta['dCallEndTime']))
                    if dt:
                        call_meta['callEndDate'] = dt.strftime("%d-%m-%Y")
                        call_meta['callEndTime'] = dt.strftime("%H:%M:%S")
                except:
                    pass
            
            self._call_metadata.append(call_meta)
        
        logger.info("call_metadata_loaded", count=len(self._call_metadata))
    
    def _load_unsupported_language_files(self, batch_id: int):
        """Load list of files with unsupported languages."""
        query = """
            SELECT audioName FROM `call` 
            WHERE batchId = %s AND lang NOT IN ('en', 'hi', 'hinglish')
        """
        rows = self.db.execute_query(query, (batch_id,))
        self._unsupported_files = [row['audioName'] for row in rows]
        logger.info("unsupported_files_loaded", count=len(self._unsupported_files))
    
    def _parse_datetime(self, dt_str: str) -> Optional[datetime]:
        """Parse datetime string in various formats."""
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%d-%m-%Y %H:%M:%S",
            "%Y/%m/%d %H:%M:%S",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(dt_str, fmt)
            except ValueError:
                continue
        return None
    
    def _str_to_datetime(self, date_str: str, time_str: str) -> Optional[datetime]:
        """Convert date and time strings to datetime."""
        try:
            return datetime.strptime(f"{date_str} {time_str}", "%d-%m-%Y %H:%M:%S")
        except:
            return None
    
    def _find_matching_trade_step_1(self, trade: Dict, batch_id: int) -> Tuple[List[Dict], Dict]:
        """
        Step 1: Match using regNumber as mobile number.
        Used when alNumber is empty.
        """
        al_number = trade.get('alNumber') or ''
        reg_number = trade.get('regNumber') or ''
        
        # Use regNumber if alNumber is empty
        mobile_number = reg_number
        if mobile_number:
            try:
                mobile_number = str(int(float(mobile_number)))
            except:
                pass
        
        return self._find_matching_calls(trade, batch_id, mobile_number)
    
    def _find_matching_trade_step_2(self, trade: Dict, batch_id: int) -> Tuple[List[Dict], Dict]:
        """
        Step 2: Match using alNumber as mobile number.
        Used when alNumber is present.
        """
        al_number = trade.get('alNumber') or ''
        
        mobile_number = al_number
        if mobile_number:
            try:
                mobile_number = str(int(float(mobile_number)))
            except:
                pass
        
        return self._find_matching_calls(trade, batch_id, mobile_number)
    
    def _find_matching_trade_step_3(self, trade: Dict, batch_id: int) -> Tuple[List[Dict], Dict]:
        """
        Step 3: Match using clientCode as sClientId.
        Used as fallback when mobile number matching fails.
        """
        client_code = str(trade.get('clientCode', '')).strip().lower()
        
        try:
            trade_date_str = trade.get('tradeDate', '')
            order_time_str = trade.get('orderPlacedTime', '')
            
            dt_obj = datetime.strptime(trade_date_str, "%Y%m%d")
            dt_obj_2 = datetime.strptime(order_time_str, "%H%M%S")
            trade_date = dt_obj.strftime("%d-%m-%Y")
            order_time = dt_obj_2.strftime("%H:%M:%S")
            order_datetime = self._str_to_datetime(trade_date, order_time)
            
            if not order_datetime:
                return [], {'tag1': 'No call record found'}
            
            # Match on clientCode (sClientId)
            matching_calls = [
                row for row in self._call_metadata
                if row.get('callStartDate') == trade_date
                and row.get('sClientId')
                and row.get('sClientId', '').lower() == client_code
                and row.get('callStartTime')
                and row.get('callEndTime')
                and row.get('batchId') == batch_id
            ]
            
            # Part 1: Find calls where order is during call
            for call_meta in matching_calls:
                call_start = self._str_to_datetime(call_meta['callStartDate'], call_meta['callStartTime'])
                call_end = self._str_to_datetime(call_meta.get('callEndDate', call_meta['callStartDate']), call_meta['callEndTime'])
                
                if call_start and call_end and call_start <= order_datetime <= call_end:
                    return [call_meta], {'tag1': 'Pre trade found'}
            
            # Part 2: Calls ending before order time (pre-trade)
            pre_trade_calls = [
                row for row in matching_calls
                if row.get('callEndTime', '') < order_time
            ]
            pre_trade_calls.sort(key=lambda x: x.get('callEndTime', ''), reverse=True)
            if pre_trade_calls:
                return pre_trade_calls, {'tag1': 'Pre trade found'}
            
            # Part 3: Calls ending after order time (post-trade)
            post_trade_calls = [
                row for row in matching_calls
                if row.get('callEndTime', '') >= order_time
            ]
            post_trade_calls.sort(key=lambda x: x.get('callEndTime', ''))
            if post_trade_calls:
                return post_trade_calls, {'tag1': 'Post trade found'}
            
        except Exception as e:
            logger.error("matching_step_3_error", error=str(e))
        
        return [], {'tag1': 'No call record found'}
    
    def _find_matching_calls(self, trade: Dict, batch_id: int, mobile_number: str) -> Tuple[List[Dict], Dict]:
        """Common matching logic for Steps 1 and 2."""
        try:
            trade_date_str = trade.get('tradeDate', '')
            order_time_str = trade.get('orderPlacedTime', '')
            
            dt_obj = datetime.strptime(trade_date_str, "%Y%m%d")
            dt_obj_2 = datetime.strptime(order_time_str, "%H%M%S")
            trade_date = dt_obj.strftime("%d-%m-%Y")
            order_time = dt_obj_2.strftime("%H:%M:%S")
            order_datetime = self._str_to_datetime(trade_date, order_time)
            
            if not order_datetime:
                return [], {'tag1': 'No call record found'}
            
            # Filter calls by mobile number and date
            matching_calls = [
                row for row in self._call_metadata
                if row.get('callStartDate') == trade_date
                and row.get('sClientMobileNumber') == mobile_number
                and row.get('callStartTime')
                and row.get('callEndTime')
                and row.get('batchId') == batch_id
            ]
            
            # Part 1: Find calls where order is during call
            for call_meta in matching_calls:
                call_start = self._str_to_datetime(call_meta['callStartDate'], call_meta['callStartTime'])
                call_end = self._str_to_datetime(call_meta.get('callEndDate', call_meta['callStartDate']), call_meta['callEndTime'])
                
                if call_start and call_end and call_start <= order_datetime <= call_end:
                    return [call_meta], {'tag1': 'Pre trade found'}
            
            # Part 2: Calls ending before order time (pre-trade) 
            pre_trade_calls = [
                row for row in matching_calls
                if row.get('callEndTime', '') < order_time
            ]
            pre_trade_calls.sort(key=lambda x: x.get('callEndTime', ''), reverse=True)
            if pre_trade_calls:
                return pre_trade_calls, {'tag1': 'Pre trade found'}
            
            # Part 3: Calls ending after order time (post-trade)
            post_trade_calls = [
                row for row in matching_calls
                if row.get('callEndTime', '') >= order_time
            ]
            post_trade_calls.sort(key=lambda x: x.get('callEndTime', ''))
            if post_trade_calls:
                return post_trade_calls, {'tag1': 'Post trade found'}
            
        except Exception as e:
            logger.error("matching_error", error=str(e))
        
        return [], {'tag1': 'No call record found'}
    
    def _update_trade_metadata(self, trade_id: int, voice_confirmation: str, 
                                audio_file: Optional[str] = None, 
                                audio_call_ref: Optional[int] = None):
        """Update tradeMetadata with matching result."""
        if audio_file and audio_call_ref:
            query = """
                UPDATE tradeMetadata 
                SET voiceRecordingConfirmations = %s, audioFileName = %s, audioCallRef = %s
                WHERE id = %s
            """
            self.db.execute_update(query, (voice_confirmation, audio_file, audio_call_ref, trade_id))
        else:
            query = """
                UPDATE tradeMetadata 
                SET voiceRecordingConfirmations = %s
                WHERE id = %s
            """
            self.db.execute_update(query, (voice_confirmation, trade_id))
    
    def _get_call_id_by_audio_name(self, audio_name: str, batch_id: int) -> Optional[int]:
        """Get call ID from audio name."""
        query = "SELECT id FROM `call` WHERE audioName = %s AND batchId = %s"
        result = self.db.execute_one(query, (audio_name, batch_id))
        return result['id'] if result else None
    
    def process(self, batch_id: int) -> int:
        """
        Process rule engine step 1 for a batch.
        
        Returns:
            Number of trade-audio mappings created
        """
        logger.info("rule_engine_step1_starting", batch_id=batch_id)
        
        # Load call metadata into memory
        self._load_call_metadata(batch_id)
        self._load_unsupported_language_files(batch_id)
        
        if not self._call_metadata:
            logger.warning("no_call_metadata_found", batch_id=batch_id)
            return 0
        
        # Get pending trade metadata
        query = "SELECT * FROM tradeMetadata WHERE batchId = %s"
        trades = self.db.execute_query(query, (batch_id,))
        
        logger.info("trades_to_process", count=len(trades))
        
        total_mappings = 0
        rows_to_insert = []
        
        for trade in trades:
            trade['clientCode'] = str(trade.get('clientCode', '')).strip()
            al_number = trade.get('alNumber')
            
            # Determine matching strategy
            if not al_number or al_number == "":
                # Step 1: Use regNumber
                matching_calls, result = self._find_matching_trade_step_1(trade, batch_id)
                if not matching_calls:
                    # Fallback to Step 3
                    matching_calls, result = self._find_matching_trade_step_3(trade, batch_id)
            else:
                # Step 2: Use alNumber
                matching_calls, result = self._find_matching_trade_step_2(trade, batch_id)
                if not matching_calls:
                    # Fallback to Step 3
                    matching_calls, result = self._find_matching_trade_step_3(trade, batch_id)
            
            # Process matching calls
            if result.get('tag1') == 'No call record found':
                self._update_trade_metadata(trade['id'], 'No call record found')
            elif matching_calls:
                data_inserted = False
                
                for call_meta in matching_calls:
                    audio_file = call_meta.get('sRecordingFileName', '')
                    
                    # Skip if file has unsupported language
                    if audio_file in self._unsupported_files:
                        continue
                    
                    data_inserted = True
                    row = {
                        'tradeMetadataId': trade['id'],
                        'orderId': trade.get('orderId'),
                        'clientCode': trade.get('clientCode'),
                        'regNumber': trade.get('regNumber'),
                        'alNumber': trade.get('alNumber'),
                        'tradeDate': trade.get('tradeDate'),
                        'orderPlacedTime': trade.get('orderPlacedTime'),
                        'instType': trade.get('instType'),
                        'expiryDate': trade.get('expiryDate'),
                        'optionType': trade.get('optionType'),
                        'symbol': trade.get('symbol'),
                        'comScriptCode': trade.get('comScriptCode'),
                        'scripName': trade.get('scripName'),
                        'strikePrice': trade.get('strikePrice'),
                        'tradeQuantity': trade.get('tradeQuantity'),
                        'tradePrice': trade.get('tradePrice'),
                        'tradeValue': trade.get('tradeValue'),
                        'lotQty': trade.get('lotQty'),
                        'voiceRecordingConfirmations': result.get('tag1', ''),
                        'audioFileName': audio_file,
                        'batchId': trade.get('batchId')
                    }
                    rows_to_insert.append(row)
                
                # If no valid audio files found (all unsupported language)
                if not data_inserted and matching_calls:
                    audio_file = matching_calls[0].get('sRecordingFileName', '')
                    call_ref = self._get_call_id_by_audio_name(audio_file, batch_id)
                    self._update_trade_metadata(
                        trade['id'], 
                        'Unsupported Language',
                        audio_file,
                        call_ref
                    )
        
        # Bulk insert mappings
        if rows_to_insert:
            # Insert in batches of 10000
            batch_size = 10000
            for i in range(0, len(rows_to_insert), batch_size):
                batch_rows = rows_to_insert[i:i + batch_size]
                count = self.trade_audio_repo.insert_many(batch_rows)
                total_mappings += count
                logger.info("mappings_batch_inserted", batch_num=i // batch_size + 1, count=count)
        
        logger.info("rule_engine_step1_completed", total_mappings=total_mappings)
        return total_mappings
    
    def is_processed(self, batch_id: int) -> bool:
        """Check if triaging is already done for this batch."""
        count = self.trade_audio_repo.get_count_by_batch(batch_id)
        return count > 0
    
    def fill_audio_not_found(self, batch_id: int) -> int:
        """
        For calls without a matching tradeAudioMapping record,
        insert 'No trade data found' into auditAnswer for first 3 questions.
        
        Returns:
            Number of calls processed
        """
        logger.info("fill_audio_not_found_starting", batch_id=batch_id)
        
        # Get all calls in this batch
        query = "SELECT * FROM `call` WHERE batchId = %s"
        call_records = self.db.execute_query(query, (batch_id,))
        
        processed_count = 0
        
        for call_record in call_records:
            call_id = call_record['id']
            process_id = call_record.get('processId', self.settings.process_id)
            audio_name = call_record['audioName']
            
            # Check if this call has a tradeAudioMapping record
            query = "SELECT id FROM tradeAudioMapping WHERE audioFileName = %s"
            trade_mapping = self.db.execute_one(query, (audio_name,))
            
            if not trade_mapping:
                # No trade mapping found - insert "No trade data found" for first 3 questions
                # Question 1: sectionId=1, subSectionId=1, questionId=1
                self._insert_or_update_audit_answer(
                    process_id, call_id, 1, 1, 1, "No trade data found"
                )
                
                # Question 2: sectionId=1, subSectionId=2, questionId=2
                self._insert_or_update_audit_answer(
                    process_id, call_id, 1, 2, 2, "No trade data found"
                )
                
                # Question 3: sectionId=1, subSectionId=2, questionId=3
                self._insert_or_update_audit_answer(
                    process_id, call_id, 1, 2, 3, "No trade data found"
                )
                
                processed_count += 1
        
        logger.info("fill_audio_not_found_completed", processed=processed_count)
        return processed_count
    
    def _insert_or_update_audit_answer(
        self,
        process_id: int,
        call_id: int,
        section_id: int,
        sub_section_id: int,
        question_id: int,
        answer: str
    ):
        """Insert or update an auditAnswer record."""
        # Check if record exists
        select_query = """
            SELECT id FROM auditAnswer 
            WHERE callId = %s AND sectionId = %s AND questionId = %s
        """
        existing = self.db.execute_one(select_query, (call_id, section_id, question_id))
        
        if existing:
            # Update existing record
            update_query = """
                UPDATE auditAnswer SET answer = %s WHERE id = %s
            """
            self.db.execute_update(update_query, (answer, existing['id']))
        else:
            # Insert new record
            insert_query = """
                INSERT INTO auditAnswer 
                (processId, callId, sectionId, subSectionId, questionId, answer, scored, score)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            self.db.execute_insert(insert_query, (
                process_id, call_id, section_id, sub_section_id, question_id, answer, 0, 0
            ))
