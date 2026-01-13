# Cofi Dashboard

Real-time monitoring dashboard for Cofi batch processing pipeline execution.

## Features

- **Real-time Updates**: Server-Sent Events (SSE) for live pipeline monitoring
- **Stage Tracking**: Monitor all 10 pipeline stages (file distribution, denoise, IVR, LID, STT, LLM1, LLM2, triaging, metadata)
- **Progress Visualization**: Progress bars and statistics for each stage
- **Event Logs**: Detailed event history with timestamps
- **Payload Inspection**: View full request/response payloads in modal dialogs
- **Error Tracking**: Track errors per stage with detailed error messages

## Architecture

```
Browser (HTML/CSS/JS)
    ↓ SSE Connection
FastAPI Server (Port 5066)
    ↓ Read Operations
MySQL Database (batchExecutionLog table)
    ↑ Write Events
Cofi Service (Batch Processing)
```

## Prerequisites

- Python 3.11+
- MySQL database with `batchExecutionLog` table
- Access to the same MySQL database used by cofi-service

## Installation

### 1. Create Database Table

Run the migration SQL to create the `batchExecutionLog` table:

```bash
mysql -u root -p testDb < ../database/migrations/create_batch_execution_log.sql
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your MySQL credentials
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

## Usage

### Local Development

```bash
# Start the dashboard server
python -m uvicorn src.app:app --host 0.0.0.0 --port 5066 --reload

# Open browser
# Navigate to http://localhost:5066
```

### Docker Deployment

```bash
# Build and start the container
docker-compose up -d

# View logs
docker-compose logs -f cofi-dashboard

# Stop the container
docker-compose down
```

## API Endpoints

### Dashboard
- `GET /` - Serve dashboard HTML

### API
- `GET /api/health` - Health check
- `GET /api/current-batch` - Get current batch status
- `GET /api/batch/{batch_id}/logs` - Get batch execution logs
- `GET /api/batch/{batch_id}/stats` - Get batch statistics
- `GET /api/stream` - SSE endpoint for real-time updates

## Dashboard Interface

### Header
- Batch date and number
- Overall batch status
- Total files count

### Stage Cards (10 stages)
Each card displays:
- Stage name and icon
- Status badge (Pending/Processing/Complete/Failed)
- Progress bar with percentage
- Statistics (Total/Processed/Errors)
- Recent events list (last 20 events)

### Event Types
- **Stage Start** - Stage begins processing
- **Stage Progress** - Periodic progress updates
- **Stage Complete** - Stage finished
- **File Start** - File processing begins
- **File Complete** - File processed successfully
- **Error** - Processing error occurred
- **Info** - Informational messages

### Payload Inspection
Click on any event to view:
- Full request payload (JSON)
- Full response data (JSON)
- Error messages (if applicable)
- Event metadata (timestamp, GPU IP, etc.)

## Integration with Cofi Service

The dashboard automatically receives events from cofi-service when:

1. `EventLogger` emits events during batch processing
2. Events are written to `batchExecutionLog` table
3. Dashboard SSE endpoint polls for new events every 2 seconds
4. Browser receives and displays events in real-time

## Troubleshooting

### Dashboard shows "No active batch found"
- Ensure cofi-service has started batch processing
- Check that `batchStatus` table has records

### SSE connection fails
- Verify dashboard server is running on port 5066
- Check firewall settings
- Look for CORS issues in browser console

### No events displayed
- Verify `batchExecutionLog` table exists
- Check MySQL credentials in `.env`
- Ensure cofi-service is logging events (check `EventLogger` integration)

### Events not updating
- Check SSE connection in browser DevTools (Network tab)
- Verify cofi-service is actively processing files
- Look for errors in dashboard server logs

## Development

### Project Structure
```
cofi-dashboard/
├── src/
│   ├── app.py               # FastAPI server with SSE
│   ├── database.py          # MySQL read operations
│   ├── config.py            # Settings management
│   └── static/
│       ├── index.html       # Dashboard UI
│       ├── app.js           # Frontend logic
│       └── style.css        # Styles
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── README.md
```

### Adding New Stage
1. Add stage card HTML in `index.html`
2. Add stage to `state.stages` in `app.js`
3. Update stage colors in `style.css`
4. Ensure cofi-service logs events for the new stage

## Performance Considerations

- SSE polling interval: 2 seconds (configurable in `app.py`)
- Event history limit: 500 events per batch (configurable in `app.py`)
- Per-stage event display: Last 20 events (configurable in `app.js`)
- Database connection pool: 5 connections (configurable in `database.py`)

## Security Notes

- Dashboard is read-only (no write operations to database)
- No authentication implemented (add if deploying publicly)
- Runs on port 5066 (ensure proper firewall configuration)
- MySQL credentials should be kept secure

## License

Internal tool for Cofi Service monitoring.
