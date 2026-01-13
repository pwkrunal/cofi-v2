"""FastAPI server for audit operations."""
import asyncio
import uuid
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, HTTPException
from pydantic import BaseModel
import structlog
import shutil
from pathlib import Path

from .config import get_settings
from .database import get_database, BatchStatusRepo, FileDistributionRepo, CallRepo
from .file_manager import FileManager
from .mediator_client import MediatorClient
from .audit_pipeline import AuditPipeline
from .reaudit_pipeline import ReauditPipeline

# Configure logging
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.dev.ConsoleRenderer()
    ]
)
logger = structlog.get_logger()

app = FastAPI(title="Cofi Audit Service", version="1.0.0")

# In-memory task tracking (could be moved to Redis/DB for production)
audit_tasks = {}
reaudit_in_progress = False
audit_upload_in_progress = False


class AuditStatusResponse(BaseModel):
    task_id: str
    status: str
    total_files: int
    progress: dict


class AuditUploadResponse(BaseModel):
    status: str
    task_id: str
    files_uploaded: int
    files: List[str]


class ReauditRequest(BaseModel):
    audio_names: List[str]
    stages: List[str] = ["lid", "stt", "llm1", "llm2"]  # Default all stages


class ReauditResponse(BaseModel):
    status: str
    task_id: str
    files_queued: int


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/audit/upload", response_model=AuditUploadResponse)
async def upload_for_audit(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    process_id: int = Form(...),
    category_mapping_id: int = Form(1),  # Optional, default 1
):
    """
    Upload audio files for audit processing.
    
    Files go through: LID → STT → LLM1 (if enabled) → LLM2 (if enabled)
    
    Returns immediately, processing happens in background.
    """
    global audit_upload_in_progress
    
    # Check if another audit upload is already being processed
    if audit_upload_in_progress:
        raise HTTPException(
            status_code=409,
            detail="Another audit upload is already being processed. Please wait for it to complete."
        )
    
    settings = get_settings()
    
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")
    
    # Generate task ID
    task_id = str(uuid.uuid4())
    
    # Save files to local storage
    upload_dir = Path(settings.client_volume) / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    saved_files = []
    for upload_file in files:
        file_path = upload_dir / upload_file.filename
        
        try:
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(upload_file.file, buffer)
            saved_files.append(upload_file.filename)
            logger.info("file_saved", file=upload_file.filename)
        except Exception as e:
            logger.error("file_save_failed", file=upload_file.filename, error=str(e))
            raise HTTPException(status_code=500, detail=f"Failed to save {upload_file.filename}")
    
    # Initialize task tracking
    audit_tasks[task_id] = {
        "status": "queued",
        "total_files": len(saved_files),
        "progress": {
            "lid": {"total": len(saved_files), "done": 0},
            "stt": {"total": len(saved_files), "done": 0},
            "llm1": {"total": len(saved_files), "done": 0},
            "llm2": {"total": len(saved_files), "done": 0}
        }
    }
    
    # Set flag to indicate audit upload in progress
    audit_upload_in_progress = True
    
    # Start background processing
    background_tasks.add_task(
        run_audit_pipeline,
        task_id=task_id,
        file_names=saved_files,
        upload_dir=str(upload_dir),
        process_id=process_id,
        category_mapping_id=category_mapping_id
    )
    
    return AuditUploadResponse(
        status="queued",
        task_id=task_id,
        files_uploaded=len(saved_files),
        files=saved_files
    )


@app.get("/audit/status/{task_id}", response_model=AuditStatusResponse)
async def get_audit_status(task_id: str):
    """Get status of an audit task."""
    if task_id not in audit_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = audit_tasks[task_id]
    return AuditStatusResponse(
        task_id=task_id,
        status=task["status"],
        total_files=task["total_files"],
        progress=task["progress"]
    )


@app.post("/reaudit", response_model=ReauditResponse)
async def reaudit_files(
    request: ReauditRequest,
    background_tasks: BackgroundTasks
):
    """
    Reaudit existing audio files.
    
    Reprocesses files through specified stages: lid → stt → llm1 → llm2
    
    - If 'stt' in stages: deletes existing transcripts
    - If 'llm2' in stages: deletes existing auditAnswer records
    
    Returns immediately, processing happens in background.
    """
    global reaudit_in_progress
    
    # Check if another reaudit is already running
    if reaudit_in_progress:
        raise HTTPException(
            status_code=409,
            detail="Another reaudit is already in progress. Please wait for it to complete."
        )
    
    if not request.audio_names:
        raise HTTPException(status_code=400, detail="No audio names provided")
    
    # Validate stages
    valid_stages = {"lid", "stt", "llm1", "llm2"}
    for stage in request.stages:
        if stage not in valid_stages:
            raise HTTPException(status_code=400, detail=f"Invalid stage: {stage}")
    
    # Generate task ID
    task_id = str(uuid.uuid4())
    
    # Initialize task tracking
    audit_tasks[task_id] = {
        "status": "queued",
        "total_files": len(request.audio_names),
        "progress": {stage: {"total": len(request.audio_names), "done": 0} for stage in request.stages}
    }
    
    # Set flag to indicate reaudit in progress
    reaudit_in_progress = True
    
    # Start background processing
    background_tasks.add_task(
        run_reaudit_pipeline,
        task_id=task_id,
        audio_names=request.audio_names,
        stages=request.stages
    )
    
    return ReauditResponse(
        status="processing",
        task_id=task_id,
        files_queued=len(request.audio_names)
    )


async def run_audit_pipeline(
    task_id: str,
    file_names: List[str],
    upload_dir: str,
    process_id: int,
    category_mapping_id: int
):
    """Background task to run audit pipeline."""
    global audit_upload_in_progress
    
    try:
        audit_tasks[task_id]["status"] = "processing"
        
        pipeline = AuditPipeline(
            task_id=task_id,
            task_tracker=audit_tasks[task_id],
            process_id=process_id,
            category_mapping_id=category_mapping_id
        )
        
        await pipeline.process(file_names, upload_dir)
        
        audit_tasks[task_id]["status"] = "completed"
        logger.info("audit_task_completed", task_id=task_id)
        
    except Exception as e:
        audit_tasks[task_id]["status"] = "failed"
        logger.error("audit_task_failed", task_id=task_id, error=str(e))
    finally:
        # Always release the lock when done
        audit_upload_in_progress = False
        logger.info("audit_upload_lock_released")


async def run_reaudit_pipeline(
    task_id: str,
    audio_names: List[str],
    stages: List[str]
):
    """Background task to run reaudit pipeline."""
    global reaudit_in_progress
    
    try:
        audit_tasks[task_id]["status"] = "processing"
        
        pipeline = ReauditPipeline(
            task_id=task_id,
            task_tracker=audit_tasks[task_id]
        )
        
        await pipeline.process(audio_names, stages)
        
        audit_tasks[task_id]["status"] = "completed"
        logger.info("reaudit_task_completed", task_id=task_id)
        
    except Exception as e:
        audit_tasks[task_id]["status"] = "failed"
        logger.error("reaudit_task_failed", task_id=task_id, error=str(e))
    finally:
        # Always release the lock when done
        reaudit_in_progress = False
        logger.info("reaudit_lock_released")


def start_server():
    """Start the FastAPI server."""
    import uvicorn
    settings = get_settings()
    uvicorn.run(app, host="0.0.0.0", port=5064)


if __name__ == "__main__":
    start_server()

