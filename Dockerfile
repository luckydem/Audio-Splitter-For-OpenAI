# Use Python slim image for smaller size
FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements-production.txt .
RUN pip install --no-cache-dir -r requirements-production.txt

# Copy application code
COPY split_audio.py .
COPY audio_splitter_drive.py .
COPY service-account-key.json .

# Create directories for logs and temp files
RUN mkdir -p /app/logs /tmp/audio_splits

# Set environment variables
ENV PORT=8080
ENV PYTHONUNBUFFERED=1

# Run as non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8080

# Start the application
CMD ["uvicorn", "audio_splitter_drive:app", "--host", "0.0.0.0", "--port", "8080"]