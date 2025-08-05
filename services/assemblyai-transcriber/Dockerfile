# Simplified Dockerfile for AssemblyAI transcription service
# Much smaller and faster than the original since we don't need FFmpeg or heavy audio processing

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install only essential system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements-assemblyai.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements-assemblyai.txt

# Copy only necessary application files
COPY src/audio_transcriber_assemblyai.py src/
COPY src/transcription/ src/transcription/
COPY config/service-account-key.json config/

# Create necessary directories
RUN mkdir -p config logs

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8080
ENV GOOGLE_APPLICATION_CREDENTIALS=config/service-account-key.json

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8080/health')"

# Run the application
CMD ["python", "src/audio_transcriber_assemblyai.py"]