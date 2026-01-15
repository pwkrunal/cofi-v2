"""Audit pipeline for processing uploaded files."""
from typing import List, Dict, Any
import asyncio
import json
import structlog
from pathlib import Path

from .config import get_settings
from .database import get_database, BatchStatusRepo, FileDistributionRepo, CallRepo, LidStatusRepo, LanguageRepo, ProcessRepo
from .file_manager import FileManager
from .mediator_client import MediatorClient
from .event_logger import EventLogger
from .pipeline.lid_stage import LIDStage
from .pipeline.stt_stage import STTStage
from .pipeline.llm1_stage import LLM1Stage
from .pipeline.llm2_stage import LLM2Stage

logger = structlog.get_logger()


class AuditPipeline:
    """
    Pipeline for processing uploaded audio files.
    
    Flow: LID → STT → LLM1 (if enabled) → LLM2 (if enabled)
    """
    
    def __init__(
        self,
        task_id: str,
        task_tracker: Dict,
        process_id: int,
        category_mapping_id: int
    ):
        self.task_id = task_id
        self.task_tracker = task_tracker
        self.process_id = process_id
        self.category_mapping_id = category_mapping_id
        
        self.settings = get_settings()
        self.db = get_database()
        self.mediator = MediatorClient()
        self.file_manager = FileManager()
        
        # Repositories
        self.batch_repo = BatchStatusRepo(self.db)
        self.file_dist_repo = FileDistributionRepo(self.db)
        self.call_repo = CallRepo(self.db)
        self.lid_repo = LidStatusRepo(self.db)
        self.language_repo = LanguageRepo(self.db)
        self.process_repo = ProcessRepo(self.db)
    
    async def process(self, file_names: List[str], upload_dir: str):
        """
        Process files through the audit pipeline.
        
        Args:
            file_names: List of uploaded file names
            upload_dir: Directory where files are stored locally
        """
        logger.info("audit_pipeline_starting", task_id=self.task_id, files=len(file_names))
        
        # Create batch for this audit
        batch_id = await self._create_audit_batch(file_names)
        
        # Distribute files to GPUs
        await self._distribute_files(file_names, upload_dir, batch_id)
        
        # Stage: LID
        await self._run_lid_stage(batch_id)
        
        # Update Call records with LID results (language and duration)
        self._update_calls_from_lid(batch_id)
        
        # Stage: STT
        await self._run_stt_stage(batch_id)
        
        # Stage: LLM1 (if enabled)
        if self.settings.llm1_enabled:
            await self._run_llm1_stage(batch_id)
        else:
            logger.info("llm1_skipped", task_id=self.task_id)
        
        # Stage: LLM2 (if enabled)
        if self.settings.llm2_enabled:
            await self._run_llm2_stage(batch_id)
        else:
            logger.info("llm2_skipped", task_id=self.task_id)
        
        # Mark batch as completed
        self.batch_repo.update_status(batch_id, "Completed")
        
        logger.info("audit_pipeline_completed", task_id=self.task_id, batch_id=batch_id)
    
    async def _create_audit_batch(self, file_names: List[str]) -> int:
        """Create a batch record for this audit."""
        from datetime import datetime
        
        batch_date = datetime.now().strftime("%d-%m-%Y")
        
        # Find next batch number for today
        existing = self.batch_repo.get_by_date_and_number(batch_date, 1)
        batch_number = 1
        while existing:
            batch_number += 1
            existing = self.batch_repo.get_by_date_and_number(batch_date, batch_number)
        
        batch_id = self.batch_repo.create(batch_date, batch_number)
        logger.info("audit_batch_created", batch_id=batch_id, task_id=self.task_id)
        
        return batch_id
    
    async def _distribute_files(self, file_names: List[str], upload_dir: str, batch_id: int):
        """Distribute files to GPUs using round-robin in parallel."""
        gpu_list = self.settings.gpu_machine_list

        # Log stage start
        EventLogger.stage_start(batch_id, 'file_distribution', total_files=len(file_names), metadata={
            'upload_dir': upload_dir,
            'task_id': self.task_id
        })

        # Get auditFormId once for all calls
        audit_form_id = self.process_repo.get_audit_form_id(self.process_id)

        async def upload_and_record(file_name: str, gpu_ip: str):
            """Upload a single file and create records."""
            file_path = Path(upload_dir) / file_name

            try:
                # Upload to GPU
                EventLogger.file_start(batch_id, 'file_distribution', file_name, gpu_ip)
                await self.mediator.upload_file(gpu_ip, str(file_path), file_name)

                # Create file distribution record
                self.file_dist_repo.insert(file_name, gpu_ip, batch_id)

                # Create call record (language info will be updated after LID stage)
                self.call_repo.insert_from_distribution(
                    audio_name=file_name,
                    batch_id=batch_id,
                    ip=gpu_ip,
                    process_id=self.process_id,
                    category_mapping_id=self.category_mapping_id,
                    audio_endpoint=self.settings.audio_endpoint,
                    audit_form_id=audit_form_id
                )

                EventLogger.file_complete(batch_id, 'file_distribution', file_name, gpu_ip, status='success')
                logger.info("file_distributed", file=file_name, gpu=gpu_ip, task_id=self.task_id)
                return True
            except Exception as e:
                logger.error("file_distribution_failed", file=file_name, error=str(e), task_id=self.task_id)
                EventLogger.file_error(batch_id, 'file_distribution', file_name, str(e), gpu_ip,
                                     payload={"file": file_name, "gpu": gpu_ip, "task_id": self.task_id})
                return False

        # Create upload tasks for all files (round-robin distribution)
        upload_tasks = []
        for idx, file_name in enumerate(file_names):
            gpu_ip = gpu_list[idx % len(gpu_list)]
            task = upload_and_record(file_name, gpu_ip)
            upload_tasks.append(task)

        # Execute all uploads in parallel with error handling
        logger.info("uploading_files_parallel", total_files=len(upload_tasks), task_id=self.task_id)
        results = await asyncio.gather(*upload_tasks, return_exceptions=True)

        # Count successes and failures
        successful = sum(1 for r in results if r is True)
        failed = sum(1 for r in results if r is False or isinstance(r, Exception))

        # Update batch status
        self.batch_repo.update_total_files(batch_id, len(file_names))
        self.batch_repo.update_db_insertion_status(batch_id, "Complete")

        # Log stage complete
        EventLogger.stage_complete(batch_id, 'file_distribution', successful, failed, metadata={
            'task_id': self.task_id
        })

        logger.info("file_distribution_complete", successful=successful, failed=failed, task_id=self.task_id)
    
    async def _run_lid_stage(self, batch_id: int):
        """Run LID stage and update progress."""
        logger.info("lid_stage_starting", task_id=self.task_id)
        
        self.batch_repo.update_lid_status(batch_id, "InProgress")
        lid_stage = LIDStage()
        await lid_stage.execute(batch_id, None)
        self.batch_repo.update_lid_status(batch_id, "Complete")
        
        # Update progress with actual completed count
        completed_files = self.file_dist_repo.get_by_batch(batch_id)
        completed_count = sum(1 for f in completed_files if f.get('lidDone') == 1)
        self.task_tracker["progress"]["lid"]["done"] = completed_count
        
        logger.info("lid_stage_completed", task_id=self.task_id, completed=completed_count)
    
    def _update_calls_from_lid(self, batch_id: int):
        """Update Call records with language info from LID results."""
        lid_records = self.lid_repo.get_by_batch(batch_id)

        updated_count = 0
        for record in lid_records:
            # Get language ID
            lang_code = record.get('language', 'unknown')
            lang_record = self.language_repo.get_by_code(lang_code)
            language_id = lang_record['id'] if lang_record else None

            # Update existing call record with language info and duration
            try:
                self.call_repo.update_lid_info(
                    audio_name=record['file'],
                    batch_id=batch_id,
                    language_id=language_id,
                    lang_code=lang_code,
                    audio_duration=record.get('duration', 0)
                )
                updated_count += 1
            except Exception as e:
                logger.error("call_lid_update_failed", file=record['file'], error=str(e), task_id=self.task_id)

        logger.info("calls_updated_from_lid", count=updated_count, task_id=self.task_id)
    
    async def _run_stt_stage(self, batch_id: int):
        """Run STT stage and update progress."""
        logger.info("stt_stage_starting", task_id=self.task_id)
        
        self.batch_repo.update_stt_status(batch_id, "InProgress")
        stt_stage = STTStage()
        await stt_stage.execute(batch_id, self.settings.lid_container)
        self.batch_repo.update_stt_status(batch_id, "Complete")
        
        # Update progress with actual completed count
        completed_files = self.file_dist_repo.get_by_batch(batch_id)
        completed_count = sum(1 for f in completed_files if f.get('sttDone') == 1)
        self.task_tracker["progress"]["stt"]["done"] = completed_count
        
        logger.info("stt_stage_completed", task_id=self.task_id, completed=completed_count)
    
    async def _run_llm1_stage(self, batch_id: int):
        """Run LLM1 stage and update progress."""
        logger.info("llm1_stage_starting", task_id=self.task_id)
        
        self.batch_repo.update_llm1_status(batch_id, "InProgress")
        llm1_stage = LLM1Stage()
        await llm1_stage.execute(batch_id, self.settings.stt_container)
        self.batch_repo.update_llm1_status(batch_id, "Complete")
        
        # Update progress with actual completed count
        completed_files = self.file_dist_repo.get_by_batch(batch_id)
        completed_count = sum(1 for f in completed_files if f.get('llm1Done') == 1)
        self.task_tracker["progress"]["llm1"]["done"] = completed_count
        
        logger.info("llm1_stage_completed", task_id=self.task_id, completed=completed_count)
    
    async def _run_llm2_stage(self, batch_id: int):
        """Run LLM2 stage and update progress."""
        logger.info("llm2_stage_starting", task_id=self.task_id)
        
        self.batch_repo.update_llm2_status(batch_id, "InProgress")
        llm2_stage = LLM2Stage()
        await llm2_stage.execute(batch_id, self.settings.llm1_container)
        self.batch_repo.update_llm2_status(batch_id, "Complete")
        
        # Update progress with actual completed count
        completed_files = self.file_dist_repo.get_by_batch(batch_id)
        completed_count = sum(1 for f in completed_files if f.get('llm2Done') == 1)
        self.task_tracker["progress"]["llm2"]["done"] = completed_count
        
        logger.info("llm2_stage_completed", task_id=self.task_id, completed=completed_count)
