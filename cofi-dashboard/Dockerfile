FROM python:3.11-slim

LABEL maintainer="Cofi Dashboard Team"
LABEL description="Real-time monitoring dashboard for Cofi batch processing pipeline"

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/

# Expose dashboard port
EXPOSE 5066

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5066/api/health')" || exit 1

# Run the application
CMD ["uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "5066", "--log-level", "info"]
