"""Configuration management using Pydantic settings."""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # GPU Mediators
    gpu_machines: str = Field(default="localhost", description="Comma-separated GPU IPs")
    mediator_port: int = Field(default=5065, description="Mediator service port")
    
    # Service Ports
    ivr_port: int = Field(default=4080, description="IVR service port")
    lid_port: int = Field(default=4070, description="LID service port")
    stt_port: int = Field(default=4030, description="STT service port")
    llm1_port: int = Field(default=7063, description="LLM1 service port")
    llm2_port: int = Field(default=7062, description="LLM2 service port")
    
    # Batch Config
    client_volume: str = Field(default="/client_volume", description="Client files directory")
    batch_date: str = Field(default="", description="Batch date in DD-MM-YYYY format")
    current_batch: int = Field(default=1, description="Current batch number")
    
    # Call Record Config
    process_id: int = Field(default=1, description="Process ID for call records")
    category_mapping_id: int = Field(default=1, description="Category mapping ID for call records")
    audio_endpoint: str = Field(default="", description="Base URL for audio files")
    
    # Optional Stages
    callmetadata_enabled: bool = Field(default=True, description="Enable callMetadata CSV upload stage")
    trademetadata_enabled: bool = Field(default=True, description="Enable tradeMetadata CSV upload stage")
    rule_engine_enabled: bool = Field(default=True, description="Enable Rule Engine Step 1 (trade-audio mapping)")
    llm1_enabled: bool = Field(default=True, description="Enable LLM1 extraction stage")
    llm2_enabled: bool = Field(default=True, description="Enable LLM2 extraction stage")
    denoise_enabled: bool = Field(default=True, description="Enable denoise processing stage")
    ivr_enabled: bool = Field(default=True, description="Enable IVR processing stage")
    
    # STT Config
    diarization: int = Field(default=0, description="Enable diarization (0=off, 1=on)")

    # Event Logging Config (for large batches)
    log_file_start_events: bool = Field(default=False, description="Log file_start events (set False for batches > 5000 files to reduce DB load by 50%)")
    progress_update_interval: int = Field(default=100, description="Log progress every N files (10=frequent, 100=balanced, 250=minimal)")

    # Wait Times (seconds)
    ivr_wait: int = Field(default=60, description="Wait after IVR container start")
    lid_wait: int = Field(default=60, description="Wait after LID container start")
    stt_wait: int = Field(default=180, description="Wait after STT container start")
    llm_wait: int = Field(default=300, description="Wait after LLM container start")
    
    # Container Names
    ivr_container: str = Field(default="auditnex-ivr-1")
    lid_container: str = Field(default="auditnex-lid-1")
    stt_container: str = Field(default="auditnex-stt-inference-1")
    llm1_container: str = Field(default="auditnex-llm-extraction-1")
    llm2_container: str = Field(default="auditnex-llm-extraction-2")
    
    # API Endpoints
    ivr_api_endpoint: str = Field(default="/file_ivr_clean")
    lid_api_endpoint: str = Field(default="/file_stt_features")
    stt_api_endpoint: str = Field(default="/file_stt_transcript")
    llm_api_endpoint: str = Field(default="/extract_information")
    
    # NLP API Base URLs (external)
    nlp_api_q1: str = Field(default="http://localhost:7063", description="NLP API base URL for LLM1")
    nlp_api_q2: str = Field(default="http://localhost:7062", description="NLP API base URL for LLM2")
    
    # MySQL
    mysql_host: str = Field(default="localhost")
    mysql_port: int = Field(default=3306)
    mysql_user: str = Field(default="root")
    mysql_password: str = Field(default="password")
    mysql_database: str = Field(default="testDb")

    # External Audit Server Webhook
    audit_server_url: str = Field(default="http://localhost:8000", description="External audit server URL for webhooks")

    # LLM2 Skip Questions
    llm2_skip_questions: str = Field(default="", description="Comma-separated list of question names to skip in LLM2")
    llm2_na_questions: str = Field(default="", description="Comma-separated list of question names to mark as NA in LLM2")
    
    @property
    def llm2_skip_question_list(self) -> List[str]:
        """Parse comma-separated skip questions into a list."""
        return [q.strip() for q in self.llm2_skip_questions.split(",") if q.strip()]
    
    @property
    def llm2_na_question_list(self) -> List[str]:
        """Parse comma-separated NA questions into a list."""
        return [q.strip() for q in self.llm2_na_questions.split(",") if q.strip()]
    
    @property
    def gpu_machine_list(self) -> List[str]:
        """Parse comma-separated GPU machines into a list."""
        return [ip.strip() for ip in self.gpu_machines.split(",") if ip.strip()]
    
    @property
    def database_url(self) -> str:
        """Generate async MySQL connection URL."""
        return f"mysql+aiomysql://{self.mysql_user}:{self.mysql_password}@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
