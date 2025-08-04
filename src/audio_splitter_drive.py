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
from functools import partial
from urllib.parse import urlparse
import math

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
from split_audio import split_audio, get_audio_info, get_optimal_output_format, calculate_chunk_duration

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

# Initialize credentials and Google clients
if os.path.exists(GOOGLE_SERVICE_ACCOUNT_KEY):
    # Use service account credentials for both Drive and Storage
    credentials = service_account.Credentials.from_service_account_file(
        GOOGLE_SERVICE_ACCOUNT_KEY,
        scopes=[
            'https://www.googleapis.com/auth/drive.readonly',
            'https://www.googleapis.com/auth/devstorage.read_write'
        ]
    )
    storage_client = storage.Client(credentials=credentials)
    drive_service = build('drive', 'v3', credentials=credentials)
    logger.info(f"Using service account credentials from {GOOGLE_SERVICE_ACCOUNT_KEY}")
else:
    # Fall back to default credentials
    storage_client = storage.Client()
    drive_service = None
    logger.warning("Service account key not found - using default credentials")

bucket = storage_client.bucket(GCS_BUCKET_NAME)

# Global process pool
executor = ProcessPoolExecutor(max_workers=2)

# OpenAI Whisper compatible formats and size limits
WHISPER_COMPATIBLE_FORMATS = {'.mp3', '.mp4', '.mpeg', '.mpga', '.m4a', '.wav', '.webm'}
WHISPER_MAX_SIZE_MB = 25

def needs_splitting(file_path: str, file_size_bytes: int, original_filename: str = None) -> bool:
    """
    Determine if a file needs splitting for OpenAI Whisper
    Returns True if file needs splitting, False if it can be sent directly
    """
    file_size_mb = file_size_bytes / (1024 * 1024)
    
    # Try to get extension from original filename first, then fallback to file_path
    if original_filename:
        file_ext = os.path.splitext(original_filename.lower())[1]
    else:
        file_ext = os.path.splitext(os.path.basename(file_path).lower())[1]
    
    # Check if file is compatible format and under size limit
    is_compatible_format = file_ext in WHISPER_COMPATIBLE_FORMATS
    is_under_size_limit = file_size_mb <= WHISPER_MAX_SIZE_MB
    
    logger.info(f"File check: '{file_ext}' format from {'original filename' if original_filename else 'file path'}, {file_size_mb:.1f}MB size")
    logger.info(f"Compatible format: {is_compatible_format}, Under limit: {is_under_size_limit}")
    logger.info(f"File path: {file_path}, Original filename: {original_filename}")
    
    return not (is_compatible_format and is_under_size_limit)

async def transcribe_file_directly(file_path: str, api_key: str) -> Dict:
    """Transcribe a file directly without splitting"""
    logger.info(f"Transcribing file directly: {os.path.basename(file_path)}")
    start_time = datetime.now()
    
    async with aiohttp.ClientSession() as session:
        with open(file_path, 'rb') as audio_file:
            audio_data = audio_file.read()
            filename = os.path.basename(file_path)
            
            # Determine content type
            file_ext = os.path.splitext(filename.lower())[1]
            content_type_map = {
                '.mp3': 'audio/mpeg',
                '.mp4': 'audio/mp4', 
                '.m4a': 'audio/mp4',
                '.wav': 'audio/wav',
                '.webm': 'audio/webm'
            }
            content_type = content_type_map.get(file_ext, 'audio/mpeg')
            
            # Create form data
            data = aiohttp.FormData()
            data.add_field('file', audio_data, filename=filename, content_type=content_type)
            data.add_field('model', 'whisper-1')
            
            logger.info(f"Sending {len(audio_data)/(1024*1024):.1f}MB file to OpenAI Whisper API")
            
            async with session.post(
                'https://api.openai.com/v1/audio/transcriptions',
                headers={"Authorization": f"Bearer {api_key}"},
                data=data
            ) as resp:
                response_time = (datetime.now() - start_time).total_seconds()
                
                if resp.status == 200:
                    result = await resp.json()
                    logger.info(f"✅ Direct transcription successful in {response_time:.1f}s. Text length: {len(result['text'])} chars")
                    return {
                        "text": result['text'],
                        "duration": get_audio_info(file_path)[0],  # Get duration from file
                        "method": "direct"
                    }
                else:
                    error_text = await resp.text()
                    logger.error(f"❌ Direct transcription failed: {resp.status} - {error_text}")
                    raise Exception(f"OpenAI API error: {resp.status} - {error_text}")

class DriveFileRequest(BaseModel):
    """Request to process a file from Google Drive"""
    drive_file_id: Optional[str] = Field(None, description="Google Drive file ID")
    drive_file_url: Optional[str] = Field(None, description="Alternative: Google Drive shareable link")
    max_size_mb: Optional[float] = Field(default=23, description="Maximum chunk size in MB")
    output_format: Optional[str] = Field(default="auto", description="Output format: auto, mp3, wav, m4a")
    quality: Optional[str] = Field(default="medium", description="Output quality: low, medium, high")
    webhook_url: Optional[str] = Field(None, description="Webhook URL for completion notification")
    backup_webhook_url: Optional[str] = Field(None, description="Backup webhook URL if primary fails")
    notification_email: Optional[str] = Field(None, description="Email address for completion notifications")
    openai_api_key: Optional[str] = Field(None, description="OpenAI API key for transcription")
    skip_transcription: Optional[bool] = Field(default=False, description="Only split, don't transcribe")
    
    # Folder organization parameters
    source_folder: Optional[str] = Field(None, description="Source folder name/ID for organization")
    transcription_folder: Optional[str] = Field(None, description="Target folder for transcription files")
    processed_folder: Optional[str] = Field(None, description="Target folder for processed source files")
    
    def model_post_init(self, __context) -> None:
        if not self.drive_file_id and not self.drive_file_url:
            raise ValueError("Either drive_file_id or drive_file_url must be provided")

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

class JobStatusResponse(BaseModel):
    """Initial response with job status and estimates"""
    job_id: str
    status: str
    file_name: str
    file_size_mb: float
    processing_method: str  # "direct_transcription" or "split_and_transcribe"
    estimated_chunks: Optional[int] = None
    estimated_processing_time_seconds: Optional[int] = None
    message: str

class TranscriptionResult(BaseModel):
    """Final transcription result"""
    job_id: str
    status: str
    file_name: str
    transcription_text: str
    total_duration_seconds: float
    processing_method: str
    chunks_processed: Optional[int] = None
    processing_time_seconds: float
    transcription_url: str
    webhook_delivered: Optional[bool] = None  # Track webhook delivery status
    
    # Additional parameters (passed through from request)
    drive_file_id: Optional[str] = None  # Original Google Drive file ID
    source_folder: Optional[str] = None
    transcription_folder: Optional[str] = None
    processed_folder: Optional[str] = None

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

def is_n8n_resume_url(webhook_url: str) -> bool:
    """Check if the webhook URL appears to be an n8n resume URL"""
    if not webhook_url:
        return False
    
    # n8n resume URLs typically contain patterns like:
    # - /webhook/
    # - /resume or /executions/
    # - execution IDs (long alphanumeric strings)
    n8n_patterns = ['/webhook/', '/resume', '/executions/', '/api/v1/webhooks/']
    url_lower = webhook_url.lower()
    
    return any(pattern in url_lower for pattern in n8n_patterns)

async def test_webhook_connectivity(webhook_url: str) -> Dict[str, any]:
    """Test webhook URL connectivity without sending the full payload"""
    import time
    from urllib.parse import urlparse
    
    result = {
        "url": webhook_url,
        "is_n8n_url": is_n8n_resume_url(webhook_url),
        "reachable": False,
        "response_time": None,
        "status_code": None,
        "error": None
    }
    
    try:
        parsed_url = urlparse(webhook_url)
        if not parsed_url.scheme or not parsed_url.netloc:
            result["error"] = "Invalid URL format"
            return result
            
        start_time = time.time()
        timeout_config = aiohttp.ClientTimeout(total=10, connect=5)
        
        async with aiohttp.ClientSession(timeout=timeout_config) as session:
            # Try a HEAD request first to avoid triggering the webhook
            async with session.head(webhook_url, allow_redirects=False) as response:
                result["response_time"] = time.time() - start_time
                result["status_code"] = response.status
                result["reachable"] = response.status != 404
                
                if response.status in [405, 501]:  # Method not allowed - endpoint exists but doesn't support HEAD
                    result["reachable"] = True
                    result["error"] = f"HEAD method not supported (status {response.status}) - endpoint likely exists"
                elif response.status == 404:
                    result["error"] = "Webhook URL returns 404 - may be expired or invalid"
                elif response.status >= 500:
                    result["error"] = f"Server error: {response.status}"
                    
    except asyncio.TimeoutError:
        result["error"] = "Connection timeout"
    except aiohttp.ClientConnectorError as e:
        result["error"] = f"Connection error: {str(e)}"
    except Exception as e:
        result["error"] = f"Unexpected error: {str(e)}"
    
    return result

async def download_from_drive_stream(file_id: str, temp_path: str) -> Dict:
    """Stream download from Google Drive to temporary file"""
    if not drive_service:
        raise HTTPException(status_code=500, detail="Google Drive service not configured")
    
    try:
        # Get file metadata (with shared drive support)
        file_metadata = drive_service.files().get(
            fileId=file_id,
            fields='name,size,mimeType',
            supportsAllDrives=True
        ).execute()
        
        # Stream download the file (with shared drive support)
        request = drive_service.files().get_media(fileId=file_id, supportsAllDrives=True)
        
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
    
    # Generate signed URL with proper arguments
    generate_url_func = partial(
        blob.generate_signed_url,
        version="v4",
        expiration=timedelta(hours=SIGNED_URL_EXPIRY_HOURS),
        method="GET"
    )
    url = await loop.run_in_executor(None, generate_url_func)
    return url

async def transcribe_chunks_parallel(chunks: List[Dict], api_key: str) -> List[Dict]:
    """Transcribe multiple chunks in parallel using OpenAI"""
    start_time = datetime.now()
    logger.info(f"Starting parallel transcription of {len(chunks)} chunks")
    
    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=300)  # 5 minute timeout
    ) as session:
        tasks = []
        for i, chunk in enumerate(chunks):
            logger.info(f"Creating transcription task {i+1}/{len(chunks)} for chunk {chunk.get('chunk_number', 'unknown')}")
            task = transcribe_single_chunk(session, chunk, api_key)
            tasks.append(task)
        
        logger.info(f"All {len(tasks)} transcription tasks created, starting parallel execution...")
        
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results and log summary
            successful = 0
            failed = 0
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Task {i+1} failed with exception: {result}")
                    failed += 1
                elif result.get('text', '').startswith('[Error'):
                    logger.warning(f"Task {i+1} completed with error: {result.get('text', '')[:50]}...")
                    failed += 1
                else:
                    successful += 1
            
            total_time = (datetime.now() - start_time).total_seconds()
            logger.info(f"Parallel transcription completed in {total_time:.1f}s: {successful} successful, {failed} failed")
            
            # Convert exceptions to error results
            processed_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    processed_results.append({
                        "chunk_number": i + 1,
                        "text": f"[Task Exception: {str(result)[:100]}]",
                        "duration": 0
                    })
                else:
                    processed_results.append(result)
            
            return processed_results
            
        except Exception as e:
            total_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"Fatal error in parallel transcription after {total_time:.1f}s: {str(e)}")
            raise

async def transcribe_single_chunk(session: aiohttp.ClientSession, chunk: Dict, api_key: str) -> Dict:
    """Transcribe a single chunk using OpenAI API"""
    chunk_num = chunk['chunk_number']
    filename = chunk['filename']
    download_url = chunk['download_url']
    
    logger.info(f"Starting transcription for chunk {chunk_num}: {filename}")
    start_time = datetime.now()
    
    try:
        # Download chunk to memory
        logger.info(f"Chunk {chunk_num}: Downloading from {download_url[:50]}...")
        async with session.get(download_url) as resp:
            if resp.status != 200:
                logger.error(f"Chunk {chunk_num}: Failed to download audio data. Status: {resp.status}")
                return {
                    "chunk_number": chunk_num,
                    "text": f"[Download Error: {resp.status}]",
                    "duration": chunk.get('duration_seconds', 0)
                }
            
            audio_data = await resp.read()
            audio_size_mb = len(audio_data) / (1024 * 1024)
            logger.info(f"Chunk {chunk_num}: Downloaded {audio_size_mb:.1f}MB audio data")
        
        # Determine content type based on filename
        content_type = 'audio/mp4' if filename.endswith('.m4a') else 'audio/mpeg'
        logger.info(f"Chunk {chunk_num}: Using content-type {content_type}")
        
        # Create form data
        data = aiohttp.FormData()
        data.add_field('file', audio_data, filename=filename, content_type=content_type)
        data.add_field('model', 'whisper-1')
        
        # Send to OpenAI
        logger.info(f"Chunk {chunk_num}: Sending {audio_size_mb:.1f}MB to OpenAI Whisper API")
        
        async with session.post(
            'https://api.openai.com/v1/audio/transcriptions',
            headers={"Authorization": f"Bearer {api_key}"},
            data=data
        ) as resp:
            response_time = (datetime.now() - start_time).total_seconds()
            
            if resp.status == 200:
                result = await resp.json()
                text_length = len(result['text'])
                logger.info(f"Chunk {chunk_num}: ✅ Transcription successful in {response_time:.1f}s. Text length: {text_length} chars")
                logger.info(f"Chunk {chunk_num}: First 100 chars: {result['text'][:100]}...")
                
                return {
                    "chunk_number": chunk_num,
                    "text": result['text'],
                    "duration": chunk.get('duration_seconds', 0)
                }
            else:
                error_text = await resp.text()
                logger.error(f"Chunk {chunk_num}: ❌ OpenAI API failed with status {resp.status} in {response_time:.1f}s")
                logger.error(f"Chunk {chunk_num}: Error response: {error_text}")
                
                return {
                    "chunk_number": chunk_num,
                    "text": f"[OpenAI Error {resp.status}: {error_text[:100]}]",
                    "duration": chunk.get('duration_seconds', 0)
                }
    
    except Exception as e:
        response_time = (datetime.now() - start_time).total_seconds()
        logger.error(f"Chunk {chunk_num}: ❌ Exception during transcription after {response_time:.1f}s: {str(e)}")
        return {
            "chunk_number": chunk_num,
            "text": f"[Exception: {str(e)[:100]}]",
            "duration": chunk.get('duration_seconds', 0)
        }

async def process_file_async(
    job_id: str,
    file_name: str,
    file_size_bytes: int,
    temp_input_path: str,
    request: DriveFileRequest,
    webhook_url: Optional[str] = None
):
    """
    Asynchronously process file - either direct transcription or split+transcribe
    This runs in the background and sends webhook when complete
    """
    start_time = datetime.now()
    
    # Log webhook URL details at the start
    if webhook_url:
        parsed_webhook = urlparse(webhook_url)
        logger.info(f"Job {job_id}: 🔗 Webhook URL provided - Domain: {parsed_webhook.scheme}://{parsed_webhook.netloc}")
        logger.info(f"Job {job_id}: 🔗 Webhook path: {parsed_webhook.path}")
        logger.info(f"Job {job_id}: 🔗 Is n8n resume URL: {is_n8n_resume_url(webhook_url)}")
    else:
        logger.info(f"Job {job_id}: ⚠️  No webhook URL provided - results will not be sent back")
    
    try:
        # Get API key
        api_key = request.openai_api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise Exception("OpenAI API key required")
        
        # Check if file needs splitting
        if not needs_splitting(temp_input_path, file_size_bytes, file_name):
            # Direct transcription path
            logger.info(f"Job {job_id}: Processing via direct transcription")
            
            transcription_result = await transcribe_file_directly(temp_input_path, api_key)
            
            # Upload transcription to GCS
            transcription_path = f"transcriptions/{job_id}/direct_transcript.txt"
            transcription_blob = bucket.blob(transcription_path)
            transcription_blob.upload_from_string(transcription_result['text'])
            
            # Generate signed URL
            generate_url_func = partial(
                transcription_blob.generate_signed_url,
                version="v4",
                expiration=timedelta(hours=SIGNED_URL_EXPIRY_HOURS),
                method="GET"
            )
            loop = asyncio.get_event_loop()
            transcription_url = await loop.run_in_executor(None, generate_url_func)
            
            # Create final result
            result = TranscriptionResult(
                job_id=job_id,
                status="completed",
                file_name=file_name,
                transcription_text=transcription_result['text'],
                total_duration_seconds=transcription_result['duration'],
                processing_method="direct_transcription",
                chunks_processed=1,
                processing_time_seconds=(datetime.now() - start_time).total_seconds(),
                transcription_url=transcription_url,
                webhook_delivered=None,  # Will be updated after webhook attempt
                # Pass through parameters from request
                drive_file_id=request.drive_file_id,
                source_folder=request.source_folder,
                transcription_folder=request.transcription_folder,
                processed_folder=request.processed_folder
            )
            
        else:
            # Split and transcribe path
            logger.info(f"Job {job_id}: Processing via split and transcribe")
            
            # Analyze audio
            duration, bitrate, codec_name = get_audio_info(temp_input_path)
            
            # Determine output format
            output_format = request.output_format
            if output_format == "auto":
                output_format = get_optimal_output_format(temp_input_path, detected_codec=codec_name)
                if output_format == "ogg":
                    output_format = "m4a"  # Better OpenAI compatibility
            
            # Calculate chunk duration - match the bitrates in split_audio.py
            quality_bitrates = {'high': 128, 'medium': 64, 'low': 32}
            output_bitrate = quality_bitrates.get(request.quality, 64)
            chunk_duration = calculate_chunk_duration(bitrate, request.max_size_mb, output_format, output_bitrate)
            logger.info(f"Job {job_id}: Calculated chunk_duration={chunk_duration:.2f}s for {duration:.2f}s audio, expecting {math.ceil(duration/chunk_duration)} chunks")
            
            # Split audio
            with tempfile.TemporaryDirectory() as chunk_temp_dir:
                output_dir = os.path.join(chunk_temp_dir, "chunks")
                os.makedirs(output_dir, exist_ok=True)
                
                loop = asyncio.get_event_loop()
                created_files = await loop.run_in_executor(
                    executor,
                    split_audio,
                    temp_input_path,
                    chunk_duration,
                    output_dir,
                    output_format,
                    request.quality,
                    False,  # verbose
                    None,   # logger
                    False   # stream_mode - for Cloud Run we process all at once
                )
                
                # Process chunks with streaming transcription
                chunks_info = []
                
                logger.info(f"Job {job_id}: Starting streaming transcription of {len(created_files)} chunks")
                
                # Create tasks for upload and transcription
                tasks = []
                for i, chunk_path in enumerate(created_files):
                    task = process_chunk_with_transcription(
                        i, chunk_path, job_id, chunk_duration, duration, api_key
                    )
                    tasks.append(task)
                
                # Process chunks in parallel
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Collect results
                successful_transcriptions = []
                total_duration_processed = 0
                
                for result in results:
                    if isinstance(result, Exception):
                        logger.error(f"Job {job_id}: Chunk processing failed: {result}")
                        continue
                    
                    chunks_info.append(result['chunk_info'])
                    if result['transcription']:
                        successful_transcriptions.append(result['transcription'])
                        total_duration_processed += result['transcription']['duration']
                
                # Combine transcriptions
                if successful_transcriptions:
                    full_text = "\n\n".join([
                        t['text'] for t in sorted(successful_transcriptions, key=lambda x: x['chunk_number'])
                    ])
                else:
                    full_text = "[No successful transcriptions]"
                
                # Upload combined transcription
                transcription_path = f"transcriptions/{job_id}/full_transcript.txt"
                transcription_blob = bucket.blob(transcription_path)
                transcription_blob.upload_from_string(full_text)
                
                generate_url_func = partial(
                    transcription_blob.generate_signed_url,
                    version="v4",
                    expiration=timedelta(hours=SIGNED_URL_EXPIRY_HOURS),
                    method="GET"
                )
                loop = asyncio.get_event_loop()
                transcription_url = await loop.run_in_executor(None, generate_url_func)
                
                # Create final result
                result = TranscriptionResult(
                    job_id=job_id,
                    status="completed",
                    file_name=file_name,
                    transcription_text=full_text,
                    total_duration_seconds=total_duration_processed,
                    processing_method="split_and_transcribe",
                    chunks_processed=len(successful_transcriptions),
                    processing_time_seconds=(datetime.now() - start_time).total_seconds(),
                    transcription_url=transcription_url,
                    webhook_delivered=None,  # Will be updated after webhook attempt
                    # Pass through parameters from request
                    drive_file_id=request.drive_file_id,
                    source_folder=request.source_folder,
                    transcription_folder=request.transcription_folder,
                    processed_folder=request.processed_folder
                )
        
        logger.info(f"Job {job_id}: ✅ Processing completed in {result.processing_time_seconds:.1f}s")
        
        # Send webhook notification with backup support
        webhook_delivered = False
        if webhook_url:
            # Log webhook URL details for debugging
            parsed_webhook = urlparse(webhook_url)
            webhook_domain = f"{parsed_webhook.scheme}://{parsed_webhook.netloc}"
            webhook_path = parsed_webhook.path
            logger.info(f"Job {job_id}: Webhook URL received - Domain: {webhook_domain}, Path: {webhook_path}")
            logger.info(f"Job {job_id}: Full webhook URL (first 100 chars): {webhook_url[:100]}{'...' if len(webhook_url) > 100 else ''}")
            logger.info(f"Job {job_id}: n8n URL pattern detected: {is_n8n_resume_url(webhook_url)}")
            logger.info(f"Job {job_id}: Attempting primary webhook delivery")
            # Disable connectivity testing for n8n webhooks to avoid HEAD request issues
            webhook_delivered = await send_webhook(webhook_url, result.dict(), test_connectivity=False)
            
            # Try backup webhook if primary fails
            if not webhook_delivered and hasattr(request, 'backup_webhook_url') and request.backup_webhook_url:
                backup_parsed = urlparse(request.backup_webhook_url)
                logger.info(f"Job {job_id}: Primary webhook failed, trying backup webhook")
                logger.info(f"Job {job_id}: Backup webhook URL - Domain: {backup_parsed.scheme}://{backup_parsed.netloc}, Path: {backup_parsed.path}")
                webhook_delivered = await send_webhook(request.backup_webhook_url, result.dict(), test_connectivity=False)
                if webhook_delivered:
                    logger.info(f"Job {job_id}: Backup webhook delivered successfully")
            
            result.webhook_delivered = webhook_delivered
            if not webhook_delivered:
                logger.warning(f"Job {job_id}: All webhook delivery attempts failed, but processing completed successfully")
                # Could add email notification here as ultimate fallback
            else:
                logger.info(f"Job {job_id}: Webhook delivered successfully")
        
    except Exception as e:
        logger.error(f"Job {job_id}: ❌ Processing failed: {str(e)}")
        
        # Send error webhook with backup support
        if webhook_url:
            error_result = {
                "job_id": job_id,
                "status": "failed",
                "error": str(e),
                "processing_time_seconds": (datetime.now() - start_time).total_seconds(),
                # Include parameters for error handling in n8n
                "drive_file_id": request.drive_file_id,
                "source_folder": request.source_folder,
                "transcription_folder": request.transcription_folder,
                "processed_folder": request.processed_folder
            }
            
            webhook_success = await send_webhook(webhook_url, error_result, test_connectivity=False)
            
            # Try backup webhook for errors too
            if not webhook_success and hasattr(request, 'backup_webhook_url') and request.backup_webhook_url:
                logger.info(f"Job {job_id}: Primary error webhook failed, trying backup")
                webhook_success = await send_webhook(request.backup_webhook_url, error_result, test_connectivity=False)
            
            if not webhook_success:
                logger.error(f"Job {job_id}: Failed to deliver error webhook notification via all methods")

async def process_chunk_with_transcription(
    chunk_index: int,
    chunk_path: str,
    job_id: str,
    chunk_duration: float,
    total_duration: float,
    api_key: str
) -> Dict:
    """Process a single chunk: upload to GCS and transcribe"""
    chunk_filename = os.path.basename(chunk_path)
    chunk_number = chunk_index + 1
    
    logger.info(f"Job {job_id}, Chunk {chunk_number}: Starting processing")
    
    try:
        # Upload to GCS
        gcs_chunk_path = f"{GCS_CHUNK_PREFIX}{job_id}/{chunk_filename}"
        signed_url = await upload_to_gcs_async(chunk_path, gcs_chunk_path)
        
        # Get chunk info
        chunk_stat = os.stat(chunk_path)
        actual_duration = min(chunk_duration, total_duration - (chunk_index * chunk_duration))
        
        chunk_info = {
            "chunk_number": chunk_number,
            "filename": chunk_filename,
            "size_mb": chunk_stat.st_size / (1024 * 1024),
            "duration_seconds": actual_duration,
            "gcs_path": f"gs://{GCS_BUCKET_NAME}/{gcs_chunk_path}",
            "download_url": signed_url
        }
        
        logger.info(f"Job {job_id}, Chunk {chunk_number}: Uploaded to GCS, starting transcription")
        
        # Transcribe immediately
        transcription = await transcribe_single_chunk_direct(chunk_path, chunk_number, actual_duration, api_key)
        
        logger.info(f"Job {job_id}, Chunk {chunk_number}: ✅ Processing complete")
        
        return {
            "chunk_info": chunk_info,
            "transcription": transcription
        }
        
    except Exception as e:
        logger.error(f"Job {job_id}, Chunk {chunk_number}: ❌ Processing failed: {str(e)}")
        return {
            "chunk_info": None,
            "transcription": None,
            "error": str(e)
        }

async def transcribe_single_chunk_direct(file_path: str, chunk_number: int, duration: float, api_key: str) -> Dict:
    """Transcribe a chunk directly from file path"""
    logger.info(f"Transcribing chunk {chunk_number} directly from file")
    start_time = datetime.now()
    
    async with aiohttp.ClientSession() as session:
        with open(file_path, 'rb') as audio_file:
            audio_data = audio_file.read()
            filename = os.path.basename(file_path)
            
            # Determine content type
            file_ext = os.path.splitext(filename.lower())[1]
            content_type = 'audio/mp4' if file_ext == '.m4a' else 'audio/mpeg'
            
            # Create form data
            data = aiohttp.FormData()
            data.add_field('file', audio_data, filename=filename, content_type=content_type)
            data.add_field('model', 'whisper-1')
            
            logger.info(f"Chunk {chunk_number}: Sending {len(audio_data)/(1024*1024):.1f}MB to OpenAI")
            
            async with session.post(
                'https://api.openai.com/v1/audio/transcriptions',
                headers={"Authorization": f"Bearer {api_key}"},
                data=data
            ) as resp:
                response_time = (datetime.now() - start_time).total_seconds()
                
                if resp.status == 200:
                    result = await resp.json()
                    logger.info(f"Chunk {chunk_number}: ✅ Transcribed in {response_time:.1f}s. Length: {len(result['text'])} chars")
                    return {
                        "chunk_number": chunk_number,
                        "text": result['text'],
                        "duration": duration
                    }
                else:
                    error_text = await resp.text()
                    logger.error(f"Chunk {chunk_number}: ❌ Transcription failed: {resp.status} - {error_text}")
                    return {
                        "chunk_number": chunk_number,
                        "text": f"[Error {resp.status}: {error_text[:100]}]",
                        "duration": duration
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

@app.get("/test-webhook")
async def test_webhook_endpoint(webhook_url: str):
    """Test webhook URL connectivity and provide diagnostics"""
    if not webhook_url:
        raise HTTPException(status_code=400, detail="webhook_url parameter is required")
    
    try:
        logger.info(f"Testing webhook connectivity for: {webhook_url}")
        result = await test_webhook_connectivity(webhook_url)
        
        # Add additional diagnostics
        result["recommendations"] = []
        
        if result["is_n8n_url"]:
            result["recommendations"].append(
                "This appears to be an n8n webhook URL. n8n resume URLs can expire, "
                "especially if the workflow execution takes too long or encounters errors."
            )
        
        if not result["reachable"]:
            result["recommendations"].extend([
                "The webhook URL is not reachable. This could be due to:",
                "- URL has expired (common with n8n resume URLs)",
                "- Network connectivity issues",
                "- The webhook service is down",
                "- Incorrect URL format"
            ])
        
        if result["status_code"] == 404:
            result["recommendations"].append(
                "404 error suggests the webhook endpoint doesn't exist or has expired. "
                "For n8n workflows, try restarting the workflow to get a fresh resume URL."
            )
        
        return result
        
    except Exception as e:
        logger.error(f"Error testing webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to test webhook: {str(e)}")

@app.post("/send-test-webhook")
async def send_test_webhook(webhook_url: str, test_message: str = "Test webhook from Audio Splitter"):
    """Send a test webhook to verify connectivity and response"""
    if not webhook_url:
        raise HTTPException(status_code=400, detail="webhook_url parameter is required")
    
    test_payload = {
        "test": True,
        "message": test_message,
        "timestamp": datetime.now().isoformat(),
        "service": "audio-splitter-drive",
        "version": "3.0.0"
    }
    
    try:
        logger.info(f"Sending test webhook to: {webhook_url}")
        success = await send_webhook(webhook_url, test_payload, max_retries=1, timeout=15)
        
        return {
            "webhook_url": webhook_url,
            "success": success,
            "message": "Test webhook sent successfully" if success else "Test webhook failed",
            "payload": test_payload
        }
        
    except Exception as e:
        logger.error(f"Error sending test webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to send test webhook: {str(e)}")

@app.post("/process-drive-file", response_model=JobStatusResponse)
async def process_drive_file(
    request: DriveFileRequest,
    background_tasks: BackgroundTasks
):
    """
    NEW ASYNC WORKFLOW:
    1. Download file and analyze
    2. Return immediate status with estimates 
    3. Process in background (split/transcribe as needed)
    4. Send webhook when complete
    """
    start_time = datetime.now()
    
    # Extract file ID
    if request.drive_file_url:
        file_id = extract_file_id_from_url(request.drive_file_url)
    elif request.drive_file_id:
        file_id = request.drive_file_id
    else:
        raise HTTPException(status_code=400, detail="Either drive_file_id or drive_file_url must be provided")
    
    job_id = f"{start_time.strftime('%Y%m%d%H%M%S')}_{file_id[:8]}"
    
    # Create persistent temp directory for background processing
    temp_dir = tempfile.mkdtemp(prefix=f"drive_split_{job_id}_")
    
    try:
        # Download from Drive
        logger.info(f"Job {job_id}: Downloading file {file_id} from Google Drive")
        temp_input = os.path.join(temp_dir, "input_audio")
        file_metadata = await download_from_drive_stream(file_id, temp_input)
        
        file_name = file_metadata['name']
        file_size_bytes = int(file_metadata['size'])
        file_size_mb = file_size_bytes / (1024 * 1024)
        
        logger.info(f"Job {job_id}: Downloaded {file_name} ({file_size_mb:.1f}MB)")
        
        # Determine processing method and estimates
        will_split = needs_splitting(temp_input, file_size_bytes, file_name)
        
        if not will_split:
            # Direct transcription
            processing_method = "direct_transcription"
            estimated_chunks = 1
            # Estimate ~2-3 seconds per MB for direct transcription
            estimated_time = int(file_size_mb * 2.5)
            message = f"File is {file_size_mb:.1f}MB and compatible - will transcribe directly"
        else:
            # Split and transcribe
            processing_method = "split_and_transcribe"
            
            # Quick analysis for estimates
            duration, bitrate, _ = get_audio_info(temp_input)
            
            # Calculate estimated chunks - match the bitrates in split_audio.py
            quality_bitrates = {'high': 128, 'medium': 64, 'low': 32}
            output_bitrate = quality_bitrates.get(request.quality, 64)
            chunk_duration = calculate_chunk_duration(bitrate, request.max_size_mb, "m4a", output_bitrate)
            estimated_chunks = max(1, int(duration / chunk_duration) + 1)
            
            # Estimate processing time: ~3s per chunk for split+transcribe
            estimated_time = int(estimated_chunks * 3 + duration * 0.1) 
            message = f"File is {file_size_mb:.1f}MB - will split into ~{estimated_chunks} chunks and transcribe"
        
        # Start background processing
        background_tasks.add_task(
            process_file_async,
            job_id,
            file_name,
            file_size_bytes,
            temp_input,
            request,
            request.webhook_url
        )
        
        # Return immediate status
        response = JobStatusResponse(
            job_id=job_id,
            status="processing",
            file_name=file_name,
            file_size_mb=file_size_mb,
            processing_method=processing_method,
            estimated_chunks=estimated_chunks,
            estimated_processing_time_seconds=estimated_time,
            message=message
        )
        
        logger.info(f"Job {job_id}: Started background processing - {processing_method}")
        return response
        
    except Exception as e:
        # Clean up temp directory on error
        import shutil
        try:
            shutil.rmtree(temp_dir)
        except:
            pass
        
        logger.error(f"Job {job_id}: Error starting processing: {str(e)}")
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
        # Generate signed URL with proper async handling
        generate_url_func = partial(
            transcription_blob.generate_signed_url,
            version="v4",
            expiration=timedelta(hours=SIGNED_URL_EXPIRY_HOURS),
            method="GET"
        )
        loop = asyncio.get_event_loop()
        transcription_url = await loop.run_in_executor(None, generate_url_func)
        
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
        # List files in folder (with shared drive support)
        query = f"'{folder_id}' in parents and mimeType contains 'audio/'"
        results = drive_service.files().list(
            q=query,
            fields="files(id, name, mimeType)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
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

async def send_webhook(webhook_url: str, data: dict, max_retries: int = 3, timeout: int = 30, test_connectivity: bool = True):
    """Send webhook notification with retry logic and comprehensive logging"""
    import time
    import json
    from urllib.parse import urlparse
    
    # Validate webhook URL
    try:
        parsed_url = urlparse(webhook_url)
        if not parsed_url.scheme or not parsed_url.netloc:
            logger.error(f"Invalid webhook URL format: {webhook_url}")
            return False
    except Exception as e:
        logger.error(f"Failed to parse webhook URL '{webhook_url}': {str(e)}")
        return False
    
    logger.info(f"Sending webhook to: {webhook_url}")
    logger.info(f"Webhook payload keys: {list(data.keys())}")
    logger.info(f"Webhook payload size: {len(json.dumps(data))} bytes")
    
    # Test connectivity first if requested
    if test_connectivity:
        logger.info("Testing webhook connectivity before sending payload...")
        connectivity_result = await test_webhook_connectivity(webhook_url)
        
        logger.info(f"Connectivity test - Reachable: {connectivity_result['reachable']}, "
                   f"Status: {connectivity_result['status_code']}, "
                   f"Response time: {connectivity_result['response_time']:.2f}s" if connectivity_result['response_time'] else "N/A")
        
        if connectivity_result['error']:
            logger.warning(f"Connectivity test warning: {connectivity_result['error']}")
        
        if connectivity_result['is_n8n_url']:
            logger.info("Detected n8n webhook URL - this may be a resume URL that could expire")
        
        # If the URL is completely unreachable, don't waste time on retries
        if not connectivity_result['reachable'] and connectivity_result['status_code'] == 404:
            logger.error("Webhook URL is unreachable (404) - skipping retry attempts")
            return False
    
    # Create timeout configuration
    timeout_config = aiohttp.ClientTimeout(total=timeout, connect=10, sock_read=10)
    
    for attempt in range(max_retries):
        start_time = time.time()
        
        try:
            async with aiohttp.ClientSession(timeout=timeout_config) as session:
                # Add custom headers for better debugging
                headers = {
                    'Content-Type': 'application/json',
                    'User-Agent': 'AudioSplitter-CloudRun/3.0.0',
                    'X-Webhook-Attempt': str(attempt + 1),
                    'X-Webhook-Max-Retries': str(max_retries)
                }
                
                logger.info(f"Webhook attempt {attempt + 1}/{max_retries} to {webhook_url}")
                
                async with session.post(
                    webhook_url, 
                    json=data, 
                    headers=headers,
                    allow_redirects=False  # Don't follow redirects to better debug URL issues
                ) as response:
                    response_time = time.time() - start_time
                    response_text = await response.text()
                    
                    logger.info(f"Webhook response: {response.status} in {response_time:.2f}s")
                    logger.info(f"Response headers: {dict(response.headers)}")
                    
                    if response.status == 200:
                        logger.info(f"✅ Webhook delivered successfully to {webhook_url} (attempt {attempt + 1})")
                        if response_text:
                            logger.info(f"Response body: {response_text[:200]}..." if len(response_text) > 200 else f"Response body: {response_text}")
                        return True
                    elif response.status == 404:
                        logger.error(f"❌ Webhook URL not found (404): {webhook_url}")
                        logger.error(f"This usually means the n8n resume URL has expired or is invalid")
                        logger.error(f"Response body: {response_text[:500]}..." if len(response_text) > 500 else f"Response body: {response_text}")
                        
                        # For 404 errors, don't retry immediately - the URL is likely expired
                        if attempt < max_retries - 1:
                            logger.info(f"Will retry webhook in case of temporary n8n issue")
                    elif response.status >= 500:
                        logger.warning(f"Server error {response.status}, will retry. Response: {response_text[:200]}..." if len(response_text) > 200 else f"Server error {response.status}, will retry. Response: {response_text}")
                    elif response.status in [301, 302, 303, 307, 308]:
                        redirect_location = response.headers.get('Location', 'Not provided')
                        logger.error(f"Webhook URL redirected ({response.status}) to: {redirect_location}")
                        logger.error(f"Original URL: {webhook_url}")
                    else:
                        logger.error(f"Webhook failed with status {response.status}: {response_text[:200]}..." if len(response_text) > 200 else f"Webhook failed with status {response.status}: {response_text}")
                        
        except asyncio.TimeoutError:
            logger.error(f"Webhook timeout after {timeout}s (attempt {attempt + 1})")
        except aiohttp.ClientConnectorError as e:
            logger.error(f"Webhook connection error (attempt {attempt + 1}): {str(e)}")
            logger.error(f"This could indicate DNS issues or network connectivity problems")
        except aiohttp.ClientError as e:
            logger.error(f"Webhook client error (attempt {attempt + 1}): {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected webhook error (attempt {attempt + 1}): {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
        
        # Exponential backoff for retries
        if attempt < max_retries - 1:
            backoff_delay = min(2 ** attempt, 30)  # Cap at 30 seconds
            logger.info(f"Retrying webhook in {backoff_delay} seconds...")
            await asyncio.sleep(backoff_delay)
    
    logger.error(f"❌ All webhook attempts failed after {max_retries} tries to {webhook_url}")
    return False

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