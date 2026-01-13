"""Database operations for cofi-dashboard (read-only)."""
import mysql.connector
from mysql.connector import pooling
from typing import Optional, List, Dict, Any
import structlog

from .config import get_settings

logger = structlog.get_logger()


class Database:
    """Database connection manager with connection pooling."""

    def __init__(self):
        settings = get_settings()
        self.pool = pooling.MySQLConnectionPool(
            pool_name="dashboard_pool",
            pool_size=5,
            pool_reset_session=True,
            host=settings.mysql_host,
            port=settings.mysql_port,
            user=settings.mysql_user,
            password=settings.mysql_password,
            database=settings.mysql_database
        )
        logger.info("dashboard_database_pool_created", host=settings.mysql_host)

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


# Database singleton
_db: Optional[Database] = None


def get_database() -> Database:
    """Get or create database instance."""
    global _db
    if _db is None:
        _db = Database()
    return _db


class BatchStatusRepo:
    """Repository for reading batchStatus table."""

    def __init__(self, db: Database):
        self.db = db

    def get_current_batch(self) -> Optional[Dict]:
        """
        Get the current batch being processed.

        Priority:
        1. Batch with currentBatch = 1 (active batch flag)
        2. Batch with any stage status = 'InProgress'
        3. Batch with batchStatus != 'Complete'
        4. Most recent batch by ID
        """
        # Priority 1: Check for currentBatch flag (best indicator)
        query = """
            SELECT * FROM batchStatus
            WHERE currentBatch = 1
            ORDER BY id DESC
            LIMIT 1
        """
        batch = self.db.execute_one(query)

        if batch:
            return batch

        # Priority 2: Find a batch with any InProgress stage
        query = """
            SELECT * FROM batchStatus
            WHERE dbInsertionStatus = 'InProgress'
               OR denoiseStatus = 'InProgress'
               OR ivrStatus = 'InProgress'
               OR lidStatus = 'InProgress'
               OR sttStatus = 'InProgress'
               OR llm1Status = 'InProgress'
               OR llm2Status = 'InProgress'
               OR triagingStatus = 'InProgress'
               OR triagingStep2Status = 'InProgress'
            ORDER BY id DESC
            LIMIT 1
        """
        batch = self.db.execute_one(query)

        if batch:
            return batch

        # Priority 3: Find the most recent non-Complete batch
        query = """
            SELECT * FROM batchStatus
            WHERE batchStatus != 'Complete'
            ORDER BY id DESC
            LIMIT 1
        """
        batch = self.db.execute_one(query)

        if batch:
            return batch

        # Priority 4: Fallback - return the most recent batch (even if completed)
        query = """
            SELECT * FROM batchStatus
            ORDER BY id DESC
            LIMIT 1
        """
        return self.db.execute_one(query)

    def get_by_id(self, batch_id: int) -> Optional[Dict]:
        """Get batch by ID."""
        query = "SELECT * FROM batchStatus WHERE id = %s"
        return self.db.execute_one(query, (batch_id,))


class BatchExecutionLogRepo:
    """Repository for reading batchExecutionLog table."""

    def __init__(self, db: Database):
        self.db = db

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

    def get_stage_stats(self, batch_id: int) -> Dict[str, Dict[str, int]]:
        """
        Get aggregated statistics for all stages in a batch.

        Args:
            batch_id: Batch ID

        Returns:
            Dictionary mapping stage name to stats (total, processed, errors)
        """
        query = """
            SELECT
                stage,
                MAX(totalFiles) as total_files,
                MAX(processedFiles) as processed_files,
                SUM(CASE WHEN eventType = 'error' THEN 1 ELSE 0 END) as error_count
            FROM batchExecutionLog
            WHERE batchId = %s
            GROUP BY stage
        """
        results = self.db.execute_query(query, (batch_id,))

        stats = {}
        for row in results:
            stats[row['stage']] = {
                'total': row['total_files'] or 0,
                'processed': row['processed_files'] or 0,
                'errors': row['error_count'] or 0
            }

        return stats
