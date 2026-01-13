"""IVR (Interactive Voice Response) processing stage."""
from typing import Dict, Any

from .base import PipelineStage
from ..config import get_settings


class IVRStage(PipelineStage):
    """IVR detection and cleaning stage."""
    
    stage_name = "IVR"
    status_column = "ivrDone"
    
    def __init__(self):
        super().__init__()
        settings = get_settings()
        self.container_name = settings.ivr_container
        self.wait_seconds = settings.ivr_wait
        self.api_endpoint = settings.ivr_api_endpoint
    
    def build_payload(self, file_name: str) -> Dict[str, Any]:
        """Build IVR API payload."""
        return {"file_name": file_name}
    
    def process_response(self, file_name: str, response: Dict[str, Any], gpu_ip: str, batch_id: int):
        """
        Process IVR API response.
        Response contains: ivr_detected, ivr_end_sec, original_duration_sec, trimmed_duration_sec, output_path
        Currently we just log the response - no additional DB updates needed.
        """
        # IVR response is not stored in DB per flow, just mark as done
        pass
