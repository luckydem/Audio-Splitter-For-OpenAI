#!/usr/bin/env python3
"""
FastAPI server for audio splitting with Google Cloud Storage integration
Optimized for Google Cloud Run deployment
"""

import os
import json
import tempfile
import logging
from typing import Optional, List
from datetime import datetime, timedelta
import asyncio
from concurrent.futures import ProcessPoolExecutor

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field
import uvicorn
from google.cloud import storage
from google.cloud.storage import Blob

# Import the existing split_audio module
from split_audio import split_audio, get_audio_info, get_optimal_output_format, get_format_bitrate

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Audio Splitter API with GCS",
    description="Split audio files into chunks and store in Google Cloud Storage",
    version="2.0.0"
)

# Configuration from environment
GCS_BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME", "audio-splitter-chunks")
GCS_UPLOAD_PREFIX = os.environ.get("GCS_UPLOAD_PREFIX", "uploads/")
GCS_CHUNK_PREFIX = os.environ.get("GCS_CHUNK_PREFIX", "chunks/")
SIGNED_URL_EXPIRY_HOURS = int(os.environ.get("SIGNED_URL_EXPIRY_HOURS", "24"))

# Initialize GCS client
storage_client = storage.Client()
bucket = storage_client.bucket(GCS_BUCKET_NAME)

# Global process pool for CPU-intensive operations
executor = ProcessPoolExecutor(max_workers=2)

class SplitRequest(BaseModel):
    """Request model for audio splitting parameters"""
    max_size_mb: Optional[float] = Field(default=20, description="Maximum chunk size in MB")
    output_format: Optional[str] = Field(default="auto", description="Output format: auto, mp3, wav, m4a, flac")
    quality: Optional[str] = Field(default="medium", description="Output quality: low, medium, high")
    webhook_url: Optional[str] = Field(default=None, description="Webhook URL for completion notification")

class ChunkInfo(BaseModel):
    """Information about a single audio chunk"""
    chunk_number: int
    filename: str
    size_mb: float
    duration_seconds: float
    gcs_path: str
    download_url: str
    
class SplitResponse(BaseModel):
    """Response model for split operation"""
    job_id: str
    status: str
    input_filename: str
    total_chunks: int
    total_duration_seconds: float
    output_format: str
    chunks: List[ChunkInfo]
    processing_time_seconds: float

def upload_to_gcs(local_path: str, gcs_path: str) -> str:
    """Upload a file to Google Cloud Storage and return signed URL"""
    blob = bucket.blob(gcs_path)
    blob.upload_from_filename(local_path)
    
    # Generate signed URL for download
    url = blob.generate_signed_url(
        version="v4",
        expiration=timedelta(hours=SIGNED_URL_EXPIRY_HOURS),
        method="GET"
    )
    return url

async def upload_to_gcs_async(local_path: str, gcs_path: str) -> str:
    """Async wrapper for GCS upload"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, upload_to_gcs, local_path, gcs_path)

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "audio-splitter-gcs",
        "bucket": GCS_BUCKET_NAME
    }

@app.post("/split", response_model=SplitResponse)
async def split_audio_endpoint(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    max_size_mb: float = 20,
    output_format: str = "auto",
    quality: str = "medium",
    webhook_url: Optional[str] = None
):
    """
    Split an audio file into chunks and upload to GCS.
    
    - **file**: Audio file to split (MP3, WAV, FLAC, OGG, M4A, WMA, etc.)
    - **max_size_mb**: Maximum size per chunk in MB (default: 20)
    - **output_format**: Output format (auto, mp3, wav, m4a, flac)
    - **quality**: Output quality (low, medium, high)
    - **webhook_url**: Optional webhook for completion notification
    """
    start_time = datetime.now()
    job_id = f"{start_time.strftime('%Y%m%d%H%M%S')}_{file.filename.replace(' ', '_')}"
    
    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    
    # Create temporary directory for processing
    with tempfile.TemporaryDirectory(prefix=f"audio_split_{job_id}_") as temp_dir:
        input_path = os.path.join(temp_dir, file.filename)
        output_dir = os.path.join(temp_dir, "chunks")
        os.makedirs(output_dir, exist_ok=True)
        
        try:
            # Save uploaded file
            with open(input_path, "wb") as f:
                content = await file.read()
                f.write(content)
            
            logger.info(f"Processing file: {file.filename} (job_id: {job_id})")
            
            # Upload original file to GCS
            original_gcs_path = f"{GCS_UPLOAD_PREFIX}{job_id}/{file.filename}"
            await upload_to_gcs_async(input_path, original_gcs_path)
            
            # Analyze audio file
            duration, bitrate, codec_name = get_audio_info(input_path)
            
            # Determine output format
            if output_format == "auto":
                output_format = get_optimal_output_format(input_path, detected_codec=codec_name)
                # Avoid OGG for better OpenAI compatibility
                if output_format == "ogg":
                    output_format = "m4a"
            
            # Calculate chunk duration
            format_bitrate = get_format_bitrate(output_format, quality, bitrate)
            max_size_bits = max_size_mb * 8 * 1024 * 1024
            chunk_duration = (max_size_bits / format_bitrate) * 0.9  # 10% safety margin
            num_chunks = int(duration / chunk_duration) + (1 if duration % chunk_duration > 0 else 0)
            
            # Split audio (run in process pool to avoid blocking)
            loop = asyncio.get_event_loop()
            created_files = await loop.run_in_executor(
                executor,
                split_audio,
                input_path,
                chunk_duration,
                output_dir,
                output_format,
                quality,
                False,  # verbose
                None,   # logger
                False   # stream_mode
            )
            
            # Upload chunks to GCS in parallel
            chunks = []
            upload_tasks = []
            
            for i, chunk_path in enumerate(created_files):
                chunk_filename = os.path.basename(chunk_path)
                gcs_chunk_path = f"{GCS_CHUNK_PREFIX}{job_id}/{chunk_filename}"
                
                # Start upload task
                upload_task = upload_to_gcs_async(chunk_path, gcs_chunk_path)
                upload_tasks.append((i, chunk_path, chunk_filename, gcs_chunk_path, upload_task))
            
            # Wait for all uploads to complete
            for i, chunk_path, chunk_filename, gcs_chunk_path, upload_task in upload_tasks:
                signed_url = await upload_task
                chunk_stat = os.stat(chunk_path)
                
                chunk_info = ChunkInfo(
                    chunk_number=i + 1,
                    filename=chunk_filename,
                    size_mb=chunk_stat.st_size / (1024 * 1024),
                    duration_seconds=min(chunk_duration, duration - (i * chunk_duration)),
                    gcs_path=f"gs://{GCS_BUCKET_NAME}/{gcs_chunk_path}",
                    download_url=signed_url
                )
                chunks.append(chunk_info)
            
            # Calculate processing time
            processing_time = (datetime.now() - start_time).total_seconds()
            
            response = SplitResponse(
                job_id=job_id,
                status="completed",
                input_filename=file.filename,
                total_chunks=len(chunks),
                total_duration_seconds=duration,
                output_format=output_format,
                chunks=chunks,
                processing_time_seconds=processing_time
            )
            
            # Send webhook notification if provided
            if webhook_url:
                background_tasks.add_task(send_webhook, webhook_url, response.dict())
            
            logger.info(f"Successfully processed {file.filename}: {len(chunks)} chunks in {processing_time:.1f}s")
            
            return response
            
        except Exception as e:
            logger.error(f"Error processing {file.filename}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")

@app.post("/split-from-gcs")
async def split_from_gcs(
    gcs_path: str,
    max_size_mb: float = 20,
    output_format: str = "auto",
    quality: str = "medium",
    webhook_url: Optional[str] = None
):
    """
    Split an audio file already stored in GCS.
    
    - **gcs_path**: GCS path (gs://bucket/path/to/file.mp3)
    - **max_size_mb**: Maximum size per chunk in MB
    - **output_format**: Output format
    - **quality**: Output quality
    - **webhook_url**: Optional webhook for completion notification
    """
    # Parse GCS path
    if not gcs_path.startswith("gs://"):
        raise HTTPException(status_code=400, detail="Invalid GCS path format")
    
    parts = gcs_path[5:].split("/", 1)
    if len(parts) != 2:
        raise HTTPException(status_code=400, detail="Invalid GCS path format")
    
    bucket_name, blob_path = parts
    
    # Download file from GCS and process
    with tempfile.TemporaryDirectory() as temp_dir:
        local_path = os.path.join(temp_dir, os.path.basename(blob_path))
        
        # Download from GCS
        source_bucket = storage_client.bucket(bucket_name)
        blob = source_bucket.blob(blob_path)
        blob.download_to_filename(local_path)
        
        # Create fake upload file
        with open(local_path, "rb") as f:
            content = f.read()
        
        # Process using existing endpoint logic
        # (In production, refactor to share code properly)
        upload = UploadFile(filename=os.path.basename(blob_path))
        upload.file = content
        
        return await split_audio_endpoint(
            BackgroundTasks(),
            upload,
            max_size_mb,
            output_format,
            quality,
            webhook_url
        )

async def send_webhook(webhook_url: str, data: dict):
    """Send completion notification to webhook"""
    import aiohttp
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=data) as response:
                if response.status != 200:
                    logger.error(f"Webhook failed: {response.status}")
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")

@app.on_event("startup")
async def startup_event():
    """Initialize the application"""
    logger.info(f"Audio Splitter API started with GCS bucket: {GCS_BUCKET_NAME}")
    
    # Verify bucket access
    try:
        list(bucket.list_blobs(max_results=1))
        logger.info("GCS bucket access verified")
    except Exception as e:
        logger.error(f"Failed to access GCS bucket: {str(e)}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown"""
    logger.info("Shutting down Audio Splitter API")
    executor.shutdown(wait=True)

if __name__ == "__main__":
    # For local development
    uvicorn.run(app, host="0.0.0.0", port=8080)