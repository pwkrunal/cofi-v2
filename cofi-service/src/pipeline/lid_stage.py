"""LID (Language Identification) processing stage."""
from typing import Dict, Any, List
import structlog

from .base import PipelineStage
from ..config import get_settings
from ..database import LidStatusRepo, get_database

logger = structlog.get_logger()


class LIDStage(PipelineStage):
    """Language identification stage."""
    
    stage_name = "LID"
    status_column = "lidDone"
    
    def __init__(self):
        super().__init__()
        settings = get_settings()
        self.container_name = settings.lid_container
        self.wait_seconds = 60  # LID is relatively fast
        self.api_endpoint = settings.lid_api_endpoint
        self.lid_repo = LidStatusRepo(self.db)
    
    def build_payload(self, file_name: str) -> Dict[str, Any]:
        """Build LID API payload."""
        return {
            "file_name": file_name,
            "entity": "LID",
            "response": ""
        }
    
    def process_response(self, file_name: str, response: Dict[str, Any], gpu_ip: str, batch_id: int):
        """
        Process LID API response and store in lidStatus table.
        Response structure:
        {
            "data": {
                "derived_value": [
                    {"results": ["hi"], "audio_duration": 120.5}
                ]
            }
        }
        """
        try:
            data = response.get("data", {})
            derived = data.get("derived_value", [{}])[0]
            
            language = derived.get("results", ["unknown"])[0]
            audio_duration = derived.get("audio_duration", 0.0)
            
            # Truncate 3-char language codes to 2 chars (e.g., "hin" -> "hi", "eng" -> "en")
            if isinstance(language, str) and len(language) == 3:
                language = language[:2]
            
            # Insert LID status record
            self.lid_repo.insert(
                audio_name=file_name,
                language=language,
                audio_duration=audio_duration,
                batch_id=batch_id,
                ip=gpu_ip
            )
            logger.info("lid_result_saved", file=file_name, language=language, duration=audio_duration)
        except Exception as e:
            logger.error("lid_response_processing_failed", file=file_name, error=str(e))

