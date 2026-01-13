"""HTTP client for communicating with cofi-mediator-service on GPU machines."""
import aiohttp
import asyncio
from typing import List, Dict, Any, Optional
import structlog

from .config import get_settings

logger = structlog.get_logger()


class MediatorClient:
    """Client for interacting with cofi-mediator-service on GPU machines."""
    
    def __init__(self, timeout: int = 600):
        self.settings = get_settings()
        self.timeout = aiohttp.ClientTimeout(total=timeout)
    
    def _get_mediator_url(self, gpu_ip: str) -> str:
        """Build mediator base URL."""
        return f"http://{gpu_ip}:{self.settings.mediator_port}"
    
    async def start_container(self, gpu_ip: str, container_name: str) -> Dict[str, Any]:
        """Start a Docker container on a GPU machine."""
        url = f"{self._get_mediator_url(gpu_ip)}/start_container"
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            try:
                async with session.post(url, json={"container_name": container_name}) as resp:
                    result = await resp.json()
                    logger.info("container_started", gpu=gpu_ip, container=container_name, result=result)
                    return result
            except Exception as e:
                logger.error("start_container_failed", gpu=gpu_ip, container=container_name, error=str(e))
                raise
    
    async def stop_container(self, gpu_ip: str, container_name: str) -> Dict[str, Any]:
        """Stop a Docker container on a GPU machine."""
        url = f"{self._get_mediator_url(gpu_ip)}/stop_container"
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            try:
                async with session.post(url, json={"container_name": container_name}) as resp:
                    result = await resp.json()
                    logger.info("container_stopped", gpu=gpu_ip, container=container_name, result=result)
                    return result
            except Exception as e:
                logger.error("stop_container_failed", gpu=gpu_ip, container=container_name, error=str(e))
                raise
    
    async def check_container_status(self, gpu_ip: str, container_name: str) -> bool:
        """Check if a container is running on a GPU machine."""
        url = f"{self._get_mediator_url(gpu_ip)}/container_status"
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            try:
                async with session.post(url, json={"container_name": container_name}) as resp:
                    result = await resp.json()
                    return result.get("is_running", False)
            except Exception as e:
                logger.error("check_status_failed", gpu=gpu_ip, container=container_name, error=str(e))
                return False
    
    async def upload_file(self, gpu_ip: str, file_path: str, file_name: str) -> Dict[str, Any]:
        """Upload a file to a GPU machine."""
        url = f"{self._get_mediator_url(gpu_ip)}/upload_file"
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            try:
                with open(file_path, 'rb') as f:
                    data = aiohttp.FormData()
                    data.add_field('file', f, filename=file_name)
                    async with session.post(url, data=data) as resp:
                        result = await resp.json()
                        logger.info("file_uploaded", gpu=gpu_ip, file=file_name, result=result)
                        return result
            except Exception as e:
                logger.error("upload_failed", gpu=gpu_ip, file=file_name, error=str(e))
                raise
    
    async def call_processing_api(self, gpu_ip: str, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Call a processing API (IVR, LID, STT, LLM) on a GPU machine."""
        url = f"{self._get_mediator_url(gpu_ip)}{endpoint}"
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            try:
                async with session.post(url, json=payload) as resp:
                    result = await resp.json()
                    logger.info("api_called", gpu=gpu_ip, endpoint=endpoint, status=resp.status)
                    return result
            except Exception as e:
                logger.error("api_call_failed", gpu=gpu_ip, endpoint=endpoint, error=str(e))
                raise
    
    # Parallel operations across all GPUs
    
    async def start_all_containers(self, container_name: str) -> List[Dict[str, Any]]:
        """Start a container on all GPU machines in parallel."""
        gpu_ips = self.settings.gpu_machine_list
        tasks = [self.start_container(ip, container_name) for ip in gpu_ips]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return list(zip(gpu_ips, results))
    
    async def stop_all_containers(self, container_name: str) -> List[Dict[str, Any]]:
        """Stop a container on all GPU machines in parallel."""
        gpu_ips = self.settings.gpu_machine_list
        tasks = [self.stop_container(ip, container_name) for ip in gpu_ips]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return list(zip(gpu_ips, results))
    
    async def process_files_parallel(
        self, 
        file_gpu_mapping: Dict[str, List[str]], 
        endpoint: str,
        payload_builder: callable
    ) -> Dict[str, Any]:
        """
        Process files in parallel across all GPUs.
        
        Args:
            file_gpu_mapping: Dict mapping GPU IP to list of files on that GPU
            endpoint: API endpoint to call
            payload_builder: Function to build payload from file name
        
        Returns:
            Dict with results per file
        """
        all_tasks = []
        task_info = []
        
        for gpu_ip, files in file_gpu_mapping.items():
            for file_name in files:
                payload = payload_builder(file_name)
                task = self.call_processing_api(gpu_ip, endpoint, payload)
                all_tasks.append(task)
                task_info.append((gpu_ip, file_name))
        
        results = await asyncio.gather(*all_tasks, return_exceptions=True)
        
        return {
            info[1]: {"gpu": info[0], "result": result}
            for info, result in zip(task_info, results)
        }
