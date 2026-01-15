-- Migration: Add denoiseDone column to fileDistribution table
-- Date: 2026-01-15
-- Purpose: Enable recovery capability for denoise stage

-- Add denoiseDone column
ALTER TABLE fileDistribution 
ADD COLUMN denoiseDone TINYINT(1) DEFAULT 0 AFTER file;

-- Add index for performance (optional but recommended for 10K+ files)
CREATE INDEX idx_filedist_batch_denoise ON fileDistribution(batchId, denoiseDone);
