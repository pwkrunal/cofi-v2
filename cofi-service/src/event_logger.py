"""Event logging module for batch processing pipeline monitoring."""
import json
from typing import Optional, Dict, Any
from datetime import datetime
import structlog

from .database import get_database

logger = structlog.get_logger()


class EventLogger:
    """
    Centralized event logger for batch processing pipeline.
    Logs detailed execution events to batchExecutionLog table for dashboard monitoring.
    """

    @staticmethod
    def _get_repo():
        """Get BatchExecutionLogRepo instance."""
        from .database import BatchExecutionLogRepo
        db = get_database()
        return BatchExecutionLogRepo(db)

    @staticmethod
    def _serialize_data(data: Any) -> Optional[str]:
        """Serialize data to JSON string."""
        if data is None:
            return None
        try:
            return json.dumps(data, default=str)
        except Exception as e:
            logger.error("event_logger_serialization_failed", error=str(e))
            return str(data)

    @staticmethod
    def stage_start(
        batch_id: int,
        stage: str,
        total_files: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Log stage start event.

        Args:
            batch_id: Batch ID
            stage: Stage name (e.g., 'lid', 'stt', 'file_distribution')
            total_files: Total number of files to process
            metadata: Additional metadata dictionary
        """
        try:
            repo = EventLogger._get_repo()
            repo.insert_event(
                batch_id=batch_id,
                stage=stage,
                event_type='stage_start',
                status='processing',
                total_files=total_files,
                metadata=EventLogger._serialize_data(metadata)
            )
            logger.info("event_logged", event_type="stage_start", stage=stage, batch_id=batch_id)
        except Exception as e:
            logger.error("event_logging_failed", event_type="stage_start", stage=stage, error=str(e))

    @staticmethod
    def stage_complete(
        batch_id: int,
        stage: str,
        processed_files: int,
        failed_files: int = 0,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Log stage completion event.

        Args:
            batch_id: Batch ID
            stage: Stage name
            processed_files: Number of files successfully processed
            failed_files: Number of files that failed
            metadata: Additional metadata (durations, stats, etc.)
        """
        try:
            repo = EventLogger._get_repo()
            status = 'success' if failed_files == 0 else 'failed'
            repo.insert_event(
                batch_id=batch_id,
                stage=stage,
                event_type='stage_complete',
                status=status,
                processed_files=processed_files,
                metadata=EventLogger._serialize_data(metadata)
            )
            logger.info(
                "event_logged",
                event_type="stage_complete",
                stage=stage,
                batch_id=batch_id,
                processed=processed_files,
                failed=failed_files
            )
        except Exception as e:
            logger.error("event_logging_failed", event_type="stage_complete", stage=stage, error=str(e))

    @staticmethod
    def stage_progress(
        batch_id: int,
        stage: str,
        processed_files: int,
        total_files: int,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Log stage progress event.

        Args:
            batch_id: Batch ID
            stage: Stage name
            processed_files: Number of files processed so far
            total_files: Total number of files
            metadata: Additional metadata
        """
        try:
            repo = EventLogger._get_repo()
            repo.insert_event(
                batch_id=batch_id,
                stage=stage,
                event_type='stage_progress',
                status='processing',
                processed_files=processed_files,
                total_files=total_files,
                metadata=EventLogger._serialize_data(metadata)
            )
            logger.debug(
                "event_logged",
                event_type="stage_progress",
                stage=stage,
                progress=f"{processed_files}/{total_files}"
            )
        except Exception as e:
            logger.error("event_logging_failed", event_type="stage_progress", stage=stage, error=str(e))

    @staticmethod
    def file_start(
        batch_id: int,
        stage: str,
        file_name: str,
        gpu_ip: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None
    ):
        """
        Log file processing start event.

        Args:
            batch_id: Batch ID
            stage: Stage name
            file_name: Name of the file being processed
            gpu_ip: GPU IP address where file is being processed
            payload: Request payload sent to processing API
        """
        try:
            repo = EventLogger._get_repo()
            repo.insert_event(
                batch_id=batch_id,
                stage=stage,
                event_type='file_start',
                file_name=file_name,
                gpu_ip=gpu_ip,
                status='processing',
                payload=EventLogger._serialize_data(payload)
            )
            logger.debug(
                "event_logged",
                event_type="file_start",
                stage=stage,
                file=file_name,
                gpu=gpu_ip
            )
        except Exception as e:
            logger.error("event_logging_failed", event_type="file_start", file=file_name, error=str(e))

    @staticmethod
    def file_complete(
        batch_id: int,
        stage: str,
        file_name: str,
        gpu_ip: Optional[str] = None,
        response: Optional[Dict[str, Any]] = None,
        status: str = 'success'
    ):
        """
        Log file processing completion event.

        Args:
            batch_id: Batch ID
            stage: Stage name
            file_name: Name of the file processed
            gpu_ip: GPU IP address
            response: Response data from processing API
            status: 'success' or 'failed'
        """
        try:
            repo = EventLogger._get_repo()
            repo.insert_event(
                batch_id=batch_id,
                stage=stage,
                event_type='file_complete',
                file_name=file_name,
                gpu_ip=gpu_ip,
                status=status,
                response=EventLogger._serialize_data(response)
            )
            logger.debug(
                "event_logged",
                event_type="file_complete",
                stage=stage,
                file=file_name,
                status=status
            )
        except Exception as e:
            logger.error("event_logging_failed", event_type="file_complete", file=file_name, error=str(e))

    @staticmethod
    def file_error(
        batch_id: int,
        stage: str,
        file_name: str,
        error_message: str,
        gpu_ip: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None
    ):
        """
        Log file processing error event.

        Args:
            batch_id: Batch ID
            stage: Stage name
            file_name: Name of the file that failed
            error_message: Error message or exception details
            gpu_ip: GPU IP address
            payload: Request payload that was sent
        """
        try:
            repo = EventLogger._get_repo()
            repo.insert_event(
                batch_id=batch_id,
                stage=stage,
                event_type='error',
                file_name=file_name,
                gpu_ip=gpu_ip,
                status='failed',
                error_message=error_message,
                payload=EventLogger._serialize_data(payload)
            )
            logger.warning(
                "event_logged",
                event_type="error",
                stage=stage,
                file=file_name,
                error=error_message
            )
        except Exception as e:
            logger.error("event_logging_failed", event_type="error", file=file_name, error=str(e))

    @staticmethod
    def info(
        batch_id: int,
        stage: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Log informational event.

        Args:
            batch_id: Batch ID
            stage: Stage name
            message: Info message
            metadata: Additional data
        """
        try:
            repo = EventLogger._get_repo()
            repo.insert_event(
                batch_id=batch_id,
                stage=stage,
                event_type='info',
                status='success',
                error_message=message,  # Reusing errorMessage field for info messages
                metadata=EventLogger._serialize_data(metadata)
            )
            logger.info("event_logged", event_type="info", stage=stage, message=message)
        except Exception as e:
            logger.error("event_logging_failed", event_type="info", stage=stage, error=str(e))
