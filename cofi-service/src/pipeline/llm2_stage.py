"""LLM2 (Audit Question Answering) processing stage."""
from typing import Dict, Any, List, Optional
import aiohttp
import asyncio
import structlog

from ..config import get_settings
from ..database import CallRepo, TranscriptRepo, get_database
from ..mediator_client import MediatorClient
from ..webhook_client import get_webhook_client
from .llm2_custom_rules import CustomRuleExecutor

logger = structlog.get_logger()


class AuditFormRepo:
    """Repository for querying audit form questions."""
    
    def __init__(self, db):
        self.db = db
    
    def get_audit_form_questions(self, audit_form_id: int) -> List[Dict]:
        """Get all audit form questions with sections."""
        query = """
            SELECT 
                afsqm.*, 
                s.*, 
                q.*
            FROM auditFormSectionQuestionMapping afsqm 
            INNER JOIN section s ON afsqm.sectionId = s.id 
            INNER JOIN question q ON afsqm.questionId = q.id 
            WHERE afsqm.auditFormId = %s 
            AND s.id IN (
                SELECT sectionId 
                FROM auditFormSectionQuestionMapping 
                WHERE auditFormId = %s
            )
        """
        return self.db.execute_query(query, (audit_form_id, audit_form_id))


class AuditAnswerRepo:
    """Repository for auditAnswer table operations."""
    
    def __init__(self, db):
        self.db = db
    
    def insert(
        self,
        process_id: int,
        call_id: int,
        section_id: int,
        sub_section_id: int,
        question_id: int,
        answer: str,
        scored: int,
        score: float,
        sentiment: str,
        is_critical: int,
        applicable_to: str
    ) -> int:
        """Insert a single audit answer."""
        query = """
            INSERT INTO auditAnswer (
                processId, callId, sectionId, subSectionId, questionId, 
                answer, scored, score, sentiment, isCritical, applicableTo
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        return self.db.execute_insert(query, (
            process_id, call_id, section_id, sub_section_id, question_id,
            answer, scored, score, sentiment, is_critical, applicable_to
        ))
    
    def insert_many(self, records: List[Dict]) -> int:
        """Insert multiple audit answers."""
        if not records:
            return 0
        
        query = """
            INSERT INTO auditAnswer (
                processId, callId, sectionId, subSectionId, questionId, 
                answer, scored, score, sentiment, isCritical, applicableTo
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        params_list = []
        for r in records:
            params = (
                r.get('processId'),
                r.get('callId'),
                r.get('sectionId'),
                r.get('subSectionId'),
                r.get('questionId'),
                r.get('answer', 'NA'),
                r.get('scored', 0),
                r.get('score', 0),
                r.get('sentiment', ''),
                r.get('isCritical', 0),
                r.get('applicableTo', 'None')
            )
            params_list.append(params)
        
        return self.db.execute_many(query, params_list)


class LLM2Stage:
    """
    Second LLM extraction stage - Audit Question Answering.
    
    Workflow:
    1. Query audit form questions
    2. Classify conversation as 'trade' or 'non-trade'
    3. If non-trade: mark all answers as 'NA'
    4. If trade: call NLP API for each question and store answer
    5. Insert all answers into auditAnswer table
    """
    
    stage_name = "LLM2"
    
    def __init__(self):
        self.settings = get_settings()
        self.db = get_database()
        self.call_repo = CallRepo(self.db)
        self.transcript_repo = TranscriptRepo(self.db)
        self.audit_form_repo = AuditFormRepo(self.db)
        self.audit_answer_repo = AuditAnswerRepo(self.db)
        self.mediator = MediatorClient()
        
        # Answer mappings for normalizing NLP responses
        self.answer_mappings = {
            'yes': 'YES',
            'no': 'NO',
            'na': 'NA',
            'dealer': 'Dealer',
            'client': 'Client',
            'both': 'Both client & dealer',
            'anger': 'YES',
            'disgust': 'YES'
        }
        
        # Custom rules for client-specific questions
        self.custom_rules = CustomRuleExecutor(self.db, self)
        
        # Build full API URL
        self.api_url = f"{self.settings.nlp_api_q2}/extract_information"
        self.timeout = aiohttp.ClientTimeout(total=600)
    
    def _get_transcript_text(self, call_id: int) -> str:
        """Get concatenated transcript text for a call."""
        transcripts = self.transcript_repo.get_by_call_id(call_id)
        
        texts = []
        for t in transcripts:
            speaker = t.get('speaker', '')
            text = t.get('text', '')
            if text:
                texts.append(f"{speaker}: {text}")
        
        return "\n".join(texts)
    
    async def call_nlp_api(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Call the NLP API directly (not via GPU mediator)."""
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            try:
                async with session.post(self.api_url, json=payload) as resp:
                    result = await resp.json()
                    logger.info("nlp_api_q2_called", status=resp.status)
                    return result
            except Exception as e:
                logger.error("nlp_api_q2_failed", error=str(e))
                raise
    
    async def classify_trade(self, transcript_text: str, language: str) -> str:
        """
        Classify conversation as 'trade' or 'non-trade'.
        
        Returns: 'trade' or 'non-trade'
        """
        payload = {
            "text": transcript_text,
            "text_language": language,
            "prompts": [
                {
                    "entity": "trade_classify",
                    "prompts": [
                        "Classify the given conversation as 'trade' or 'non-trade: Short calls', "
                        "based on the following conditions: non-trade - Short calls: Any one or more "
                        "criteria should be consider The call ends with only one statement. The call ends "
                        "due to not audible properly. The call conversation only about IVR options. The call "
                        "end due to one speaker is busy or not picking up the call etc. There should not be "
                        "any discussion about trade related information, stock details, market conditions, "
                        "profit/loss, buy/sell, lot/quantity, trading suggestions during the conversation. "
                        "OR trade: Any one scenario should present There should be discussion or mention "
                        "about trading in terms of stock information, market conditions, profit/loss, buy/sell, "
                        "lot/quantity and or order confirmation. Answer the following question in 'trade' or "
                        "'non-trade' in valid JSON like {'validation':'trade/non-trade'} and explanation outside the JSON."
                    ],
                    "type": "multiple"
                }
            ],
            "additional_params": {}
        }
        
        try:
            response = await self.call_nlp_api(payload)
            
            if 'data' in response:
                if 'derived_value' in response['data']:
                    result = response['data']['derived_value'][0]['result']
                    logger.info("trade_classification", result=result)
                    return result
        except Exception as e:
            logger.error("trade_classification_failed", error=str(e))
        
        return 'non-trade'  # Default to non-trade on error
    
    async def answer_question(self, transcript_text: str, language: str, question: Dict) -> str:
        """
        Answer a single audit question using NLP API.
        
        Returns: 'YES', 'NO', or 'NA'
        """
        # Use intent or hindiIntent based on language
        intent = question.get('hindiIntent') if language == 'hi' else question.get('intent')
        if not intent:
            intent = question.get('prompt', '')
        
        payload = {
            "text": transcript_text,
            "text_language": language,
            "prompts": [
                {
                    "entity": question.get('attribute', 'question'),
                    "prompts": [intent],
                    "type": "multiple"
                }
            ],
            "additional_params": {}
        }
        
        try:
            response = await self.call_nlp_api(payload)
            
            if 'data' in response:
                if 'derived_value' in response['data']:
                    result = response['data']['derived_value'][0]['result']
                    
                    if result and len(str(result)) > 0:
                        result_lower = str(result).lower()
                        
                        # Check if result has a mapping
                        if result_lower in self.answer_mappings:
                            return self.answer_mappings[result_lower]
                        else:
                            # Return original result if no mapping found
                            return str(result)
        except Exception as e:
            logger.error("question_answering_failed", question_id=question.get('questionId'), error=str(e))
        
        return 'NA'
    
    def _build_transcript_chunks(self, call_id: int) -> List[Dict]:
        """Build transcript chunks in required format."""
        transcripts = self.transcript_repo.get_by_call_id(call_id)
        all_chunks = []
        for row in transcripts:
            chunk = {
                'start_time': row.get('startTime'),
                'end_time': row.get('endTime'),
                'speaker': row.get('speaker'),
                'transcript': row.get('text')
            }
            all_chunks.append(chunk)
        return all_chunks
    
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
        try:
            response = await self.mediator.call_api(
                gpu_ip,
                self.settings.lid_port,  # Port 4030
                self.settings.lid_api_endpoint,  # /file_stt_features
                payload
            )
            
            # Extract result
            if 'data' in response:
                derived_val = response['data'].get('derived_value', [])
                if derived_val:
                    result = derived_val[0].get('results')
                    return result if result else 'NA'
        except Exception as e:
            logger.error("speech_param_api_failed", error=str(e), call_id=call_record['id'])
        
        return 'NA'
    
    async def process_call(self, call_record: Dict):
        """Process a single call for audit question answering."""
        call_id = call_record['id']
        batch_id = call_record['batchId']
        audio_name = call_record['audioName']
        language = call_record.get('lang', 'hi')
        
        try:
            # Get audit form ID from processRepo or call record
            process_id = self.settings.process_id
            
            # For now, we can get audit_form_id from process table or use default
            # Let's assume we have a method to get it
            from ..database import ProcessRepo
            process_repo = ProcessRepo(self.db)
            process_info = process_repo.get_by_id(process_id)
            audit_form_id = process_info.get('auditFormId', 1) if process_info else 1
            
            # Get audit form questions
            audit_form_questions = self.audit_form_repo.get_audit_form_questions(audit_form_id)
            
            if not audit_form_questions:
                logger.warning("no_audit_questions_found", audit_form_id=audit_form_id)
                return
            
            logger.info("audit_questions_loaded", count=len(audit_form_questions), call_id=call_id)
            
            # Get transcript
            transcript_text = self._get_transcript_text(call_id)
            
            if not transcript_text:
                logger.warning("no_transcript_found", call_id=call_id)
                return
            
            # Step 1: Classify as trade or non-trade
            classification = await self.classify_trade(transcript_text, language)
            
            audit_answers = []
            
            if classification == 'non-trade':
                # Mark all answers as NA
                logger.info("call_classified_non_trade", call_id=call_id)
                for question in audit_form_questions:
                    answer_record = {
                        'processId': process_id,
                        'callId': call_id,
                        'sectionId': question.get('sectionId'),
                        'subSectionId': question.get('subSectionId'),
                        'questionId': question.get('questionId'),
                        'answer': 'NA',
                        'scored': 0,
                        'score': 0,
                        'sentiment': '',
                        'isCritical': question.get('isCritical', 0),
                        'applicableTo': question.get('applicableTo', 'None')
                    }
                    audit_answers.append(answer_record)
            else:
                # Answer each question
                logger.info("call_classified_trade", call_id=call_id)
                
                skip_list = self.settings.llm2_skip_question_list
                na_list = self.settings.llm2_na_question_list
                
                # Get GPU IP for this call
                gpu_ip = call_record.get('ip', self.settings.gpu_machine_list[0])
                
                for question in audit_form_questions:
                    question_name = question.get('name', '')
                    attribute = question.get('attribute', '')
                    
                    if question_name in skip_list:
                        logger.info("skipping_question", question_name=question_name, call_id=call_id)
                        continue
                        
                    if question_name in na_list:
                        logger.info("marking_question_as_na", question_name=question_name, call_id=call_id)
                        answer = 'NA'
                    elif self.custom_rules.has_custom_rule(question_name):
                        logger.info("executing_custom_rule", question_name=question_name, call_id=call_id)
                        answer = await self.custom_rules.execute(
                            question_name,
                            call_record,
                            question,
                            transcript_text,
                            language
                        )
                    elif attribute == 'speech_parameter':
                        logger.info("processing_speech_parameter_question", question_name=question_name, call_id=call_id)
                        answer = await self.answer_speech_parameter_question(call_record, question, gpu_ip)
                    else:
                        answer = await self.answer_question(transcript_text, language, question)
                    
                    answer_record = {
                        'processId': process_id,
                        'callId': call_id,
                        'sectionId': question.get('sectionId'),
                        'subSectionId': question.get('subSectionId'),
                        'questionId': question.get('questionId'),
                        'answer': answer,
                        'scored': 0,
                        'score': 0,
                        'sentiment': '',
                        'isCritical': question.get('isCritical', 0),
                        'applicableTo': question.get('applicableTo', 'None')
                    }
                    audit_answers.append(answer_record)
            
            # Insert all audit answers
            if audit_answers:
                count = self.audit_answer_repo.insert_many(audit_answers)
                logger.info("audit_answers_inserted", call_id=call_id, count=count)
            
        except Exception as e:
            logger.error("llm2_processing_failed", call_id=call_id, error=str(e))
    
    async def execute(self, batch_id: int, previous_container: Optional[str] = None):
        """
        Execute LLM2 stage for audit question answering.
        
        Note: This stage calls external NLP API directly, not via GPU mediator.
        """
        logger.info("llm2_stage_starting", batch_id=batch_id)
        
        # Get calls with status='AuditDone'
        call_records = self.call_repo.get_by_status(batch_id, "AuditDone")
        
        if not call_records:
            logger.info("no_pending_calls_for_llm2")
            return
        
        logger.info("calls_to_process", count=len(call_records))
        
        successful = 0
        failed = 0
        
        for call_record in call_records:
            try:
                await self.process_call(call_record)
                
                # Update call status
                self.call_repo.update_status(
                    call_record['audioName'],
                    "AuditDone",
                    "Complete"
                )

                # Send webhook notification
                try:
                    webhook_client = get_webhook_client()
                    webhook_client.notify_call_status(call_record['id'], "Complete")
                except Exception as webhook_err:
                    logger.error("webhook_failed", call_id=call_record['id'], status="Complete", error=str(webhook_err))

                successful += 1
                
            except Exception as e:
                logger.error("llm2_call_processing_failed", 
                           call_id=call_record['id'], 
                           error=str(e))
                failed += 1
        
        logger.info("llm2_stage_completed", successful=successful, failed=failed)
