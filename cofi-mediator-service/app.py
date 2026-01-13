"""FastAPI application for cofi-mediator-service."""
import os
import shutil
from pathlib import Path
from fastapi import FastAPI, File, UploadFile, HTTPException
from pydantic import BaseModel
import structlog
from dotenv import load_dotenv

from docker_service import get_docker_service

# Load environment
load_dotenv()

# Configure logging
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.dev.ConsoleRenderer()
    ]
)
logger = structlog.get_logger()

# Configuration
STORAGE_PATH = os.getenv("STORAGE_PATH", "/audio_files")
PORT = int(os.getenv("PORT", "8000"))
HOST = os.getenv("HOST", "0.0.0.0")

# Ensure storage directory exists
Path(STORAGE_PATH).mkdir(parents=True, exist_ok=True)

# FastAPI app
app = FastAPI(
    title="Cofi Mediator Service",
    description="GPU-side service for Docker container management and file uploads",
    version="1.0.0"
)

# Request models
class ContainerRequest(BaseModel):
    container_name: str


class ContainerStatusRequest(BaseModel):
    container_name: str


# Endpoints

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "cofi-mediator"}


@app.post("/upload_file")
async def upload_file(file: UploadFile = File(...)):
    """
    Upload an audio file to the GPU storage directory.
    
    Args:
        file: The file to upload
        
    Returns:
        Status and file path
    """
    try:
        file_path = Path(STORAGE_PATH) / file.filename
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        logger.info("file_uploaded", filename=file.filename, path=str(file_path))
        
        return {
            "status": True,
            "message": "File uploaded successfully",
            "file_name": file.filename,
            "file_path": str(file_path)
        }
    except Exception as e:
        logger.error("upload_failed", filename=file.filename, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/start_container")
async def start_container(request: ContainerRequest):
    """
    Start a Docker container by name.
    
    Args:
        request: ContainerRequest with container_name
        
    Returns:
        Container start status
    """
    docker_service = get_docker_service()
    result = docker_service.start_container(request.container_name)
    
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])
    
    return result


@app.post("/stop_container")
async def stop_container(request: ContainerRequest):
    """
    Stop a Docker container by name.
    
    Args:
        request: ContainerRequest with container_name
        
    Returns:
        Container stop status
    """
    docker_service = get_docker_service()
    result = docker_service.stop_container(request.container_name)
    
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])
    
    return result


@app.post("/container_status")
async def container_status(request: ContainerStatusRequest):
    """
    Check if a Docker container is running.
    
    Args:
        request: ContainerStatusRequest with container_name
        
    Returns:
        Container running status
    """
    docker_service = get_docker_service()
    return docker_service.get_container_status(request.container_name)


@app.get("/containers")
async def list_containers():
    """
    List all Docker containers.
    
    Returns:
        List of containers with their status
    """
    docker_service = get_docker_service()
    return {"containers": docker_service.list_containers()}


if __name__ == "__main__":
    import uvicorn
    logger.info("starting_mediator_service", host=HOST, port=PORT)
    uvicorn.run(app, host=HOST, port=PORT)
