"""Denoise processing stage."""
from typing import Dict, Any, List, Optional
import structlog

from .base import PipelineStage
from ..config import get_settings

logger = structlog.get_logger()


class DenoiseStage(PipelineStage):
    """Audio denoising stage."""

    stage_name = "Denoise"
    status_column = "denoiseDone"
    processing_log_stage = "denoise"  # For processing_logs table
    
    def __init__(self):
        super().__init__()
        settings = get_settings()
        self.container_name = None  # Denoise doesn't use GPU containers
        self.wait_seconds = 0  # No wait needed
        self.api_port = settings.denoise_port
        self.api_endpoint = "/process"
    
    def build_payload(self, file_name: str) -> Dict[str, Any]:
        """
        Build denoise API payload.
        
        Args:
            file_name: Name of the audio file
        
        Returns:
            Payload dict with file_name
        """
        return {
            "file_name": file_name
        }
    
    def process_response(self, file_name: str, response: Dict[str, Any], gpu_ip: str, batch_id: int):
        """
        Process denoise API response.
        
        Response format:
        {
            "status": "success",
            "message": "Audio denoised successfully",
            "output_path": "/path/to/denoised_audio.wav",
            "original_duration_sec": 120.0,
            "processed_duration_sec": 120.0
        }
        """
        try:
            status = response.get('status')
            
            if status == 'success':
                logger.info("denoise_success", 
                           file=file_name,
                           output_path=response.get('output_path'))
            else:
                logger.warning("denoise_failed", 
                              file=file_name,
                              message=response.get('message'))
        
        except Exception as e:
            logger.error("denoise_response_processing_failed", 
                        file=file_name, 
                        error=str(e))
