"""MySQL database connection and operations using mysql.connector."""
import mysql.connector
from mysql.connector import pooling
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
import structlog

from .config import get_settings

logger = structlog.get_logger()


class Database:
    """Database connection manager using mysql.connector with connection pooling."""
    
    def __init__(self):
        settings = get_settings()
        self.pool = pooling.MySQLConnectionPool(
            pool_name="cofi_pool",
            pool_size=5,
            pool_reset_session=True,
            host=settings.mysql_host,
            port=settings.mysql_port,
            user=settings.mysql_user,
            password=settings.mysql_password,
            database=settings.mysql_database
        )
        logger.info("database_pool_created", host=settings.mysql_host, database=settings.mysql_database)
    
    def get_connection(self):
        """Get a connection from the pool."""
        return self.pool.get_connection()
    
    def execute_query(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        """Execute a SELECT query and return results as list of dicts."""
        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(query, params)
            results = cursor.fetchall()
            return results
        finally:
            cursor.close()
            conn.close()
    
    def execute_one(self, query: str, params: tuple = None) -> Optional[Dict[str, Any]]:
        """Execute a SELECT query and return single result."""
        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(query, params)
            result = cursor.fetchone()
            return result
        finally:
            cursor.close()
            conn.close()
    
    def execute_update(self, query: str, params: tuple = None) -> int:
        """Execute an INSERT/UPDATE/DELETE query and return affected rows."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(query, params)
            conn.commit()
            return cursor.rowcount
        finally:
            cursor.close()
            conn.close()
    
    def execute_insert(self, query: str, params: tuple = None) -> int:
        """Execute an INSERT query and return the last inserted ID."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(query, params)
            conn.commit()
            return cursor.lastrowid
        finally:
            cursor.close()
            conn.close()
    
    def execute_many(self, query: str, params_list: List[tuple]) -> int:
        """Execute a query with multiple parameter sets."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.executemany(query, params_list)
            conn.commit()
            return cursor.rowcount
        finally:
            cursor.close()
            conn.close()


# Database singleton
_db: Optional[Database] = None


def get_database() -> Database:
    """Get or create database instance."""
    global _db
    if _db is None:
        _db = Database()
    return _db


# Repository functions for specific tables

class BatchStatusRepo:
    """Repository for batchStatus table operations."""
    
    def __init__(self, db: Database):
        self.db = db
    
    def get_by_date_and_number(self, batch_date: str, batch_number: int) -> Optional[Dict]:
        """Get batch by date and number."""
        query = """
            SELECT * FROM batchStatus 
            WHERE batchDate = %s AND batchNumber = %s
        """
        return self.db.execute_one(query, (batch_date, batch_number))
    
    def create(self, batch_date: str, batch_number: int) -> int:
        """Create a new batch record."""
        query = """
            INSERT INTO batchStatus (batchDate, batchNumber, status, totalFiles, processedFiles)
            VALUES (%s, %s, 'Pending', 0, 0)
        """
        return self.db.execute_insert(query, (batch_date, batch_number))
    
    def update_status(self, batch_id: int, status: str):
        """Update batch status."""
        query = "UPDATE batchStatus SET status = %s WHERE id = %s"
        self.db.execute_update(query, (status, batch_id))
    
    # Stage-specific status columns (enum: 'Pending', 'InProgress', 'Complete')
    
    def update_db_insertion_status(self, batch_id: int, status: str):
        """Update database insertion status."""
        query = "UPDATE batchStatus SET dbInsertionStatus = %s WHERE id = %s"
        self.db.execute_update(query, (status, batch_id))
    
    def update_denoise_status(self, batch_id: int, status: str):
        """Update denoise status."""
        query = "UPDATE batchStatus SET denoiseStatus = %s WHERE id = %s"
        self.db.execute_update(query, (status, batch_id))
    
    def update_ivr_status(self, batch_id: int, status: str):
        """Update ivrStatus column for IVR stage."""
        query = "UPDATE batchStatus SET ivrStatus = %s WHERE id = %s"
        self.db.execute_update(query, (status, batch_id))
    
    def update_lid_status(self, batch_id: int, status: str):
        """Update lidStatus column for LID stage."""
        query = "UPDATE batchStatus SET lidStatus = %s WHERE id = %s"
        self.db.execute_update(query, (status, batch_id))
    
    def update_triaging_status(self, batch_id: int, status: str):
        """Update triagingStatus column for Rule Engine Step 1."""
        query = "UPDATE batchStatus SET triagingStatus = %s WHERE id = %s"
        self.db.execute_update(query, (status, batch_id))
    
    def update_stt_status(self, batch_id: int, status: str):
        """Update sttStatus column for STT stage."""
        query = "UPDATE batchStatus SET sttStatus = %s WHERE id = %s"
        self.db.execute_update(query, (status, batch_id))
    
    def update_llm1_status(self, batch_id: int, status: str):
        """Update llm1Status column for LLM1 stage."""
        query = "UPDATE batchStatus SET llm1Status = %s WHERE id = %s"
        self.db.execute_update(query, (status, batch_id))
    
    def update_llm2_status(self, batch_id: int, status: str):
        """Update llm2Status column for LLM2 stage."""
        query = "UPDATE batchStatus SET llm2Status = %s WHERE id = %s"
        self.db.execute_update(query, (status, batch_id))
    
    def update_callmetadata_status(self, batch_id: int, status: int = 1):
        """Update callmetadataStatus column (integer)."""
        query = "UPDATE batchStatus SET callmetadataStatus = %s WHERE id = %s"
        self.db.execute_update(query, (status, batch_id))
    
    def update_trademetadata_status(self, batch_id: int, status: int = 1):
        """Update trademetadataStatus column (integer)."""
        query = "UPDATE batchStatus SET trademetadataStatus = %s WHERE id = %s"
        self.db.execute_update(query, (status, batch_id))
    
    def update_triaging_step2_status(self, batch_id: int, status: str = "Complete"):
        """Update triagingStep2Status column for Rule Engine Step 2."""
        query = "UPDATE batchStatus SET triagingStep2Status = %s WHERE id = %s"
        self.db.execute_update(query, (status, batch_id))
    
    def update_total_files(self, batch_id: int, total_files: int):
        """Update total files count."""
        query = "UPDATE batchStatus SET totalFiles = %s, status = 'dbInsertDone' WHERE id = %s"
        self.db.execute_update(query, (total_files, batch_id))


class FileDistributionRepo:
    """Repository for fileDistribution table operations."""
    
    def __init__(self, db: Database):
        self.db = db
    
    def get_by_batch(self, batch_id: int) -> List[Dict]:
        """Get all file distributions for a batch."""
        query = "SELECT * FROM fileDistribution WHERE batchId = %s"
        return self.db.execute_query(query, (batch_id,))
    
    def get_pending_for_stage(self, batch_id: int, stage_column: str) -> List[Dict]:
        """Get files pending for a specific stage."""
        query = f"SELECT * FROM fileDistribution WHERE batchId = %s AND {stage_column} = 0"
        return self.db.execute_query(query, (batch_id,))
    
    def insert(self, file_name: str, ip: str, batch_id: int) -> int:
        """Insert a new file distribution record."""
        query = """
            INSERT INTO fileDistribution (file, ip, batchId, denoiseDone, ivrDone, lidDone, sttDone, llm1Done, llm2Done)
            VALUES (%s, %s, %s, 0, 0, 0, 0, 0, 0)
        """
        return self.db.execute_insert(query, (file_name, ip, batch_id))
    
    def mark_stage_done(self, file_names: List[str], batch_id: int, stage_column: str):
        """Mark multiple files as done for a specific stage."""
        if not file_names:
            return
        placeholders = ', '.join(['%s'] * len(file_names))
        query = f"""
            UPDATE fileDistribution 
            SET {stage_column} = 1 
            WHERE file IN ({placeholders}) AND batchId = %s
        """
        params = tuple(file_names) + (batch_id,)
        self.db.execute_update(query, params)
    
    def reset_stage_for_file(self, file_name: str, stage_column: str):
        """Reset a stage to 0 for a specific file (for reaudit)."""
        query = f"UPDATE fileDistribution SET {stage_column} = 0 WHERE file = %s"
        self.db.execute_update(query, (file_name,))


class LidStatusRepo:
    """Repository for lidStatus table operations."""
    
    def __init__(self, db: Database):
        self.db = db
    
    def insert(self, audio_name: str, language: str, audio_duration: float, batch_id: int, ip: str) -> int:
        """Insert a new LID status record."""
        query = """
            INSERT INTO lidStatus (audioName, language, audioDuration, batchId, ip)
            VALUES (%s, %s, %s, %s, %s)
        """
        return self.db.execute_insert(query, (audio_name, language, audio_duration, batch_id, ip))
    
    def get_by_batch(self, batch_id: int) -> List[Dict]:
        """Get all LID records for a batch."""
        query = "SELECT * FROM lidStatus WHERE batchId = %s"
        return self.db.execute_query(query, (batch_id,))


class LanguageRepo:
    """Repository for language table operations."""
    
    def __init__(self, db: Database):
        self.db = db
    
    def get_by_code(self, language_code: str) -> Optional[Dict]:
        """Get language by language code."""
        query = "SELECT * FROM `language` WHERE languageCode = %s"
        return self.db.execute_one(query, (language_code,))
    
    def get_id_by_code(self, language_code: str) -> Optional[int]:
        """Get language ID by language code."""
        result = self.get_by_code(language_code)
        return result['id'] if result else None


class ProcessRepo:
    """Repository for process table operations."""
    
    def __init__(self, db: Database):
        self.db = db
    
    def get_by_id(self, process_id: int) -> Optional[Dict]:
        """Get process by ID."""
        query = "SELECT * FROM `process` WHERE id = %s"
        return self.db.execute_one(query, (process_id,))
    
    def get_audit_form_id(self, process_id: int) -> Optional[int]:
        """Get auditFormId for a process."""
        result = self.get_by_id(process_id)
        return result['auditFormId'] if result else None


class CallRepo:
    """Repository for call table operations."""
    
    def __init__(self, db: Database):
        self.db = db
    
    def get_by_audio_name(self, audio_name: str, batch_id: int) -> Optional[Dict]:
        """Get call by audio name."""
        query = "SELECT * FROM `call` WHERE audioName = %s AND batchId = %s"
        return self.db.execute_one(query, (audio_name, batch_id))
    
    def get_by_status(self, batch_id: int, status: str) -> List[Dict]:
        """Get calls by status for a batch."""
        query = "SELECT * FROM `call` WHERE batchId = %s AND status = %s"
        return self.db.execute_query(query, (batch_id, status))
    
    def insert(
        self,
        audio_name: str,
        audio_duration: float,
        lang: str,
        batch_id: int,
        ip: str,
        process_id: int,
        user_id: int,
        category_mapping_id: int,
        audio_url: str,
        audit_form_id: Optional[int],
        language_id: Optional[int]
    ) -> int:
        """Insert a new call record with all required fields."""
        query = """
            INSERT INTO `call` (
                audioName, audioDuration, lang, status, batchId, ip,
                processId, userId, categoryMappingId, audioUrl, 
                auditFormId, languageId, type
            )
            VALUES (%s, %s, %s, 'Pending', %s, %s, %s, %s, %s, %s, %s, %s, 'Call')
        """
        return self.db.execute_insert(query, (
            audio_name, audio_duration, lang, batch_id, ip,
            process_id, user_id, category_mapping_id, audio_url,
            audit_form_id, language_id
        ))
    
    def update_status(self, audio_name: str, current_status: str, new_status: str):
        """Update call status."""
        query = "UPDATE `call` SET status = %s WHERE audioName = %s AND status = %s"
        self.db.execute_update(query, (new_status, audio_name, current_status))
    
    def bulk_update_status(self, audio_names: List[str], current_status: str, new_status: str):
        """Update status for multiple calls."""
        if not audio_names:
            return
        placeholders = ', '.join(['%s'] * len(audio_names))
        query = f"""
            UPDATE `call` SET status = %s 
            WHERE audioName IN ({placeholders}) AND status = %s
        """
        params = (new_status,) + tuple(audio_names) + (current_status,)
        self.db.execute_update(query, params)
    
    def get_by_audio_name_any_batch(self, audio_name: str) -> Optional[Dict]:
        """Get call by audio name (any batch - for reaudit)."""
        query = "SELECT * FROM `call` WHERE audioName = %s ORDER BY id DESC LIMIT 1"
        return self.db.execute_one(query, (audio_name,))
    
    def update_status_by_id(self, call_id: int, new_status: str):
        """Update call status by ID."""
        query = "UPDATE `call` SET status = %s WHERE id = %s"
        self.db.execute_update(query, (new_status, call_id))

    def update_lid_info(self, audio_name: str, batch_id: int, language_id: Optional[int],
                       lang_code: str, audio_duration: float):
        """Update language_id, lang, and audio_duration from LID results."""
        query = """
            UPDATE `call`
            SET languageId = %s, lang = %s, audioDuration = %s
            WHERE audioName = %s AND batchId = %s
        """
        self.db.execute_update(query, (language_id, lang_code, audio_duration, audio_name, batch_id))

    def insert_from_distribution(
        self,
        audio_name: str,
        batch_id: int,
        ip: str,
        process_id: int,
        category_mapping_id: int,
        audio_endpoint: str,
        audit_form_id: Optional[int]
    ) -> int:
        """
        Insert call record during file distribution stage.
        Language info and duration will be updated after LID stage.
        """
        # Build audio URL
        audio_url = f"{audio_endpoint}/{audio_name}"

        query = """
            INSERT INTO `call` (
                audioName, audioDuration, lang, status, batchId, ip,
                processId, userId, categoryMappingId, audioUrl,
                auditFormId, languageId, type
            )
            VALUES (%s, %s, %s, 'Pending', %s, %s, %s, %s, %s, %s, %s, %s, 'Call')
        """
        # Initial values: duration=0, lang='unknown', userId=1 (default), languageId=NULL
        return self.db.execute_insert(query, (
            audio_name, 0, 'unknown', batch_id, ip,
            process_id, 1, category_mapping_id, audio_url,
            audit_form_id, None
        ))


class TranscriptRepo:
    """Repository for transcript table operations."""
    
    def __init__(self, db: Database):
        self.db = db
    
    def insert(
        self,
        call_id: int,
        language_id: Optional[int],
        start_time: float,
        end_time: float,
        speaker: str,
        text: str,
        confidence: Optional[float] = None
    ) -> int:
        """Insert a single transcript record."""
        query = """
            INSERT INTO transcript (callId, languageId, startTime, endTime, speaker, text, confidence)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        return self.db.execute_insert(query, (
            call_id, language_id, start_time, end_time, speaker, text, confidence
        ))
    
    def insert_many(self, records: List[Dict[str, Any]]) -> int:
        """Insert multiple transcript records."""
        if not records:
            return 0
        
        query = """
            INSERT INTO transcript (callId, languageId, startTime, endTime, speaker, text, confidence)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        
        params_list = []
        for record in records:
            params = (
                record.get('callId'),
                record.get('languageId'),
                record.get('startTime'),
                record.get('endTime'),
                record.get('speaker'),
                record.get('text'),
                record.get('confidence')
            )
            params_list.append(params)
        
        return self.db.execute_many(query, params_list)
    
    def get_by_call_id(self, call_id: int) -> List[Dict]:
        """Get all transcript records for a call."""
        query = "SELECT * FROM transcript WHERE callId = %s ORDER BY startTime"
        return self.db.execute_query(query, (call_id,))
    
    def delete_by_call_id(self, call_id: int) -> int:
        """Delete all transcripts for a call (for reaudit)."""
        query = "DELETE FROM transcript WHERE callId = %s"
        return self.db.execute_update(query, (call_id,))


class BatchExecutionLogRepo:
    """Repository for batchExecutionLog table operations."""

    def __init__(self, db: Database):
        self.db = db

    def insert_event(
        self,
        batch_id: int,
        stage: str,
        event_type: str,
        file_name: Optional[str] = None,
        gpu_ip: Optional[str] = None,
        payload: Optional[str] = None,
        response: Optional[str] = None,
        status: str = 'processing',
        error_message: Optional[str] = None,
        total_files: Optional[int] = None,
        processed_files: Optional[int] = None,
        metadata: Optional[str] = None
    ) -> int:
        """
        Insert a batch execution log event.

        Args:
            batch_id: Batch ID
            stage: Stage name (lid, stt, file_distribution, etc.)
            event_type: Event type (stage_start, file_complete, error, etc.)
            file_name: File name (optional, for file-level events)
            gpu_ip: GPU IP address (optional)
            payload: JSON string of request payload (optional)
            response: JSON string of response data (optional)
            status: Event status (pending, processing, success, failed)
            error_message: Error message (optional)
            total_files: Total files count (optional, for stage_start)
            processed_files: Processed files count (optional, for stage_progress/complete)
            metadata: JSON string of additional metadata (optional)

        Returns:
            Inserted event ID
        """
        query = """
            INSERT INTO batchExecutionLog (
                batchId, stage, eventType, fileName, gpuIp,
                payload, response, status, errorMessage,
                totalFiles, processedFiles, metadata
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = (
            batch_id, stage, event_type, file_name, gpu_ip,
            payload, response, status, error_message,
            total_files, processed_files, metadata
        )
        return self.db.execute_insert(query, params)

    def get_by_batch(self, batch_id: int, limit: int = 1000) -> List[Dict]:
        """
        Get all execution log events for a batch.

        Args:
            batch_id: Batch ID
            limit: Maximum number of events to return

        Returns:
            List of event records ordered by timestamp descending
        """
        query = """
            SELECT * FROM batchExecutionLog
            WHERE batchId = %s
            ORDER BY timestamp DESC
            LIMIT %s
        """
        return self.db.execute_query(query, (batch_id, limit))

    def get_latest_events(
        self,
        batch_id: int,
        since_id: Optional[int] = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        Get latest events for a batch since a specific event ID.
        Used for SSE streaming to get new events.

        Args:
            batch_id: Batch ID
            since_id: Get events with ID greater than this (optional)
            limit: Maximum number of events to return

        Returns:
            List of event records ordered by ID ascending (chronological)
        """
        if since_id is not None:
            query = """
                SELECT * FROM batchExecutionLog
                WHERE batchId = %s AND id > %s
                ORDER BY id ASC
                LIMIT %s
            """
            return self.db.execute_query(query, (batch_id, since_id, limit))
        else:
            query = """
                SELECT * FROM batchExecutionLog
                WHERE batchId = %s
                ORDER BY id DESC
                LIMIT %s
            """
            results = self.db.execute_query(query, (batch_id, limit))
            # Reverse to get chronological order
            return list(reversed(results))

    def get_current_stage_stats(self, batch_id: int, stage: str) -> Dict[str, Any]:
        """
        Get aggregated statistics for a specific stage.

        Args:
            batch_id: Batch ID
            stage: Stage name

        Returns:
            Dictionary with total_files, processed_files, errors counts
        """
        query = """
            SELECT
                MAX(totalFiles) as total_files,
                MAX(processedFiles) as processed_files,
                SUM(CASE WHEN eventType = 'error' THEN 1 ELSE 0 END) as error_count
            FROM batchExecutionLog
            WHERE batchId = %s AND stage = %s
        """
        result = self.db.execute_one(query, (batch_id, stage))
        return result if result else {'total_files': 0, 'processed_files': 0, 'error_count': 0}

    def get_by_stage(self, batch_id: int, stage: str, limit: int = 500) -> List[Dict]:
        """
        Get all events for a specific stage.

        Args:
            batch_id: Batch ID
            stage: Stage name
            limit: Maximum number of events

        Returns:
            List of event records for the stage
        """
        query = """
            SELECT * FROM batchExecutionLog
            WHERE batchId = %s AND stage = %s
            ORDER BY timestamp DESC
            LIMIT %s
        """
        return self.db.execute_query(query, (batch_id, stage, limit))
