"""Main entry point for cofi-service - the CPU orchestrator."""
import asyncio
import structlog

from .config import get_settings
from .database import get_database, BatchStatusRepo, FileDistributionRepo, LidStatusRepo, CallRepo, LanguageRepo, ProcessRepo
from .file_manager import FileManager
from .metadata_manager import MetadataManager
from .rule_engine import RuleEngineStep1
from .mediator_client import MediatorClient
from .pipeline.denoise_stage import DenoiseStage
from .pipeline.ivr_stage import IVRStage
from .pipeline.lid_stage import LIDStage
from .pipeline.stt_stage import STTStage
from .pipeline.llm1_stage import LLM1Stage
from .pipeline.llm2_stage import LLM2Stage
from .event_logger import EventLogger

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.dev.ConsoleRenderer()
    ]
)
logger = structlog.get_logger()


class CofiOrchestrator:
    """Main orchestrator for the audio processing pipeline."""
    
    def __init__(self):
        self.settings = get_settings()
        self.db = get_database()
        self.file_manager = FileManager()
        self.mediator = MediatorClient()
        
        # Initialize repositories
        self.batch_repo = BatchStatusRepo(self.db)
        self.file_dist_repo = FileDistributionRepo(self.db)
        self.lid_repo = LidStatusRepo(self.db)
        self.call_repo = CallRepo(self.db)
        self.language_repo = LanguageRepo(self.db)
        self.process_repo = ProcessRepo(self.db)
        self.metadata_manager = MetadataManager()
        self.rule_engine = RuleEngineStep1()
    
    def get_or_create_batch(self) -> dict:
        """Get existing batch or create new one."""
        batch = self.batch_repo.get_by_date_and_number(
            self.settings.batch_date,
            self.settings.current_batch
        )
        
        if batch:
            logger.info("batch_found", batch_id=batch['id'])
            return batch
        
        # Create new batch
        batch_id = self.batch_repo.create(
            self.settings.batch_date,
            self.settings.current_batch
        )
        logger.info("batch_created", batch_id=batch_id)
        
        return self.batch_repo.get_by_date_and_number(
            self.settings.batch_date,
            self.settings.current_batch
        )
    
    async def distribute_files(self, batch: dict) -> bool:
        """
        Read files from batch directory and distribute to GPUs.
        Returns True if distribution was done, False if already complete.
        """
        batch_id = batch['id']

        # Check if dbInsertionStatus is already Complete
        if batch.get('dbInsertionStatus') == 'Complete':
            logger.info("file_distribution_already_complete", batch_id=batch_id)
            return False

        # Mark as InProgress
        self.batch_repo.update_db_insertion_status(batch_id, "InProgress")
        self.batch_repo.set_stage_start_time(batch_id, "file_distribution")

        # Check if files already distributed (partial resume)
        existing = self.file_dist_repo.get_by_batch(batch_id)

        if existing:
            logger.info("files_already_distributed", batch_id=batch_id, count=len(existing))
            self.batch_repo.update_db_insertion_status(batch_id, "Complete")
            self.batch_repo.set_stage_end_time(batch_id, "file_distribution")
            return False

        # Read batch files
        batch_files = self.file_manager.read_batch_files()

        # Log stage start
        EventLogger.stage_start(batch_id, 'file_distribution', total_files=len(batch_files.audio_files))

        # Distribute to GPUs
        distribution = self.file_manager.distribute_files_to_gpus(batch_files.audio_files)

        # Get audit form ID once (used for all calls)
        audit_form_id = self.process_repo.get_audit_form_id(self.settings.process_id)

        # Upload files to GPUs in parallel
        async def upload_and_record(gpu_ip: str, file_path: str):
            """Upload a single file and create records."""
            file_name = self.file_manager.get_file_name(file_path)

            try:
                # Upload file to GPU
                EventLogger.file_start(batch_id, 'file_distribution', file_name, gpu_ip)
                await self.mediator.upload_file(gpu_ip, file_path, file_name)
                EventLogger.file_complete(batch_id, 'file_distribution', file_name, gpu_ip,
                                        response={'uploaded': True, 'size': 'N/A'}, status='success')

                # Create file distribution record
                self.file_dist_repo.insert(file_name, gpu_ip, batch_id)

                # Create call record (language info will be updated after LID stage)
                try:
                    self.call_repo.insert_from_distribution(
                        audio_name=file_name,
                        batch_id=batch_id,
                        ip=gpu_ip,
                        process_id=self.settings.process_id,
                        category_mapping_id=self.settings.category_mapping_id,
                        audio_endpoint=self.settings.audio_endpoint,
                        audit_form_id=audit_form_id
                    )
                    logger.info("call_record_created", file=file_name, batch_id=batch_id)
                except Exception as e:
                    logger.error("call_record_creation_failed", file=file_name, error=str(e))

                return True, file_name
            except Exception as e:
                logger.error("file_upload_failed", file=file_name, gpu=gpu_ip, error=str(e))
                EventLogger.file_error(batch_id, 'file_distribution', file_name, str(e), gpu_ip)
                return False, file_name

        # Create upload tasks for all files across all GPUs
        upload_tasks = []
        for gpu_ip, file_paths in distribution.items():
            for file_path in file_paths:
                task = upload_and_record(gpu_ip, file_path)
                upload_tasks.append(task)

        # Execute all uploads in parallel
        logger.info("uploading_files_parallel", total_tasks=len(upload_tasks))
        results = await asyncio.gather(*upload_tasks, return_exceptions=False)

        # Count successes and failures
        uploaded_count = sum(1 for success, _ in results if success)
        failed_count = sum(1 for success, _ in results if not success)

        # Update batch status
        self.batch_repo.update_total_files(batch_id, len(batch_files.audio_files))
        self.batch_repo.update_db_insertion_status(batch_id, "Complete")
        self.batch_repo.set_stage_end_time(batch_id, "file_distribution")

        # Log stage complete
        EventLogger.stage_complete(batch_id, 'file_distribution', uploaded_count, failed_count)

        logger.info("files_distributed", total=len(batch_files.audio_files))
        return True
    
    def update_calls_from_lid(self, batch_id: int):
        """Update Call records with language info from LID results."""
        EventLogger.info(batch_id, 'lid', 'Updating call records with LID results')

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
                logger.error("call_lid_update_failed", file=record['file'], error=str(e))

        EventLogger.info(batch_id, 'lid', f'Updated {updated_count} call records with LID data',
                        metadata={'updated': updated_count})
        logger.info("calls_updated_from_lid", count=updated_count)
    
    def update_batch_status(self, batch_id: int, status: str):
        """Update batch status."""
        self.batch_repo.update_status(batch_id, status)
        logger.info("batch_status_updated", batch_id=batch_id, status=status)
    
    async def run(self):
        """Run the complete pipeline with resume support."""
        logger.info("cofi_service_starting", batch_date=self.settings.batch_date)
        
        # 1. Get or create batch
        batch = self.get_or_create_batch()
        batch_id = batch['id']
        self.batch_repo.set_batch_start_time(batch_id)
        
        # 2. File Distribution Stage
        if batch.get('dbInsertionStatus') != 'Complete':
            await self.distribute_files(batch)
        else:
            logger.info("file_distribution_skipped")
        
        # 3. Process callMetadata CSV (optional)
        if self.settings.callmetadata_enabled:
            if not self.metadata_manager.is_call_metadata_processed(batch_id):
                self.batch_repo.set_stage_start_time(batch_id, "callmetadata")
                try:
                    EventLogger.stage_start(batch_id, 'callmetadata')
                    count = self.metadata_manager.process_call_metadata_csv(batch_id)
                    self.batch_repo.update_callmetadata_status(batch_id, 1)
                    EventLogger.stage_complete(batch_id, 'callmetadata', count, 0, metadata={'records': count})
                    logger.info("callmetadata_processed", count=count)
                except Exception as e:
                    logger.error("callmetadata_failed", error=str(e))
                    EventLogger.file_error(batch_id, 'callmetadata', 'callMetadata.csv', str(e))
                finally:
                    self.batch_repo.set_stage_end_time(batch_id, "callmetadata")
            else:
                logger.info("callmetadata_already_processed")
        else:
            logger.info("callmetadata_stage_skipped")

        # 4. Process tradeMetadata CSV (optional)
        if self.settings.trademetadata_enabled:
            if not self.metadata_manager.is_trade_metadata_processed(batch_id):
                self.batch_repo.set_stage_start_time(batch_id, "trademetadata")
                try:
                    EventLogger.stage_start(batch_id, 'trademetadata')
                    count = self.metadata_manager.process_trade_metadata_csv(batch_id)
                    self.batch_repo.update_trademetadata_status(batch_id, 1)
                    EventLogger.stage_complete(batch_id, 'trademetadata', count, 0, metadata={'records': count})
                    logger.info("trademetadata_processed", count=count)
                except Exception as e:
                    logger.error("trademetadata_failed", error=str(e))
                    EventLogger.file_error(batch_id, 'trademetadata', 'tradeMetadata.csv', str(e))
                finally:
                    self.batch_repo.set_stage_end_time(batch_id, "trademetadata")
            else:
                logger.info("trademetadata_already_processed")
        else:
            logger.info("trademetadata_stage_skipped")
        
        # 5. Run pipeline stages
        previous_container = None
        
        # Stage: Denoise (optional)
        if self.settings.denoise_enabled:
            if batch.get('denoiseStatus') != 'Complete':
                self.batch_repo.update_denoise_status(batch_id, "InProgress")
                self.batch_repo.set_stage_start_time(batch_id, "denoise")
                denoise_stage = DenoiseStage()
                await denoise_stage.execute(batch_id, previous_container)
                self.batch_repo.update_denoise_status(batch_id, "Complete")
                self.batch_repo.set_stage_end_time(batch_id, "denoise")
                self.update_batch_status(batch_id, "denoiseDone")
            else:
                logger.info("denoise_stage_already_complete")
        else:
            logger.info("denoise_stage_skipped")
        
        # Stage: IVR (optional)
        if self.settings.ivr_enabled:
            if batch.get('ivrStatus') != 'Complete':
                self.batch_repo.update_ivr_status(batch_id, "InProgress")
                self.batch_repo.set_stage_start_time(batch_id, "ivr")
                ivr_stage = IVRStage()
                await ivr_stage.execute(batch_id, previous_container)
                self.batch_repo.update_ivr_status(batch_id, "Complete")
                self.batch_repo.set_stage_end_time(batch_id, "ivr")
                self.update_batch_status(batch_id, "ivrDone")
                previous_container = self.settings.ivr_container
            else:
                logger.info("ivr_stage_already_complete")
        else:
            logger.info("ivr_stage_skipped")
        
        # Stage: LID
        if batch.get('lidStatus') != 'Complete':
            self.batch_repo.update_lid_status(batch_id, "InProgress")
            self.batch_repo.set_stage_start_time(batch_id, "lid")
            lid_stage = LIDStage()
            await lid_stage.execute(batch_id, previous_container)
            self.batch_repo.update_lid_status(batch_id, "Complete")
            self.batch_repo.set_stage_end_time(batch_id, "lid")
            self.update_batch_status(batch_id, "lidDone")
            previous_container = self.settings.lid_container
        else:
            logger.info("lid_stage_already_complete")
        
        # Update Call records with LID results (language and duration)
        self.update_calls_from_lid(batch_id)
        
        # Stage: Rule Engine Step 1 - Trade to Audio Mapping (optional)
        if self.settings.rule_engine_enabled:
            if batch.get('triagingStatus') != 'Complete':
                self.batch_repo.update_triaging_status(batch_id, "InProgress")
                self.batch_repo.set_stage_start_time(batch_id, "triaging")
                try:
                    EventLogger.stage_start(batch_id, 'triaging', metadata={'step': 1, 'description': 'Trade to audio mapping'})
                    count = self.rule_engine.process(batch_id)

                    # Fill auditAnswer for calls without trade data
                    no_trade_count = self.rule_engine.fill_audio_not_found(batch_id)
                    logger.info("audio_not_found_filled", count=no_trade_count)

                    self.batch_repo.update_triaging_status(batch_id, "Complete")
                    self.update_batch_status(batch_id, "triagingDone")
                    EventLogger.stage_complete(batch_id, 'triaging', count, 0, metadata={
                        'mappings': count,
                        'no_trade_count': no_trade_count
                    })
                    logger.info("rule_engine_step1_done", mappings=count)
                except Exception as e:
                    logger.error("rule_engine_failed", error=str(e))
                    EventLogger.file_error(batch_id, 'triaging', 'rule_engine_step1', str(e))
                finally:
                    self.batch_repo.set_stage_end_time(batch_id, "triaging")
            else:
                logger.info("rule_engine_already_complete")
        else:
            logger.info("rule_engine_stage_skipped")
        
        # Stage: STT
        if batch.get('sttStatus') != 'Complete':
            self.batch_repo.update_stt_status(batch_id, "InProgress")
            self.batch_repo.set_stage_start_time(batch_id, "stt")
            stt_stage = STTStage()
            await stt_stage.execute(batch_id, previous_container)
            self.batch_repo.update_stt_status(batch_id, "Complete")
            self.batch_repo.set_stage_end_time(batch_id, "stt")
            self.update_batch_status(batch_id, "sttDone")
            previous_container = self.settings.stt_container
        else:
            logger.info("stt_stage_already_complete")
        
        # Stage: LLM1 (optional)
        if self.settings.llm1_enabled:
            if batch.get('llm1Status') != 'Complete':
                self.batch_repo.update_llm1_status(batch_id, "InProgress")
                self.batch_repo.set_stage_start_time(batch_id, "llm1")
                llm1_stage = LLM1Stage()
                await llm1_stage.execute(batch_id, previous_container)
                self.batch_repo.update_llm1_status(batch_id, "Complete")
                self.batch_repo.set_stage_end_time(batch_id, "llm1")
                self.update_batch_status(batch_id, "llm1Done")
            else:
                logger.info("llm1_stage_already_complete")
        else:
            logger.info("llm1_stage_skipped")
        
        # Stage: LLM2 (optional)
        if self.settings.llm2_enabled:
            if batch.get('llm2Status') != 'Complete':
                self.batch_repo.update_llm2_status(batch_id, "InProgress")
                self.batch_repo.set_stage_start_time(batch_id, "llm2")
                llm2_stage = LLM2Stage()
                await llm2_stage.execute(batch_id, previous_container)
                self.batch_repo.update_llm2_status(batch_id, "Complete")
                self.batch_repo.set_stage_end_time(batch_id, "llm2")
                self.update_batch_status(batch_id, "llm2Done")
            else:
                logger.info("llm2_stage_already_complete")
        else:
            logger.info("llm2_stage_skipped")
        
        # Stop final container
        await self.mediator.stop_all_containers(self.settings.llm2_container)
        
        # Stage: Rule Engine Step 2 (TODO: implement full logic)
        if self.settings.rule_engine_enabled:
            if batch.get('triagingStep2Status') != 'Complete':
                logger.info("rule_engine_step2_starting")
                self.batch_repo.set_stage_start_time(batch_id, "triaging_step2")
                # TODO: Add Rule Engine Step 2 implementation here
                self.batch_repo.update_triaging_step2_status(batch_id, "Complete")
                self.batch_repo.set_stage_end_time(batch_id, "triaging_step2")
                logger.info("rule_engine_step2_done")
            else:
                logger.info("rule_engine_step2_already_complete")
        else:
            logger.info("rule_engine_step2_skipped")
        
        # Mark batch complete
        self.update_batch_status(batch_id, "Completed")
        self.batch_repo.set_batch_end_time(batch_id)
        
        logger.info("pipeline_completed", batch_id=batch_id)


async def main():
    """Entry point."""
    orchestrator = CofiOrchestrator()
    await orchestrator.run()


if __name__ == "__main__":
    asyncio.run(main())
