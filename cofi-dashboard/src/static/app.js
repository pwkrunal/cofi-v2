/**
 * Cofi Dashboard Frontend
 * Handles SSE connection and real-time UI updates
 */

// State management
const state = {
    currentBatch: null,
    stages: {
        file_distribution: { total: 0, processed: 0, errors: 0, status: 'pending' },
        callmetadata: { total: 0, processed: 0, errors: 0, status: 'pending' },
        trademetadata: { total: 0, processed: 0, errors: 0, status: 'pending' },
        denoise: { total: 0, processed: 0, errors: 0, status: 'pending' },
        ivr: { total: 0, processed: 0, errors: 0, status: 'pending' },
        lid: { total: 0, processed: 0, errors: 0, status: 'pending' },
        triaging: { total: 0, processed: 0, errors: 0, status: 'pending' },
        stt: { total: 0, processed: 0, errors: 0, status: 'pending' },
        llm1: { total: 0, processed: 0, errors: 0, status: 'pending' },
        llm2: { total: 0, processed: 0, errors: 0, status: 'pending' }
    },
    events: []
};

// Initialize dashboard
async function init() {
    console.log('Initializing Cofi Dashboard...');

    try {
        await loadCurrentBatch();
        await connectSSE();
    } catch (error) {
        console.error('Dashboard initialization failed:', error);
        showError('Failed to initialize dashboard. Please refresh the page.');
    }
}

// Get batch ID from URL parameter (optional)
function getBatchIdFromUrl() {
    const params = new URLSearchParams(window.location.search);
    return params.get('batch_id');
}

// Load current batch information
async function loadCurrentBatch() {
    try {
        // Check if specific batch_id is requested via URL parameter
        const batchId = getBatchIdFromUrl();
        const url = batchId ? `/api/current-batch?batch_id=${batchId}` : '/api/current-batch';

        const response = await fetch(url);
        const data = await response.json();

        if (data.error || !data.batch_id) {
            showError('No active batch found. Dashboard will show data once batch processing starts.');
            return;
        }

        state.currentBatch = data;
        updateBatchHeader(data);

        // Update stage statuses from API
        if (data.stages) {
            for (const [stageName, stageData] of Object.entries(data.stages)) {
                state.stages[stageName] = {
                    total: stageData.total || 0,
                    processed: stageData.processed || 0,
                    errors: stageData.errors || 0,
                    status: mapStatus(stageData.status)
                };
                updateStageCard(stageName);
            }
        }

        // Load initial logs
        const logsResponse = await fetch(`/api/batch/${data.batch_id}/logs`);
        const events = await logsResponse.json();

        if (Array.isArray(events)) {
            events.reverse().forEach(processEvent);  // Reverse to show chronological order
        }

        console.log('Batch data loaded:', data);
    } catch (error) {
        console.error('Failed to load current batch:', error);
        showError('Failed to load batch data: ' + error.message);
    }
}

// Map batch status to stage status
function mapStatus(status) {
    const statusMap = {
        'Pending': 'pending',
        'InProgress': 'processing',
        'Complete': 'complete',
        'Failed': 'failed'
    };
    return statusMap[status] || 'pending';
}

// Update batch header information
function updateBatchHeader(data) {
    document.getElementById('batch-id').textContent = data.batch_id || '-';
    document.getElementById('batch-date').textContent = data.batch_date || '-';

    const statusBadge = document.getElementById('batch-status');
    statusBadge.textContent = data.status || '-';
    statusBadge.className = `badge ${mapStatus(data.status)}`;

    const currentBadge = document.getElementById('batch-current');
    if (data.current_batch) {
        currentBadge.textContent = 'Yes';
        currentBadge.className = 'badge processing';
    } else {
        currentBadge.textContent = 'No';
        currentBadge.className = 'badge pending';
    }
}

// Connect to SSE stream
async function connectSSE() {
    // If monitoring specific batch, pass batch_id to SSE endpoint
    const batchId = getBatchIdFromUrl();
    const sseUrl = batchId ? `/api/stream?batch_id=${batchId}` : '/api/stream';

    const eventSource = new EventSource(sseUrl);

    eventSource.addEventListener('open', () => {
        console.log('SSE connection established');
    });

    // Handle all event types
    const eventTypes = ['stage_start', 'stage_progress', 'stage_complete', 'file_start', 'file_complete', 'error', 'info'];

    eventTypes.forEach(eventType => {
        eventSource.addEventListener(eventType, (e) => {
            try {
                const data = JSON.parse(e.data);
                processEvent(data);
            } catch (error) {
                console.error('Failed to process event:', error);
            }
        });
    });

    eventSource.addEventListener('error', (error) => {
        console.error('SSE connection error:', error);

        if (eventSource.readyState === EventSource.CLOSED) {
            console.log('SSE connection closed. Attempting reconnection in 5s...');
            setTimeout(() => connectSSE(), 5000);
        }
    });

    return eventSource;
}

// Process incoming event
function processEvent(event) {
    if (!event || !event.stage) return;

    state.events.push(event);

    const stage = event.stage;

    // Ensure stage exists in state
    if (!state.stages[stage]) {
        state.stages[stage] = { total: 0, processed: 0, errors: 0, status: 'pending' };
    }

    switch (event.eventType) {
        case 'stage_start':
            state.stages[stage].status = 'processing';
            state.stages[stage].total = event.totalFiles || state.stages[stage].total;
            break;

        case 'stage_progress':
            state.stages[stage].processed = event.processedFiles || 0;
            break;

        case 'file_start':
            // File started, no state change needed
            break;

        case 'file_complete':
            state.stages[stage].processed++;
            break;

        case 'error':
            state.stages[stage].errors++;
            break;

        case 'stage_complete':
            state.stages[stage].status = 'complete';
            state.stages[stage].processed = event.processedFiles || state.stages[stage].total;
            break;

        case 'info':
            // Informational event, no state change
            break;
    }

    updateStageCard(stage);
    addEventToLog(stage, event);
}

// Update stage card UI
function updateStageCard(stageName) {
    const card = document.querySelector(`.stage-card[data-stage="${stageName}"]`);
    if (!card) {
        console.warn(`Stage card not found for: ${stageName}`);
        return;
    }

    const stageData = state.stages[stageName];

    // Update status badge
    const statusBadge = card.querySelector('.stage-status');
    statusBadge.textContent = stageData.status;
    statusBadge.className = `stage-status ${stageData.status}`;

    // Update progress bar
    const progressPercent = stageData.total > 0
        ? Math.min(100, (stageData.processed / stageData.total) * 100)
        : 0;

    const progressFill = card.querySelector('.progress-fill');
    progressFill.style.width = `${progressPercent}%`;

    const progressText = card.querySelector('.progress-text');
    progressText.textContent = `${stageData.processed}/${stageData.total} ${getUnitName(stageName)}`;

    // Update details
    card.querySelector('.total-files').textContent = stageData.total;
    card.querySelector('.processed-files').textContent = stageData.processed;
    card.querySelector('.error-count').textContent = stageData.errors;

    // Add visual indicator for errors
    if (stageData.errors > 0) {
        card.querySelector('.error-count').style.color = '#e53935';
        card.querySelector('.error-count').style.fontWeight = 'bold';
    }
}

// Get unit name for stage
function getUnitName(stageName) {
    const unitMap = {
        'file_distribution': 'files',
        'callmetadata': 'records',
        'trademetadata': 'records',
        'triaging': 'mappings'
    };
    return unitMap[stageName] || 'files';
}

// Add event to stage log
function addEventToLog(stageName, event) {
    const card = document.querySelector(`.stage-card[data-stage="${stageName}"]`);
    if (!card) return;

    const eventList = card.querySelector('.event-list');
    if (!eventList) return;

    const li = document.createElement('li');
    li.className = `event-item ${event.eventType.replace('_', '-')}`;

    const timestamp = event.timestamp ? new Date(event.timestamp).toLocaleTimeString() : '-';
    let message = `[${timestamp}] `;

    if (event.fileName) {
        message += `📄 ${event.fileName}: `;
    }

    message += formatEventType(event.eventType);

    if (event.errorMessage) {
        message += ` - ${event.errorMessage}`;
    }

    li.textContent = message;

    // Add click handler for payload/response inspection
    if (event.payload || event.response || event.errorMessage) {
        li.style.cursor = 'pointer';
        li.title = 'Click to view details';
        li.onclick = () => showPayloadModal(event);
    }

    eventList.prepend(li);

    // Keep only last 20 events per stage
    while (eventList.children.length > 20) {
        eventList.removeChild(eventList.lastChild);
    }
}

// Format event type for display
function formatEventType(eventType) {
    const typeMap = {
        'stage_start': '▶️ Stage Started',
        'stage_progress': '⏳ Progress Update',
        'stage_complete': '✅ Stage Complete',
        'file_start': '🔄 Processing',
        'file_complete': '✅ Complete',
        'error': '❌ Error',
        'info': 'ℹ️ Info'
    };
    return typeMap[eventType] || eventType;
}

// Show payload/response in modal
function showPayloadModal(event) {
    const modal = document.getElementById('payload-modal');
    const modalTitle = document.getElementById('modal-title');
    const modalJson = document.getElementById('modal-json');

    let content = '';

    // Event details
    content += `Stage: ${event.stage}\n`;
    content += `Event Type: ${event.eventType}\n`;
    content += `Status: ${event.status}\n`;

    if (event.fileName) {
        content += `File: ${event.fileName}\n`;
    }

    if (event.gpuIp) {
        content += `GPU: ${event.gpuIp}\n`;
    }

    content += `Timestamp: ${event.timestamp}\n`;
    content += '\n' + '='.repeat(60) + '\n\n';

    if (event.payload) {
        content += '📤 REQUEST PAYLOAD\n';
        content += '='.repeat(60) + '\n';
        try {
            const payload = typeof event.payload === 'string' ? JSON.parse(event.payload) : event.payload;
            content += JSON.stringify(payload, null, 2);
        } catch (e) {
            content += event.payload;
        }
        content += '\n\n';
    }

    if (event.response) {
        content += '📥 RESPONSE\n';
        content += '='.repeat(60) + '\n';
        try {
            const response = typeof event.response === 'string' ? JSON.parse(event.response) : event.response;
            content += JSON.stringify(response, null, 2);
        } catch (e) {
            content += event.response;
        }
        content += '\n\n';
    }

    if (event.errorMessage) {
        content += '❌ ERROR MESSAGE\n';
        content += '='.repeat(60) + '\n';
        content += event.errorMessage;
    }

    modalTitle.textContent = `${event.stage.toUpperCase()} - ${event.fileName || 'Stage Event'}`;
    modalJson.textContent = content;
    modal.style.display = 'block';
}

// Show error message
function showError(message) {
    console.error(message);
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-banner';
    errorDiv.textContent = message;
    errorDiv.style.cssText = `
        position: fixed;
        top: 20px;
        left: 50%;
        transform: translateX(-50%);
        background: #e53935;
        color: white;
        padding: 15px 30px;
        border-radius: 5px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        z-index: 10000;
        max-width: 80%;
        text-align: center;
    `;
    document.body.appendChild(errorDiv);

    setTimeout(() => {
        errorDiv.remove();
    }, 5000);
}

// Modal close handler
document.addEventListener('DOMContentLoaded', () => {
    const modal = document.getElementById('payload-modal');
    const closeBtn = document.querySelector('.close');

    closeBtn.onclick = () => {
        modal.style.display = 'none';
    };

    window.onclick = (event) => {
        if (event.target === modal) {
            modal.style.display = 'none';
        }
    };

    // Initialize dashboard
    init();
});
