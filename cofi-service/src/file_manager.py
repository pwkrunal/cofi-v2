"""File management for reading batch files and distributing to GPUs."""
import os
from pathlib import Path
from typing import List, Dict, Tuple
import pandas as pd
import structlog
from dataclasses import dataclass

from .config import get_settings

logger = structlog.get_logger()


@dataclass
class BatchFiles:
    """Container for batch files."""
    call_metadata: pd.DataFrame
    trade_metadata: pd.DataFrame
    audio_files: List[str]


class FileManager:
    """Manages file reading and distribution."""
    
    def __init__(self):
        self.settings = get_settings()
    
    def get_batch_directory(self) -> Path:
        """Get the batch directory path."""
        return Path(self.settings.client_volume) / self.settings.batch_date
    
    def read_batch_files(self) -> BatchFiles:
        """
        Read files from the batch directory.
        
        Returns:
            BatchFiles containing metadata DataFrames and audio file list
        """
        batch_dir = self.get_batch_directory()
        
        if not batch_dir.exists():
            raise FileNotFoundError(f"Batch directory not found: {batch_dir}")
        
        # Read metadata CSVs
        call_metadata_path = batch_dir / "callMetadata.csv"
        trade_metadata_path = batch_dir / "tradeMetadata.csv"
        
        call_metadata = pd.DataFrame()
        trade_metadata = pd.DataFrame()
        
        if call_metadata_path.exists():
            call_metadata = pd.read_csv(call_metadata_path)
            logger.info("call_metadata_loaded", rows=len(call_metadata))
        else:
            logger.warning("call_metadata_not_found", path=str(call_metadata_path))
        
        if trade_metadata_path.exists():
            trade_metadata = pd.read_csv(trade_metadata_path)
            logger.info("trade_metadata_loaded", rows=len(trade_metadata))
        else:
            logger.warning("trade_metadata_not_found", path=str(trade_metadata_path))
        
        # Get audio files (all files except CSVs)
        audio_extensions = {".wav", ".mp3", ".ogg", ".flac", ".m4a"}
        audio_files = []
        
        for file_path in batch_dir.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in audio_extensions:
                audio_files.append(str(file_path))
        
        logger.info("audio_files_found", count=len(audio_files))
        
        return BatchFiles(
            call_metadata=call_metadata,
            trade_metadata=trade_metadata,
            audio_files=audio_files
        )
    
    def distribute_files_to_gpus(self, audio_files: List[str]) -> Dict[str, List[str]]:
        """
        Distribute audio files across GPU machines using round-robin.
        
        Args:
            audio_files: List of audio file paths
        
        Returns:
            Dict mapping GPU IP to list of file paths assigned to it
        """
        gpu_ips = self.settings.gpu_machine_list
        distribution: Dict[str, List[str]] = {ip: [] for ip in gpu_ips}
        
        for i, file_path in enumerate(audio_files):
            gpu_ip = gpu_ips[i % len(gpu_ips)]
            distribution[gpu_ip].append(file_path)
        
        for gpu_ip, files in distribution.items():
            logger.info("files_distributed", gpu=gpu_ip, count=len(files))
        
        return distribution
    
    def get_file_name(self, file_path: str) -> str:
        """Extract file name from path."""
        return os.path.basename(file_path)
