FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY app.py .
COPY docker_service.py .

# Set environment
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8000

CMD ["python", "app.py"]
