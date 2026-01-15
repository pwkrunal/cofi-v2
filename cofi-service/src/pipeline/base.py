"""Base pipeline stage with common logic using mysql.connector."""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
import asyncio
import structlog

import json
from ..config import get_settings
from ..database import get_database, FileDistributionRepo, ProcessingLogRepo
from ..mediator_client import MediatorClient
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


class PipelineStage(ABC):
    """Base class for pipeline processing stages."""
    
    stage_name: str = ""
    container_name: str = ""
    wait_seconds: int = 60
    status_column: str = ""  # e.g., "ivrDone", "lidDone"
    api_endpoint: str = ""
    
    # Map stage_name to processing_logs ENUM value
    processing_log_stage: str = ""  # e.g., "denoise", "ivr", "lid", "stt", "llm1", "llm2"

    def __init__(self):
        self.settings = get_settings()
        self.mediator = MediatorClient()
        self.db = get_database()
        self.file_dist_repo = FileDistributionRepo(self.db)
        self.processing_log_repo = ProcessingLogRepo(self.db)

    def _get_request_url(self, gpu_ip: str) -> str:
        """Build full request URL for logging."""
        return f"http://{gpu_ip}:{self.settings.mediator_port}/{self.api_endpoint}"

    def log_processing_failure(
        self,
        call_id: str,
        batch_id: int,
        gpu_ip: str,
        error_message: str,
        input_payload: Optional[Dict] = None,
        output_payload: Optional[Dict] = None
    ):
        """Log failed processing to processing_logs table."""
        if not self.processing_log_stage:
            return  # Skip if stage not configured for processing logs
        try:
            self.processing_log_repo.log_failure(
                call_id=call_id,
                batch_id=str(batch_id),
                stage_name=self.processing_log_stage,
                error_message=error_message,
                request_url=self._get_request_url(gpu_ip),
                input_payload=_safe_json_serialize(input_payload),
                output_payload=_safe_json_serialize(output_payload)
            )
        except Exception as e:
            logger.error("processing_log_failed", stage=self.stage_name, call_id=call_id, error=str(e))

    def log_processing_success(
        self,
        call_id: str,
        batch_id: int,
        gpu_ip: str,
        input_payload: Optional[Dict] = None,
        output_payload: Optional[Dict] = None
    ):
        """Log successful processing to processing_logs table."""
        if not self.processing_log_stage:
            return  # Skip if stage not configured for processing logs
        try:
            self.processing_log_repo.log_success(
                call_id=call_id,
                batch_id=str(batch_id),
                stage_name=self.processing_log_stage,
                request_url=self._get_request_url(gpu_ip),
                input_payload=_safe_json_serialize(input_payload),
                output_payload=_safe_json_serialize(output_payload)
            )
        except Exception as e:
            logger.error("processing_log_success_failed", stage=self.stage_name, call_id=call_id, error=str(e))
    
    @abstractmethod
    def build_payload(self, file_name: str) -> Dict[str, Any]:
        """Build API request payload for a file."""
        pass
    
    @abstractmethod
    def process_response(self, file_name: str, response: Dict[str, Any], gpu_ip: str, batch_id: int):
        """Process API response and update database if needed."""
        pass
    
    def get_pending_files(self, batch_id: int) -> Dict[str, List[str]]:
        """
        Get files that need processing for this stage.
        
        Returns:
            Dict mapping GPU IP to list of files pending for this stage
        """
        records = self.file_dist_repo.get_pending_for_stage(batch_id, self.status_column)
        
        # Group by GPU IP
        file_gpu_mapping: Dict[str, List[str]] = {}
        for record in records:
            ip = record['ip']
            if ip not in file_gpu_mapping:
                file_gpu_mapping[ip] = []
            file_gpu_mapping[ip].append(record['file'])
        
        return file_gpu_mapping
    
    def mark_files_complete(self, file_names: List[str], batch_id: int):
        """Mark files as complete for this stage."""
        self.file_dist_repo.mark_stage_done(file_names, batch_id, self.status_column)
        logger.info("files_marked_complete", stage=self.stage_name, count=len(file_names))
    
    async def execute(self, batch_id: int, previous_container: Optional[str] = None):
        """
        Execute this pipeline stage.

        Args:
            batch_id: Current batch ID
            previous_container: Container from previous stage to stop first
        """
        logger.info("stage_starting", stage=self.stage_name)

        # 1. Stop previous container on all GPUs (if any)
        if previous_container:
            logger.info("stopping_previous_container", container=previous_container)
            EventLogger.info(batch_id, self.stage_name, f"Stopping previous container: {previous_container}")
            await self.mediator.stop_all_containers(previous_container)

        # 2. Get pending files for this stage
        file_gpu_mapping = self.get_pending_files(batch_id)

        if not file_gpu_mapping:
            logger.info("no_pending_files", stage=self.stage_name)
            EventLogger.info(batch_id, self.stage_name, "No pending files for processing")
            return

        total_files = sum(len(files) for files in file_gpu_mapping.values())
        logger.info("pending_files_found", stage=self.stage_name, count=total_files)

        # Log stage start
        EventLogger.stage_start(batch_id, self.stage_name, total_files=total_files, metadata={
            'container': self.container_name,
            'api_endpoint': self.api_endpoint
        })

        # 3. Start this stage's container on all GPUs
        logger.info("starting_containers", container=self.container_name)
        EventLogger.info(batch_id, self.stage_name, f"Starting containers: {self.container_name}")
        await self.mediator.start_all_containers(self.container_name)

        # 4. Wait for container startup
        logger.info("waiting_for_startup", seconds=self.wait_seconds)
        EventLogger.info(batch_id, self.stage_name, f"Waiting {self.wait_seconds}s for container startup")
        await asyncio.sleep(self.wait_seconds)

        # 5. Process all files in parallel
        EventLogger.info(batch_id, self.stage_name, f"Processing {total_files} files in parallel")
        results = await self.mediator.process_files_parallel(
            file_gpu_mapping,
            self.api_endpoint,
            self.build_payload
        )

        # 6. Process responses and update database
        successful_files = []
        # Get progress interval from settings (configurable for large batches)
        progress_interval = self.settings.progress_update_interval

        for idx, (file_name, result_data) in enumerate(results.items(), 1):
            result = result_data.get("result")
            gpu_ip = result_data.get("gpu")

            # Build payload for logging
            payload = None
            try:
                payload = self.build_payload(file_name)
            except Exception as e:
                logger.error("payload_build_failed", file=file_name, error=str(e))

            # Log file start (with payload) - optional for large batches
            if self.settings.log_file_start_events and payload:
                EventLogger.file_start(batch_id, self.stage_name, file_name, gpu_ip, payload)

            if isinstance(result, Exception):
                logger.error("file_processing_failed", file=file_name, error=str(result))
                EventLogger.file_error(batch_id, self.stage_name, file_name, str(result), gpu_ip)
                # Log failure to processing_logs - continues without stopping
                self.log_processing_failure(
                    call_id=file_name,
                    batch_id=batch_id,
                    gpu_ip=gpu_ip or "",
                    error_message=str(result),
                    input_payload=payload
                )
            else:
                # Log file complete (with response)
                EventLogger.file_complete(batch_id, self.stage_name, file_name, gpu_ip, result, status='success')

                # Log success to processing_logs
                self.log_processing_success(
                    call_id=file_name,
                    batch_id=batch_id,
                    gpu_ip=gpu_ip or "",
                    input_payload=payload,
                    output_payload=result
                )

                self.process_response(file_name, result, gpu_ip, batch_id)
                successful_files.append(file_name)

            # Periodic progress update (every N files)
            if idx % progress_interval == 0 or idx == total_files:
                EventLogger.stage_progress(
                    batch_id,
                    self.stage_name,
                    processed_files=len(successful_files),
                    total_files=total_files,
                    metadata={'files_processed': idx, 'success_rate': len(successful_files) / idx * 100}
                )

        # 7. Mark successful files as complete
        if successful_files:
            self.mark_files_complete(successful_files, batch_id)

        failed_count = total_files - len(successful_files)

        # Log stage complete
        EventLogger.stage_complete(batch_id, self.stage_name, len(successful_files), failed_count, metadata={
            'total_files': total_files,
            'container': self.container_name
        })

        logger.info("stage_completed", stage=self.stage_name, processed=len(successful_files), failed=failed_count)
