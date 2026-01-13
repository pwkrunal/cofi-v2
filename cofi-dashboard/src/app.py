"""FastAPI server for Cofi Dashboard with SSE support."""
import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

from .config import get_settings
from .database import get_database, BatchStatusRepo, BatchExecutionLogRepo

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.dev.ConsoleRenderer()
    ]
)
logger = structlog.get_logger()

# Initialize FastAPI app
app = FastAPI(
    title="Cofi Dashboard",
    description="Real-time monitoring dashboard for cofi-service batch processing pipeline",
    version="1.0.0"
)

# Initialize database and settings
settings = get_settings()
db = get_database()
batch_repo = BatchStatusRepo(db)
log_repo = BatchExecutionLogRepo(db)

# Get static directory path
STATIC_DIR = Path(__file__).parent / "static"


@app.on_event("startup")
async def startup_event():
    """Application startup event."""
    logger.info("dashboard_starting")


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event."""
    logger.info("dashboard_shutting_down")


@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    """Serve the main dashboard HTML page."""
    html_file = STATIC_DIR / "index.html"
    if html_file.exists():
        return FileResponse(html_file)
    else:
        return HTMLResponse(content="<h1>Dashboard not found</h1><p>Please ensure static/index.html exists.</p>", status_code=404)


@app.get("/static/style.css")
async def serve_css():
    """Serve the CSS file."""
    css_file = STATIC_DIR / "style.css"
    if css_file.exists():
        return FileResponse(css_file, media_type="text/css")
    return HTMLResponse(content="/* CSS not found */", status_code=404)


@app.get("/static/app.js")
async def serve_js():
    """Serve the JavaScript file."""
    js_file = STATIC_DIR / "app.js"
    if js_file.exists():
        return FileResponse(js_file, media_type="application/javascript")
    return HTMLResponse(content="// JS not found", status_code=404)


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "cofi-dashboard"}


@app.get("/api/current-batch")
async def get_current_batch(batch_id: Optional[int] = None):
    """
    Get the current or most recent batch information.

    Args:
        batch_id: Optional specific batch ID to monitor. If not provided,
                  returns the currently processing batch or most recent batch.

    Returns:
        Batch status information with stage statuses
    """
    try:
        # If specific batch_id provided, get that batch
        if batch_id is not None:
            batch = batch_repo.get_by_id(batch_id)
        else:
            # Otherwise, get the current/most recent batch
            batch = batch_repo.get_current_batch()

        if not batch:
            return {
                "error": "No batches found",
                "batch_id": None
            }

        # Get stage statistics
        stats = log_repo.get_stage_stats(batch['id'])

        return {
            "batch_id": batch['id'],
            "batch_date": batch.get('batchDate'),
            "current_batch": batch.get('currentBatch', 0) == 1,
            "status": batch.get('batchStatus', 'Pending'),
            "batch_start_time": batch.get('batchStartTime'),
            "batch_end_time": batch.get('batchEndTime'),
            "stages": {
                "file_distribution": {
                    "status": batch.get('dbInsertionStatus', 'Pending'),
                    "start_time": batch.get('dbInsertionStartTime'),
                    "end_time": batch.get('dbInsertionEndTime'),
                    **stats.get('file_distribution', {'total': 0, 'processed': 0, 'errors': 0})
                },
                "callmetadata": {
                    "status": "Complete" if batch.get('callmetadataStatus', 0) == 1 else "Pending",
                    **stats.get('callmetadata', {'total': 0, 'processed': 0, 'errors': 0})
                },
                "trademetadata": {
                    "status": "Complete" if batch.get('trademetadataStatus', 0) == 1 else "Pending",
                    **stats.get('trademetadata', {'total': 0, 'processed': 0, 'errors': 0})
                },
                "denoise": {
                    "status": batch.get('denoiseStatus', 'Pending'),
                    "start_time": batch.get('denoiseStartTime'),
                    "end_time": batch.get('denoiseEndTime'),
                    **stats.get('denoise', {'total': 0, 'processed': 0, 'errors': 0})
                },
                "ivr": {
                    "status": batch.get('ivrStatus', 'Pending'),
                    "start_time": batch.get('ivrStartTime'),
                    "end_time": batch.get('ivrEndTime'),
                    **stats.get('ivr', {'total': 0, 'processed': 0, 'errors': 0})
                },
                "lid": {
                    "status": batch.get('lidStatus', 'Pending'),
                    "start_time": batch.get('lidStartTime'),
                    "end_time": batch.get('lidEndTime'),
                    **stats.get('lid', {'total': 0, 'processed': 0, 'errors': 0})
                },
                "triaging": {
                    "status": batch.get('triagingStatus', 'Pending'),
                    "start_time": batch.get('triaggingStartTime'),
                    "end_time": batch.get('triaggingEndTime'),
                    **stats.get('triaging', {'total': 0, 'processed': 0, 'errors': 0})
                },
                "stt": {
                    "status": batch.get('sttStatus', 'Pending'),
                    "start_time": batch.get('sttStartTime'),
                    "end_time": batch.get('sttEndTime'),
                    **stats.get('stt', {'total': 0, 'processed': 0, 'errors': 0})
                },
                "llm1": {
                    "status": batch.get('llm1Status', 'Pending'),
                    "start_time": batch.get('llm1StartTime'),
                    "end_time": batch.get('llm1EndTime'),
                    **stats.get('llm1', {'total': 0, 'processed': 0, 'errors': 0})
                },
                "llm2": {
                    "status": batch.get('llm2Status', 'Pending'),
                    "start_time": batch.get('llm2StartTime'),
                    "end_time": batch.get('llm2EndTime'),
                    **stats.get('llm2', {'total': 0, 'processed': 0, 'errors': 0})
                }
            }
        }
    except Exception as e:
        logger.error("get_current_batch_failed", error=str(e))
        return {
            "error": str(e),
            "batch_id": None
        }


@app.get("/api/batch/{batch_id}/logs")
async def get_batch_logs(batch_id: int, since_id: int = 0):
    """
    Get execution logs for a batch.

    Args:
        batch_id: Batch ID
        since_id: Get events with ID greater than this (for pagination)

    Returns:
        List of log events
    """
    try:
        if since_id > 0:
            events = log_repo.get_latest_events(batch_id, since_id=since_id, limit=100)
        else:
            events = log_repo.get_by_batch(batch_id, limit=500)

        # Convert datetime objects to ISO format strings
        for event in events:
            if 'timestamp' in event and event['timestamp']:
                event['timestamp'] = event['timestamp'].isoformat()

        return events
    except Exception as e:
        logger.error("get_batch_logs_failed", batch_id=batch_id, error=str(e))
        return {"error": str(e)}


@app.get("/api/batch/{batch_id}/stats")
async def get_batch_stats(batch_id: int):
    """
    Get aggregated statistics for a batch.

    Args:
        batch_id: Batch ID

    Returns:
        Dictionary of stage statistics
    """
    try:
        stats = log_repo.get_stage_stats(batch_id)
        return {"batch_id": batch_id, "stages": stats}
    except Exception as e:
        logger.error("get_batch_stats_failed", batch_id=batch_id, error=str(e))
        return {"error": str(e)}


@app.get("/api/stream")
async def event_stream(request: Request, batch_id: Optional[int] = None):
    """
    Server-Sent Events endpoint for real-time updates.

    Args:
        batch_id: Optional specific batch ID to stream. If not provided,
                  streams events for the currently processing batch.

    Streams new batch execution events as they occur.
    """
    async def event_generator():
        # Get batch to monitor
        if batch_id is not None:
            current_batch = batch_repo.get_by_id(batch_id)
        else:
            current_batch = batch_repo.get_current_batch()

        if not current_batch:
            yield {
                "event": "error",
                "data": json.dumps({"message": "No active batch found"})
            }
            return

        monitoring_batch_id = current_batch['id']
        last_event_id = 0

        logger.info("sse_stream_started", batch_id=monitoring_batch_id)

        try:
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    logger.info("sse_client_disconnected", batch_id=monitoring_batch_id)
                    break

                # Query new events since last_event_id
                events = log_repo.get_latest_events(
                    monitoring_batch_id,
                    since_id=last_event_id,
                    limit=50
                )

                for event in events:
                    # Convert datetime to ISO string
                    if 'timestamp' in event and event['timestamp']:
                        event['timestamp'] = event['timestamp'].isoformat()

                    event_data = {
                        "id": event['id'],
                        "stage": event['stage'],
                        "eventType": event['eventType'],
                        "fileName": event.get('fileName'),
                        "gpuIp": event.get('gpuIp'),
                        "status": event['status'],
                        "payload": event.get('payload'),
                        "response": event.get('response'),
                        "errorMessage": event.get('errorMessage'),
                        "totalFiles": event.get('totalFiles'),
                        "processedFiles": event.get('processedFiles'),
                        "timestamp": event['timestamp']
                    }

                    yield {
                        "event": event['eventType'],
                        "id": str(event['id']),
                        "data": json.dumps(event_data)
                    }

                    last_event_id = event['id']

                # Wait before polling again (configurable via SSE_POLL_INTERVAL env var)
                # Options: 1s (real-time), 2s (balanced), 5s (less frequent), 10s (minimal)
                await asyncio.sleep(settings.sse_poll_interval)

        except asyncio.CancelledError:
            logger.info("sse_stream_cancelled", batch_id=monitoring_batch_id)
        except Exception as e:
            logger.error("sse_stream_error", batch_id=monitoring_batch_id, error=str(e))
            yield {
                "event": "error",
                "data": json.dumps({"message": str(e)})
            }

    return EventSourceResponse(event_generator())


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5066, log_level="info")
