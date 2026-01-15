"""Reaudit pipeline for reprocessing existing audio files."""
from typing import List, Dict
import structlog

from .config import get_settings
from .database import get_database, CallRepo, TranscriptRepo, LidStatusRepo, FileDistributionRepo, BatchStatusRepo
from .event_logger import EventLogger
from .pipeline.lid_stage import LIDStage
from .pipeline.stt_stage import STTStage
from .pipeline.llm1_stage import LLM1Stage
from .pipeline.llm2_stage import LLM2Stage

logger = structlog.get_logger()


class AuditAnswerRepo:
    """Repository for auditAnswer table operations (for reaudit cleanup)."""
    
    def __init__(self, db):
        self.db = db
    
    def delete_by_call_ids(self, call_ids: List[int]) -> int:
        """Delete audit answers for given call IDs."""
        if not call_ids:
            return 0
        
        placeholders = ','.join(['%s'] * len(call_ids))
        query = f"DELETE FROM auditAnswer WHERE callId IN ({placeholders})"
        return self.db.execute_update(query, tuple(call_ids))


class ReauditPipeline:
    """
    Pipeline for reprocessing existing audio files.
    
    Flow: LID (if selected) → STT → LLM1 → LLM2
    
    Data cleanup:
    - If 'stt' in stages: deletes existing transcripts
    - If 'llm2' in stages: deletes existing auditAnswer records
    """
    
    def __init__(self, task_id: str, task_tracker: Dict):
        self.task_id = task_id
        self.task_tracker = task_tracker
        
        self.settings = get_settings()
        self.db = get_database()
        
        # Repositories
        self.call_repo = CallRepo(self.db)
        self.transcript_repo = TranscriptRepo(self.db)
        self.lid_repo = LidStatusRepo(self.db)
        self.file_dist_repo = FileDistributionRepo(self.db)
        self.audit_answer_repo = AuditAnswerRepo(self.db)
        self.batch_repo = BatchStatusRepo(self.db)
    
    async def process(self, audio_names: List[str], stages: List[str]):
        """
        Reprocess files through specified stages.
        
        Args:
            audio_names: List of audio file names to reprocess
            stages: List of stages to run (lid, stt, llm1, llm2)
        """
        logger.info("reaudit_pipeline_starting", 
                   task_id=self.task_id, 
                   files=len(audio_names),
                   stages=stages)
        
        # Log reaudit start to EventLogger (batch_id=0 for reaudit operations)
        EventLogger.info(0, 'reaudit', f"Reaudit started for {len(audio_names)} files", metadata={
            'task_id': self.task_id,
            'stages': stages,
            'files': audio_names
        })
        
        # Get call records for these audio files
        call_ids = []
        batch_ids = set()
        for audio_name in audio_names:
            call = self.call_repo.get_by_audio_name_any_batch(audio_name)
            if call:
                call_ids.append(call['id'])
                batch_ids.add(call['batchId'])
        
        if not call_ids:
            logger.warning("no_calls_found", audio_names=audio_names)
            EventLogger.info(0, 'reaudit', f"No calls found for reaudit", metadata={
                'task_id': self.task_id,
                'audio_names': audio_names
            })
            return
        
        logger.info("calls_found_for_reaudit", count=len(call_ids), batches=list(batch_ids))
        
        # Data cleanup based on stages
        if "stt" in stages:
            deleted = self._delete_transcripts(call_ids)
            logger.info("transcripts_deleted", count=deleted)
            EventLogger.info(0, 'reaudit', f"Deleted {deleted} transcripts", metadata={
                'task_id': self.task_id,
                'count': deleted
            })
        
        if "llm2" in stages:
            deleted = self._delete_audit_answers(call_ids)
            logger.info("audit_answers_deleted", count=deleted)
            EventLogger.info(0, 'reaudit', f"Deleted {deleted} audit answers", metadata={
                'task_id': self.task_id,
                'count': deleted
            })
        
        # Reset call statuses based on earliest stage
        self._reset_call_statuses(call_ids, stages)
        
        # Process each batch
        for batch_id in batch_ids:
            # Stage: LID (if selected)
            if "lid" in stages:
                await self._run_lid_stage(batch_id, audio_names)
                self._update_progress("lid", len(audio_names))
            
            # Stage: STT
            if "stt" in stages:
                await self._run_stt_stage(batch_id)
                self._update_progress("stt", len(audio_names))
            
            # Stage: LLM1 (if enabled and selected)
            if "llm1" in stages and self.settings.llm1_enabled:
                await self._run_llm1_stage(batch_id)
                self._update_progress("llm1", len(audio_names))
            
            # Stage: LLM2 (if enabled and selected)
            if "llm2" in stages and self.settings.llm2_enabled:
                await self._run_llm2_stage(batch_id)
                self._update_progress("llm2", len(audio_names))
        
        # Log reaudit completion
        EventLogger.info(0, 'reaudit', f"Reaudit completed for {len(audio_names)} files", metadata={
            'task_id': self.task_id,
            'batches_processed': list(batch_ids),
            'stages': stages
        })
        
        logger.info("reaudit_pipeline_completed", task_id=self.task_id, batches=list(batch_ids))
    
    def _delete_transcripts(self, call_ids: List[int]) -> int:
        """Delete existing transcripts for given call IDs."""
        total_deleted = 0
        for call_id in call_ids:
            deleted = self.transcript_repo.delete_by_call_id(call_id)
            total_deleted += deleted
        return total_deleted
    
    def _delete_audit_answers(self, call_ids: List[int]) -> int:
        """Delete existing audit answers for given call IDs."""
        return self.audit_answer_repo.delete_by_call_ids(call_ids)
    
    def _reset_call_statuses(self, call_ids: List[int], stages: List[str]):
        """Reset call statuses based on the earliest stage in the pipeline."""
        # Determine the reset status based on earliest stage
        stage_order = ["lid", "stt", "llm1", "llm2"]
        earliest_status = "Pending"  # Default reset to Pending
        
        for stage in stage_order:
            if stage in stages:
                if stage == "lid":
                    earliest_status = "Pending"
                elif stage == "stt":
                    earliest_status = "Pending"  # STT picks up Pending calls
                elif stage == "llm1":
                    earliest_status = "TranscriptDone"
                elif stage == "llm2":
                    earliest_status = "AuditDone"
                break
        
        # Update call statuses
        for call_id in call_ids:
            self.call_repo.update_status_by_id(call_id, earliest_status)
        
        logger.info("call_statuses_reset", count=len(call_ids), new_status=earliest_status)
    
    def _update_progress(self, stage: str, count: int):
        """Update task progress for a stage."""
        if stage in self.task_tracker["progress"]:
            self.task_tracker["progress"][stage]["done"] = count
    
    async def _run_lid_stage(self, batch_id: int, audio_names: List[str]):
        """Run LID stage for specific files."""
        logger.info("reaudit_lid_starting", task_id=self.task_id)
        
        # Reset fileDistribution lidDone for these files
        for audio_name in audio_names:
            self.file_dist_repo.reset_stage_for_file(audio_name, "lidDone")
        
        lid_stage = LIDStage()
        await lid_stage.execute(batch_id, None)
        
        logger.info("reaudit_lid_completed", task_id=self.task_id)
    
    async def _run_stt_stage(self, batch_id: int):
        """Run STT stage."""
        logger.info("reaudit_stt_starting", task_id=self.task_id)
        
        stt_stage = STTStage()
        await stt_stage.execute(batch_id, self.settings.lid_container)
        
        logger.info("reaudit_stt_completed", task_id=self.task_id)
    
    async def _run_llm1_stage(self, batch_id: int):
        """Run LLM1 stage."""
        logger.info("reaudit_llm1_starting", task_id=self.task_id)
        
        llm1_stage = LLM1Stage()
        await llm1_stage.execute(batch_id, self.settings.stt_container)
        
        logger.info("reaudit_llm1_completed", task_id=self.task_id)
    
    async def _run_llm2_stage(self, batch_id: int):
        """Run LLM2 stage."""
        logger.info("reaudit_llm2_starting", task_id=self.task_id)
        
        llm2_stage = LLM2Stage()
        await llm2_stage.execute(batch_id, self.settings.llm1_container)
        
        logger.info("reaudit_llm2_completed", task_id=self.task_id)
