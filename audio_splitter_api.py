#!/usr/bin/env python3
"""
FastAPI server for audio splitting service
Designed for Google Cloud Run deployment
"""

import os
import json
import tempfile
import shutil
import logging
from pathlib import Path
from typing import Optional, List
from datetime import datetime
import asyncio
from concurrent.futures import ProcessPoolExecutor

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field
import uvicorn

# Import the existing split_audio module
from split_audio import split_audio, get_audio_info, get_optimal_output_format, get_format_bitrate

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Audio Splitter API",
    description="Split audio files into chunks for OpenAI Whisper transcription",
    version="1.0.0"
)

# Global process pool for CPU-intensive operations
executor = ProcessPoolExecutor(max_workers=2)

class SplitRequest(BaseModel):
    """Request model for audio splitting parameters"""
    max_size_mb: Optional[float] = Field(default=20, description="Maximum chunk size in MB")
    output_format: Optional[str] = Field(default="auto", description="Output format: auto, mp3, wav, m4a, flac")
    quality: Optional[str] = Field(default="medium", description="Output quality: low, medium, high")
    return_urls: Optional[bool] = Field(default=True, description="Return download URLs instead of inline data")

class ChunkInfo(BaseModel):
    """Information about a single audio chunk"""
    chunk_number: int
    filename: str
    size_mb: float
    duration_seconds: float
    download_url: Optional[str] = None
    
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

# In-memory job storage (use Redis/Firestore in production)
jobs = {}

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "healthy", "service": "audio-splitter"}

@app.post("/split", response_model=SplitResponse)
async def split_audio_endpoint(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    max_size_mb: float = 20,
    output_format: str = "auto",
    quality: str = "medium",
    return_urls: bool = True
):
    """
    Split an audio file into chunks.
    
    - **file**: Audio file to split (MP3, WAV, FLAC, OGG, M4A, WMA, etc.)
    - **max_size_mb**: Maximum size per chunk in MB (default: 20)
    - **output_format**: Output format (auto, mp3, wav, m4a, flac)
    - **quality**: Output quality (low, medium, high)
    - **return_urls**: Return download URLs vs inline data
    """
    start_time = datetime.now()
    job_id = f"{start_time.strftime('%Y%m%d%H%M%S')}_{file.filename}"
    
    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    
    # Create temporary directory for this job
    temp_dir = tempfile.mkdtemp(prefix=f"audio_split_{job_id}_")
    input_path = os.path.join(temp_dir, file.filename)
    output_dir = os.path.join(temp_dir, "chunks")
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        # Save uploaded file
        with open(input_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        logger.info(f"Processing file: {file.filename} (job_id: {job_id})")
        
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
        
        # Prepare response
        chunks = []
        for i, chunk_path in enumerate(created_files):
            chunk_stat = os.stat(chunk_path)
            chunk_info = ChunkInfo(
                chunk_number=i + 1,
                filename=os.path.basename(chunk_path),
                size_mb=chunk_stat.st_size / (1024 * 1024),
                duration_seconds=min(chunk_duration, duration - (i * chunk_duration))
            )
            
            if return_urls:
                # In production, upload to GCS and return signed URLs
                # For now, store path for download endpoint
                chunk_info.download_url = f"/download/{job_id}/{chunk_info.filename}"
            
            chunks.append(chunk_info)
        
        # Store job info for download endpoint
        jobs[job_id] = {
            "temp_dir": temp_dir,
            "chunks": created_files,
            "created_at": start_time
        }
        
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
        
        # Schedule cleanup after 1 hour (in production, use Cloud Scheduler)
        background_tasks.add_task(cleanup_job, job_id, delay_seconds=3600)
        
        return response
        
    except Exception as e:
        logger.error(f"Error processing {file.filename}: {str(e)}")
        # Clean up on error
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")

@app.get("/download/{job_id}/{filename}")
async def download_chunk(job_id: str, filename: str):
    """Download a specific chunk file"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    file_path = os.path.join(job["temp_dir"], "chunks", filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        path=file_path,
        media_type="audio/mpeg",
        filename=filename
    )

@app.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    """Get status of a split job"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    return {
        "job_id": job_id,
        "status": "completed",
        "created_at": job["created_at"].isoformat(),
        "chunk_count": len(job["chunks"])
    }

@app.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    """Delete a job and its files"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    await cleanup_job(job_id)
    return {"message": "Job deleted successfully"}

async def cleanup_job(job_id: str, delay_seconds: int = 0):
    """Clean up temporary files for a job"""
    if delay_seconds > 0:
        await asyncio.sleep(delay_seconds)
    
    if job_id in jobs:
        job = jobs[job_id]
        if os.path.exists(job["temp_dir"]):
            shutil.rmtree(job["temp_dir"])
        del jobs[job_id]
        logger.info(f"Cleaned up job: {job_id}")

@app.on_event("startup")
async def startup_event():
    """Initialize the application"""
    logger.info("Audio Splitter API started")
    # In production: Initialize GCS client, Redis connection, etc.

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown"""
    logger.info("Shutting down Audio Splitter API")
    # Clean up all temporary files
    for job_id in list(jobs.keys()):
        await cleanup_job(job_id)
    executor.shutdown(wait=True)

if __name__ == "__main__":
    # For local development
    uvicorn.run(app, host="0.0.0.0", port=8080)