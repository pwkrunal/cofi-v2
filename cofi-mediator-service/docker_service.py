"""Docker SDK wrapper for container management."""
import docker
from docker.errors import NotFound, APIError
import structlog
from typing import Dict, Any, Optional

logger = structlog.get_logger()


class DockerService:
    """Service for managing Docker containers using docker.from_env()."""
    
    def __init__(self):
        self.client = docker.from_env()
    
    def start_container(self, container_name: str) -> Dict[str, Any]:
        """
        Start a Docker container by name.
        
        Args:
            container_name: Name of the container to start
            
        Returns:
            Dict with status and message
        """
        try:
            container = self.client.containers.get(container_name)
            
            if container.status == "running":
                logger.info("container_already_running", container=container_name)
                return {
                    "status": "already_running",
                    "container_name": container_name,
                    "message": f"Container {container_name} is already running"
                }
            
            container.start()
            logger.info("container_started", container=container_name)
            
            return {
                "status": "started",
                "container_name": container_name,
                "message": f"Container {container_name} started successfully"
            }
            
        except NotFound:
            logger.error("container_not_found", container=container_name)
            return {
                "status": "error",
                "container_name": container_name,
                "message": f"Container {container_name} not found"
            }
        except APIError as e:
            logger.error("docker_api_error", container=container_name, error=str(e))
            return {
                "status": "error",
                "container_name": container_name,
                "message": str(e)
            }
    
    def stop_container(self, container_name: str, timeout: int = 10) -> Dict[str, Any]:
        """
        Stop a Docker container by name.
        
        Args:
            container_name: Name of the container to stop
            timeout: Seconds to wait before killing
            
        Returns:
            Dict with status and message
        """
        try:
            container = self.client.containers.get(container_name)
            
            if container.status != "running":
                logger.info("container_not_running", container=container_name)
                return {
                    "status": "not_running",
                    "container_name": container_name,
                    "message": f"Container {container_name} is not running"
                }
            
            container.stop(timeout=timeout)
            logger.info("container_stopped", container=container_name)
            
            return {
                "status": "stopped",
                "container_name": container_name,
                "message": f"Container {container_name} stopped successfully"
            }
            
        except NotFound:
            logger.error("container_not_found", container=container_name)
            return {
                "status": "error",
                "container_name": container_name,
                "message": f"Container {container_name} not found"
            }
        except APIError as e:
            logger.error("docker_api_error", container=container_name, error=str(e))
            return {
                "status": "error",
                "container_name": container_name,
                "message": str(e)
            }
    
    def get_container_status(self, container_name: str) -> Dict[str, Any]:
        """
        Get the status of a Docker container.
        
        Args:
            container_name: Name of the container
            
        Returns:
            Dict with is_running flag and status
        """
        try:
            container = self.client.containers.get(container_name)
            is_running = container.status == "running"
            
            return {
                "is_running": is_running,
                "container_name": container_name,
                "status": container.status
            }
            
        except NotFound:
            return {
                "is_running": False,
                "container_name": container_name,
                "status": "not_found"
            }
        except APIError as e:
            return {
                "is_running": False,
                "container_name": container_name,
                "status": "error",
                "message": str(e)
            }
    
    def list_containers(self, all: bool = True) -> list:
        """List all containers."""
        containers = self.client.containers.list(all=all)
        return [
            {
                "name": c.name,
                "status": c.status,
                "image": c.image.tags[0] if c.image.tags else "unknown"
            }
            for c in containers
        ]


# Singleton instance
_docker_service: Optional[DockerService] = None


def get_docker_service() -> DockerService:
    """Get or create Docker service instance."""
    global _docker_service
    if _docker_service is None:
        _docker_service = DockerService()
    return _docker_service
