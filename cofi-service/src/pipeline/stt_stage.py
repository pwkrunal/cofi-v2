"""STT (Speech-to-Text) processing stage."""
from typing import Dict, Any, List, Optional
import structlog

from .base import PipelineStage
from ..config import get_settings
from ..database import CallRepo, TranscriptRepo, LanguageRepo, get_database
from ..webhook_client import get_webhook_client

logger = structlog.get_logger()


class STTStage(PipelineStage):
    """Speech-to-text transcription stage."""
    
    stage_name = "STT"
    status_column = "sttDone"
    
    def __init__(self):
        super().__init__()
        settings = get_settings()
        self.container_name = settings.stt_container
        self.wait_seconds = settings.stt_wait
        self.api_endpoint = settings.stt_api_endpoint
        self.call_repo = CallRepo(self.db)
        self.transcript_repo = TranscriptRepo(self.db)
        self.language_repo = LanguageRepo(self.db)
        
        # Diarization setting from config
        self.diarization = settings.diarization
        
        # IVR enabled setting
        self.ivr_enabled = settings.ivr_enabled
        
        # Cache for call records to get call_id
        self._call_cache: Dict[str, Dict] = {}
    
    def build_payload(self, file_name: str) -> Dict[str, Any]:
        """
        Build STT API payload.
        
        Uses language from call table, with hinglish -> hi mapping.
        Applies diarization settings based on DIARIZATION env var.
        """
        # Get language from call record cache
        call_record = self._call_cache.get(file_name)
        lang = call_record.get('lang', 'hi') if call_record else 'hi'
        
        # Map hinglish to hi for the API
        if lang == 'hinglish':
            audio_language = 'hi'
        else:
            audio_language = lang
        
        # use_time_based and no_of_speakers depend on diarization setting
        if self.diarization == 1:
            use_time_based = True
            no_of_speakers = 0
        else:
            use_time_based = False
            no_of_speakers = 2
        
        return {
            "file_name": file_name,
            "no_of_speakers": no_of_speakers,
            "audio_language": audio_language,
            "post_processing": True,
            "use_ivr": self.ivr_enabled,
            "use_time_based": use_time_based
        }
    
    def process_response(self, file_name: str, response: Dict[str, Any], gpu_ip: str, batch_id: int):
        """
        Process STT API response and store transcripts.
        
        Response format (from stt_wrapper.py):
        response.json() = [metadata, all_chunks]
        all_chunks = [
            {
                "start_time": 0.0,
                "end_time": 2.5,
                "speaker": "0",
                "transcript": "Hello",
                "confidence": 0.95
            },
            ...
        ]
        """
        try:
            # Get call record to get call_id and language_id
            call_record = self._call_cache.get(file_name)
            if not call_record:
                call_record = self.call_repo.get_by_audio_name(file_name, batch_id)
                if call_record:
                    self._call_cache[file_name] = call_record
            
            if not call_record:
                logger.error("call_record_not_found", file=file_name, batch_id=batch_id)
                return
            
            call_id = call_record['id']
            language_code = call_record.get('lang', 'hi')
            language_id = self.language_repo.get_id_by_code(language_code)
            
            # Parse STT response
            # Response can be: [metadata, chunks] or just chunks or dict with data
            all_chunks = []
            
            if isinstance(response, list) and len(response) >= 2:
                # Format: [metadata, chunks]
                all_chunks = response[1] if isinstance(response[1], list) else []
            elif isinstance(response, list):
                # Format: just chunks
                all_chunks = response
            elif isinstance(response, dict):
                # Format: {"data": {"chunks": [...]}} or similar
                data = response.get("data", response)
                all_chunks = data.get("chunks", data.get("transcripts", []))
            
            if not all_chunks:
                logger.warning("no_transcript_chunks", file=file_name)
            else:
                # Insert transcript records
                transcript_records = []
                for chunk in all_chunks:
                    # Handle confidence - check for 'nan' string
                    confidence = chunk.get('confidence')
                    if confidence == 'nan' or confidence == 'NaN':
                        confidence = None
                    elif confidence is not None:
                        try:
                            confidence = float(confidence)
                        except (ValueError, TypeError):
                            confidence = None
                    
                    record = {
                        'callId': call_id,
                        'languageId': language_id,
                        'startTime': float(chunk.get('start_time', 0)),
                        'endTime': float(chunk.get('end_time', 0)),
                        'speaker': 'Speaker ' + str(chunk.get('speaker', '0')),
                        'text': chunk.get('transcript', ''),
                        'confidence': confidence
                    }
                    transcript_records.append(record)
                
                # Bulk insert transcripts
                if transcript_records:
                    inserted = self.transcript_repo.insert_many(transcript_records)
                    logger.info("transcripts_inserted", file=file_name, count=inserted)
            
            # Update call status
            self.call_repo.update_status(file_name, "Pending", "TranscriptDone")
            logger.info("stt_status_updated", file=file_name, new_status="TranscriptDone")

            # Send webhook notification
            if file_name in self._call_cache:
                call_id = self._call_cache[file_name]['id']
                try:
                    webhook_client = get_webhook_client()
                    webhook_client.notify_call_status(call_id, "TranscriptDone")
                except Exception as webhook_err:
                    logger.error("webhook_failed", call_id=call_id, status="TranscriptDone", error=str(webhook_err))

        except Exception as e:
            logger.error("stt_response_processing_failed", file=file_name, error=str(e))
            # Still update status to avoid reprocessing
            self.call_repo.update_status(file_name, "Pending", "TranscriptDone")

            # Send webhook notification even on error
            if file_name in self._call_cache:
                call_id = self._call_cache[file_name]['id']
                try:
                    webhook_client = get_webhook_client()
                    webhook_client.notify_call_status(call_id, "TranscriptDone")
                except Exception as webhook_err:
                    logger.error("webhook_failed", call_id=call_id, status="TranscriptDone", error=str(webhook_err))
    
    def get_pending_files(self, batch_id: int) -> Dict[str, List[str]]:
        """
        Override to get files from Call table with status='Pending'.
        Filters out:
        - Short calls (< 5 seconds duration)
        - Unsupported languages (not en, hi, hinglish)
        Also caches call records for later use in process_response.
        """
        records = self.call_repo.get_by_status(batch_id, "Pending")
        
        # Supported languages for STT
        supported_languages = ['en', 'hi', 'hinglish']
        
        # Cache call records and group by GPU IP
        file_gpu_mapping: Dict[str, List[str]] = {}
        short_call_count = 0
        unsupported_count = 0
        
        for record in records:
            audio_name = record['audioName']
            language = record.get('lang', '')
            audio_duration = record.get('audioDuration', 0)
            
            # Check if call is too short (less than 5 seconds)
            if audio_duration < 5:
                # Mark as ShortCall and skip
                self.call_repo.update_status(audio_name, "Pending", "ShortCall")
                logger.info("short_call_skipped",
                           file=audio_name,
                           duration=audio_duration)

                # Send webhook notification
                try:
                    webhook_client = get_webhook_client()
                    webhook_client.notify_call_status(record['id'], "ShortCall")
                except Exception as webhook_err:
                    logger.error("webhook_failed", call_id=record['id'], status="ShortCall", error=str(webhook_err))

                short_call_count += 1
                continue
            
            # Check if language is supported
            if language not in supported_languages:
                # Mark as UnsupportedLanguage and skip
                self.call_repo.update_status(audio_name, "Pending", "UnsupportedLanguage")
                logger.info("unsupported_language_skipped",
                           file=audio_name,
                           language=language)

                # Send webhook notification
                try:
                    webhook_client = get_webhook_client()
                    webhook_client.notify_call_status(record['id'], "UnsupportedLanguage")
                except Exception as webhook_err:
                    logger.error("webhook_failed", call_id=record['id'], status="UnsupportedLanguage", error=str(webhook_err))

                unsupported_count += 1
                continue
            
            # Cache for later use
            self._call_cache[audio_name] = record
            
            ip = record.get('ip') or self.settings.gpu_machine_list[0]
            if ip not in file_gpu_mapping:
                file_gpu_mapping[ip] = []
            file_gpu_mapping[ip].append(audio_name)
        
        if short_call_count > 0:
            logger.info("short_calls_marked", count=short_call_count)
        if unsupported_count > 0:
            logger.info("unsupported_languages_marked", count=unsupported_count)
        
        return file_gpu_mapping
