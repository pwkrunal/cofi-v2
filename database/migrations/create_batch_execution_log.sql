-- Migration: Create batchExecutionLog table for dashboard monitoring
-- Date: 2026-01-13
-- Description: Table to store detailed execution logs for batch processing pipeline

CREATE TABLE IF NOT EXISTS batchExecutionLog (
    id INT AUTO_INCREMENT PRIMARY KEY,
    batchId INT NOT NULL,
    timestamp DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    stage VARCHAR(50) NOT NULL COMMENT 'file_distribution, denoise, ivr, lid, stt, llm1, llm2, triaging, callmetadata, trademetadata',
    eventType ENUM('stage_start', 'stage_progress', 'stage_complete', 'file_start', 'file_complete', 'error', 'info') NOT NULL,
    fileName VARCHAR(255) DEFAULT NULL COMMENT 'NULL for batch-level events',
    gpuIp VARCHAR(50) DEFAULT NULL,
    payload TEXT DEFAULT NULL COMMENT 'JSON string of request payload',
    response TEXT DEFAULT NULL COMMENT 'JSON string of response data',
    status ENUM('pending', 'processing', 'success', 'failed') DEFAULT 'processing',
    errorMessage TEXT DEFAULT NULL,
    totalFiles INT DEFAULT NULL COMMENT 'For stage_start events',
    processedFiles INT DEFAULT NULL COMMENT 'For stage_progress events',
    metadata JSON DEFAULT NULL COMMENT 'Additional data (durations, counts, etc.)',

    INDEX idx_batch_id (batchId),
    INDEX idx_stage (stage),
    INDEX idx_timestamp (timestamp),
    INDEX idx_event_type (eventType),

    FOREIGN KEY (batchId) REFERENCES batchStatus(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Detailed execution logs for batch processing pipeline monitoring';
