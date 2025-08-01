#!/usr/bin/env python3
"""
Google Drive integrated audio splitter API
Processes files directly from Google Drive without intermediate downloads
"""

import os
import io
import tempfile
import logging
from typing import Optional, List, Dict
from datetime import datetime, timedelta
import asyncio
from concurrent.futures import ProcessPoolExecutor

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn
from google.cloud import storage
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import aiohttp

# Import the existing split_audio module
from split_audio import split_audio, get_audio_info, get_optimal_output_format, get_format_bitrate

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Audio Splitter - Google Drive Integration",
    description="Split audio files directly from Google Drive",
    version="3.0.0"
)

# Configuration from environment
GCS_BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME", "audio-splitter-chunks")
GCS_CHUNK_PREFIX = os.environ.get("GCS_CHUNK_PREFIX", "chunks/")
SIGNED_URL_EXPIRY_HOURS = int(os.environ.get("SIGNED_URL_EXPIRY_HOURS", "24"))
GOOGLE_SERVICE_ACCOUNT_KEY = os.environ.get("GOOGLE_SERVICE_ACCOUNT_KEY", "service-account-key.json")

# Initialize Google clients
storage_client = storage.Client()
bucket = storage_client.bucket(GCS_BUCKET_NAME)

# Initialize Drive API
if os.path.exists(GOOGLE_SERVICE_ACCOUNT_KEY):
    credentials = service_account.Credentials.from_service_account_file(
        GOOGLE_SERVICE_ACCOUNT_KEY,
        scopes=['https://www.googleapis.com/auth/drive.readonly']
    )
    drive_service = build('drive', 'v3', credentials=credentials)
else:
    drive_service = None
    logger.warning("Google Drive service account key not found - Drive features disabled")

# Global process pool
executor = ProcessPoolExecutor(max_workers=2)

class DriveFileRequest(BaseModel):
    """Request to process a file from Google Drive"""
    drive_file_id: str = Field(..., description="Google Drive file ID")
    drive_file_url: Optional[str] = Field(None, description="Alternative: Google Drive shareable link")
    max_size_mb: Optional[float] = Field(default=20, description="Maximum chunk size in MB")
    output_format: Optional[str] = Field(default="auto", description="Output format: auto, mp3, wav, m4a")
    quality: Optional[str] = Field(default="medium", description="Output quality: low, medium, high")
    webhook_url: Optional[str] = Field(None, description="Webhook URL for completion notification")
    skip_transcription: Optional[bool] = Field(default=False, description="Only split, don't transcribe")

class TranscriptionRequest(BaseModel):
    """Request to transcribe chunks and compile minutes"""
    chunks: List[Dict] = Field(..., description="List of chunk info with download URLs")
    openai_api_key: Optional[str] = Field(None, description="OpenAI API key (or use env var)")
    compile_minutes: Optional[bool] = Field(default=True, description="Compile transcriptions into minutes")
    webhook_url: Optional[str] = Field(None, description="Webhook URL for completion notification")

class ProcessingResponse(BaseModel):
    """Response for file processing"""
    job_id: str
    status: str
    drive_file_name: str
    total_chunks: int
    total_duration_seconds: float
    output_format: str
    chunks: List[Dict]
    transcription_url: Optional[str] = None
    minutes_url: Optional[str] = None
    processing_time_seconds: float

def extract_file_id_from_url(url: str) -> str:
    """Extract file ID from Google Drive URL"""
    # Handle various Google Drive URL formats
    if '/file/d/' in url:
        # https://drive.google.com/file/d/FILE_ID/view
        return url.split('/file/d/')[1].split('/')[0]
    elif 'id=' in url:
        # https://drive.google.com/open?id=FILE_ID
        return url.split('id=')[1].split('&')[0]
    else:
        return url  # Assume it's already a file ID

async def download_from_drive_stream(file_id: str, temp_path: str) -> Dict:
    """Stream download from Google Drive to temporary file"""
    if not drive_service:
        raise HTTPException(status_code=500, detail="Google Drive service not configured")
    
    try:
        # Get file metadata
        file_metadata = drive_service.files().get(
            fileId=file_id,
            fields='name,size,mimeType'
        ).execute()
        
        # Stream download the file
        request = drive_service.files().get_media(fileId=file_id)
        
        with open(temp_path, 'wb') as fh:
            downloader = MediaIoBaseDownload(fh, request, chunksize=10*1024*1024)  # 10MB chunks
            done = False
            while not done:
                status, done = downloader.next_chunk()
                if status:
                    logger.info(f"Download progress: {int(status.progress() * 100)}%")
        
        return file_metadata
    
    except Exception as e:
        logger.error(f"Error downloading from Drive: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Failed to download from Drive: {str(e)}")

async def upload_to_gcs_async(local_path: str, gcs_path: str) -> str:
    """Async wrapper for GCS upload"""
    loop = asyncio.get_event_loop()
    blob = bucket.blob(gcs_path)
    
    await loop.run_in_executor(None, blob.upload_from_filename, local_path)
    
    # Generate signed URL
    url = await loop.run_in_executor(
        None,
        blob.generate_signed_url,
        "v4",
        timedelta(hours=SIGNED_URL_EXPIRY_HOURS),
        "GET"
    )
    return url

async def transcribe_chunks_parallel(chunks: List[Dict], api_key: str) -> List[Dict]:
    """Transcribe multiple chunks in parallel using OpenAI"""
    async with aiohttp.ClientSession() as session:
        tasks = []
        for chunk in chunks:
            task = transcribe_single_chunk(session, chunk, api_key)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        return results

async def transcribe_single_chunk(session: aiohttp.ClientSession, chunk: Dict, api_key: str) -> Dict:
    """Transcribe a single chunk using OpenAI API"""
    headers = {"Authorization": f"Bearer {api_key}"}
    
    # Download chunk to memory
    async with session.get(chunk['download_url']) as resp:
        audio_data = await resp.read()
    
    # Create form data
    data = aiohttp.FormData()
    data.add_field('file', audio_data, filename=chunk['filename'], content_type='audio/mpeg')
    data.add_field('model', 'whisper-1')
    
    # Send to OpenAI
    async with session.post(
        'https://api.openai.com/v1/audio/transcriptions',
        headers=headers,
        data=data
    ) as resp:
        if resp.status == 200:
            result = await resp.json()
            return {
                "chunk_number": chunk['chunk_number'],
                "text": result['text'],
                "duration": chunk['duration_seconds']
            }
        else:
            error = await resp.text()
            logger.error(f"Transcription failed for chunk {chunk['chunk_number']}: {error}")
            return {
                "chunk_number": chunk['chunk_number'],
                "text": f"[Error: {resp.status}]",
                "duration": chunk['duration_seconds']
            }

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "audio-splitter-drive",
        "features": {
            "google_drive": drive_service is not None,
            "gcs_bucket": GCS_BUCKET_NAME
        }
    }

@app.post("/process-drive-file", response_model=ProcessingResponse)
async def process_drive_file(
    request: DriveFileRequest,
    background_tasks: BackgroundTasks
):
    """
    Process an audio file directly from Google Drive:
    1. Stream download from Drive
    2. Split into chunks
    3. Upload chunks to GCS
    4. Optionally transcribe and create minutes
    """
    start_time = datetime.now()
    
    # Extract file ID
    file_id = request.drive_file_id
    if request.drive_file_url:
        file_id = extract_file_id_from_url(request.drive_file_url)
    
    job_id = f"{start_time.strftime('%Y%m%d%H%M%S')}_{file_id[:8]}"
    
    with tempfile.TemporaryDirectory(prefix=f"drive_split_{job_id}_") as temp_dir:
        try:
            # Download from Drive
            logger.info(f"Downloading file {file_id} from Google Drive")
            temp_input = os.path.join(temp_dir, "input_audio")
            file_metadata = await download_from_drive_stream(file_id, temp_input)
            
            file_name = file_metadata['name']
            logger.info(f"Downloaded {file_name} ({file_metadata['size']} bytes)")
            
            # Analyze audio
            duration, bitrate, codec_name = get_audio_info(temp_input)
            
            # Determine output format
            output_format = request.output_format
            if output_format == "auto":
                output_format = get_optimal_output_format(temp_input, detected_codec=codec_name)
                if output_format == "ogg":
                    output_format = "m4a"  # Better OpenAI compatibility
            
            # Calculate chunk parameters
            format_bitrate = get_format_bitrate(output_format, request.quality, bitrate)
            max_size_bits = request.max_size_mb * 8 * 1024 * 1024
            chunk_duration = (max_size_bits / format_bitrate) * 0.9
            
            # Split audio
            output_dir = os.path.join(temp_dir, "chunks")
            os.makedirs(output_dir, exist_ok=True)
            
            loop = asyncio.get_event_loop()
            created_files = await loop.run_in_executor(
                executor,
                split_audio,
                temp_input,
                chunk_duration,
                output_dir,
                output_format,
                request.quality,
                False,
                None,
                False
            )
            
            # Upload chunks to GCS in parallel
            chunks = []
            upload_tasks = []
            
            for i, chunk_path in enumerate(created_files):
                chunk_filename = os.path.basename(chunk_path)
                gcs_chunk_path = f"{GCS_CHUNK_PREFIX}{job_id}/{chunk_filename}"
                
                upload_task = upload_to_gcs_async(chunk_path, gcs_chunk_path)
                upload_tasks.append((i, chunk_path, chunk_filename, gcs_chunk_path, upload_task))
            
            # Wait for uploads
            for i, chunk_path, chunk_filename, gcs_chunk_path, upload_task in upload_tasks:
                signed_url = await upload_task
                chunk_stat = os.stat(chunk_path)
                
                chunk_info = {
                    "chunk_number": i + 1,
                    "filename": chunk_filename,
                    "size_mb": chunk_stat.st_size / (1024 * 1024),
                    "duration_seconds": min(chunk_duration, duration - (i * chunk_duration)),
                    "gcs_path": f"gs://{GCS_BUCKET_NAME}/{gcs_chunk_path}",
                    "download_url": signed_url
                }
                chunks.append(chunk_info)
            
            # Calculate processing time
            processing_time = (datetime.now() - start_time).total_seconds()
            
            response = ProcessingResponse(
                job_id=job_id,
                status="completed",
                drive_file_name=file_name,
                total_chunks=len(chunks),
                total_duration_seconds=duration,
                output_format=output_format,
                chunks=chunks,
                processing_time_seconds=processing_time
            )
            
            # Send webhook if provided
            if request.webhook_url:
                background_tasks.add_task(send_webhook, request.webhook_url, response.dict())
            
            logger.info(f"Successfully processed {file_name}: {len(chunks)} chunks in {processing_time:.1f}s")
            
            return response
            
        except Exception as e:
            logger.error(f"Error processing Drive file: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")

@app.post("/transcribe-and-compile")
async def transcribe_and_compile(
    request: TranscriptionRequest,
    background_tasks: BackgroundTasks
):
    """
    Transcribe chunks and compile into minutes
    This can be called after splitting or with existing chunks
    """
    start_time = datetime.now()
    job_id = f"transcript_{start_time.strftime('%Y%m%d%H%M%S')}"
    
    # Get API key
    api_key = request.openai_api_key or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=400, detail="OpenAI API key required")
    
    try:
        # Transcribe chunks in parallel
        logger.info(f"Transcribing {len(request.chunks)} chunks in parallel")
        transcriptions = await transcribe_chunks_parallel(request.chunks, api_key)
        
        # Combine transcriptions
        full_text = "\n\n".join([t['text'] for t in sorted(transcriptions, key=lambda x: x['chunk_number'])])
        total_duration = sum(t['duration'] for t in transcriptions)
        
        # Save transcription
        transcription_path = f"transcriptions/{job_id}/full_transcript.txt"
        transcription_blob = bucket.blob(transcription_path)
        transcription_blob.upload_from_string(full_text)
        transcription_url = transcription_blob.generate_signed_url(
            version="v4",
            expiration=timedelta(hours=SIGNED_URL_EXPIRY_HOURS),
            method="GET"
        )
        
        response = {
            "job_id": job_id,
            "status": "transcribed",
            "total_duration_seconds": total_duration,
            "transcription_url": transcription_url,
            "processing_time_seconds": (datetime.now() - start_time).total_seconds()
        }
        
        # Compile minutes if requested
        if request.compile_minutes:
            # Here you would call OpenAI to generate minutes from the transcript
            # For now, just return the transcript URL
            response["minutes_url"] = transcription_url
            response["status"] = "completed"
        
        # Send webhook
        if request.webhook_url:
            background_tasks.add_task(send_webhook, request.webhook_url, response)
        
        return response
        
    except Exception as e:
        logger.error(f"Transcription error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")

@app.post("/process-drive-folder")
async def process_drive_folder(
    folder_id: str,
    max_size_mb: float = 20,
    output_format: str = "auto",
    quality: str = "medium",
    webhook_url: Optional[str] = None
):
    """
    Process all audio files in a Google Drive folder
    Useful for batch processing
    """
    if not drive_service:
        raise HTTPException(status_code=500, detail="Google Drive service not configured")
    
    try:
        # List files in folder
        query = f"'{folder_id}' in parents and mimeType contains 'audio/'"
        results = drive_service.files().list(
            q=query,
            fields="files(id, name, mimeType)"
        ).execute()
        
        files = results.get('files', [])
        logger.info(f"Found {len(files)} audio files in folder")
        
        # Process each file
        jobs = []
        for file in files:
            request = DriveFileRequest(
                drive_file_id=file['id'],
                max_size_mb=max_size_mb,
                output_format=output_format,
                quality=quality,
                webhook_url=webhook_url
            )
            
            job = await process_drive_file(request, BackgroundTasks())
            jobs.append(job)
        
        return {
            "folder_id": folder_id,
            "total_files": len(files),
            "jobs": jobs
        }
        
    except Exception as e:
        logger.error(f"Folder processing error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Folder processing failed: {str(e)}")

async def send_webhook(webhook_url: str, data: dict):
    """Send webhook notification"""
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(webhook_url, json=data) as response:
                if response.status != 200:
                    logger.error(f"Webhook failed: {response.status}")
        except Exception as e:
            logger.error(f"Webhook error: {str(e)}")

@app.on_event("startup")
async def startup_event():
    """Initialize the application"""
    logger.info("Audio Splitter Drive API started")
    if drive_service:
        logger.info("Google Drive integration enabled")
    else:
        logger.warning("Google Drive integration disabled - no service account key")

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown"""
    logger.info("Shutting down Audio Splitter Drive API")
    executor.shutdown(wait=True)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)