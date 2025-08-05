#!/usr/bin/env python3
"""
Simplified Google Drive to AssemblyAI transcription service.
This service is dramatically simpler than the original because AssemblyAI handles:
- Direct URL transcription (no download needed)
- Files up to 5GB (no chunking needed)
- Webhook delivery (no polling needed)
- Automatic retries (no complex error handling)
"""

import os
import logging
import uuid
import io
from typing import Optional, Dict, Tuple
from urllib.parse import urlencode, urlparse, urlunparse
from datetime import datetime, timedelta

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload
from google.cloud import storage

# Add parent directory to path for imports
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import transcription module with proper path handling
try:
    from src.transcription import TranscriptionFactory, TranscriptionError
except ImportError:
    # For running from different directories
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from transcription import TranscriptionFactory, TranscriptionError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Google Drive configuration
SERVICE_ACCOUNT_FILE = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "config/service-account-key.json")
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

# AssemblyAI configuration
ASSEMBLYAI_API_KEY = os.environ.get("ASSEMBLYAI_API_KEY")

# Google Cloud Storage configuration
GCS_BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME", "audio-splitter-uploads")
GCS_TEMP_PREFIX = "temp-audio/"  # Temporary files location
GCS_SIGNED_URL_EXPIRY_HOURS = 1.0  # 1 hour expiry for temporary files

# Streaming configuration
STREAM_CHUNK_SIZE = 10 * 1024 * 1024  # 10MB chunks for streaming

app = FastAPI(
    title="Audio Transcriber - AssemblyAI Service",
    description="Simplified service that sends Google Drive audio files to AssemblyAI for transcription",
    version="1.0.0"
)


class AssemblyAIRequest(BaseModel):
    """Request to transcribe a Google Drive file using AssemblyAI"""
    drive_file_id: Optional[str] = Field(None, description="Google Drive file ID")
    drive_file_url: Optional[str] = Field(None, description="Alternative: Google Drive shareable link")
    file_name: Optional[str] = Field(None, description="Original file name")
    webhook_url: str = Field(..., description="Webhook URL for transcription results (required)")
    
    # AssemblyAI specific options
    model: Optional[str] = Field(default="universal", description="AssemblyAI model: slam-1, universal")
    language: Optional[str] = Field(None, description="Language code (e.g., 'en'). Required for slam-1")
    prompt: Optional[str] = Field(None, description="Custom prompt for slam-1 model")
    speaker_diarization: Optional[bool] = Field(default=True, description="Enable speaker diarization")
    
    # Folder organization parameters (passed through to webhook)
    source_folder: Optional[str] = Field(None, description="Source folder name/ID for organization")
    transcription_folder: Optional[str] = Field(None, description="Target folder for transcription files")
    processed_folder: Optional[str] = Field(None, description="Target folder for processed source files")
    
    def model_post_init(self, __context) -> None:
        if not self.drive_file_id and not self.drive_file_url:
            raise ValueError("Either drive_file_id or drive_file_url must be provided")


class TranscriptionResponse(BaseModel):
    """Response from the transcription service"""
    job_id: str
    transcript_id: str
    status: str
    message: str
    webhook_url: str
    estimated_duration_seconds: Optional[float] = None


def extract_file_id_from_url(url: str) -> str:
    """Extract file ID from Google Drive URL"""
    if '/file/d/' in url:
        # https://drive.google.com/file/d/FILE_ID/view
        return url.split('/file/d/')[1].split('/')[0]
    elif 'id=' in url:
        # https://drive.google.com/open?id=FILE_ID
        return url.split('id=')[1].split('&')[0]
    else:
        return url  # Assume it's already a file ID


def get_drive_service():
    """Initialize Google Drive service"""
    try:
        if os.path.exists(SERVICE_ACCOUNT_FILE):
            credentials = service_account.Credentials.from_service_account_file(
                SERVICE_ACCOUNT_FILE, scopes=SCOPES
            )
        else:
            # Use default credentials in Cloud Run
            from google.auth import default
            credentials, _ = default(scopes=SCOPES)
        
        return build('drive', 'v3', credentials=credentials)
    except Exception as e:
        logger.error(f"Failed to initialize Drive service: {e}")
        raise


def get_drive_download_url(drive_service, file_id: str) -> tuple[str, str]:
    """
    Get direct download URL and file name from Google Drive
    Returns: (download_url, file_name)
    """
    try:
        # Get file metadata
        file_metadata = drive_service.files().get(
            fileId=file_id,
            fields="id,name,mimeType,size",
            supportsAllDrives=True
        ).execute()
        
        file_name = file_metadata.get('name', 'unknown')
        file_size = int(file_metadata.get('size', 0))
        mime_type = file_metadata.get('mimeType', '')
        
        logger.info(f"File info: {file_name}, {file_size / (1024*1024):.1f} MB, {mime_type}")
        
        # Build download URL
        download_url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"
        
        # For large files or specific mime types, we might need export URL
        if mime_type.startswith('application/vnd.google-apps'):
            # Google Docs/Sheets/etc need export
            raise HTTPException(
                status_code=400,
                detail=f"Google Workspace files cannot be transcribed directly. Please export to audio format first."
            )
        
        return download_url, file_name
        
    except HttpError as e:
        if e.resp.status == 404:
            raise HTTPException(status_code=404, detail="File not found in Google Drive")
        elif e.resp.status == 403:
            raise HTTPException(status_code=403, detail="No permission to access this file")
        else:
            raise HTTPException(status_code=500, detail=f"Google Drive error: {str(e)}")


def build_webhook_with_metadata(webhook_url: str, metadata: Dict[str, str]) -> str:
    """
    Add metadata as query parameters to webhook URL
    This allows AssemblyAI to pass our custom data back to n8n
    """
    # Parse the URL
    parsed = urlparse(webhook_url)
    
    # Build query parameters from metadata
    # Filter out None values
    clean_metadata = {k: v for k, v in metadata.items() if v is not None}
    query_params = urlencode(clean_metadata)
    
    # Combine with existing query params if any
    if parsed.query:
        query_params = f"{parsed.query}&{query_params}"
    
    # Rebuild URL with metadata
    return urlunparse(parsed._replace(query=query_params))


def generate_job_id() -> str:
    """Generate a unique job ID"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"aai_{timestamp}_{uuid.uuid4().hex[:8]}"


def get_gcs_client():
    """Get authenticated GCS client"""
    if os.path.exists(SERVICE_ACCOUNT_FILE):
        return storage.Client.from_service_account_json(SERVICE_ACCOUNT_FILE)
    else:
        # Use default credentials in Cloud Run
        return storage.Client()


async def transfer_drive_to_gcs_streaming(
    drive_service, 
    file_id: str, 
    file_name: str,
    job_id: str
) -> Tuple[str, str]:
    """
    Stream file from Google Drive to GCS without loading entire file into memory
    Returns: (gcs_path, signed_url)
    """
    logger.info(f"Job {job_id}: Starting streaming transfer from Drive to GCS")
    
    try:
        # Initialize GCS
        gcs_client = get_gcs_client()
        bucket = gcs_client.bucket(GCS_BUCKET_NAME)
        
        # Create GCS path
        safe_filename = file_name.replace('/', '_').replace('\\', '_')
        gcs_path = f"{GCS_TEMP_PREFIX}{job_id}/{safe_filename}"
        blob = bucket.blob(gcs_path)
        
        # Get file metadata for size
        file_metadata = drive_service.files().get(
            fileId=file_id,
            fields="size",
            supportsAllDrives=True
        ).execute()
        file_size = int(file_metadata.get('size', 0))
        logger.info(f"Job {job_id}: File size: {file_size / (1024*1024):.1f} MB")
        
        # Create Drive download request
        request = drive_service.files().get_media(fileId=file_id, supportsAllDrives=True)
        
        # Stream from Drive to GCS
        with blob.open('wb') as gcs_stream:
            downloader = MediaIoBaseDownload(gcs_stream, request, chunksize=STREAM_CHUNK_SIZE)
            
            done = False
            bytes_downloaded = 0
            while not done:
                status, done = downloader.next_chunk()
                if status:
                    bytes_downloaded = status.resumable_progress
                    progress = (bytes_downloaded / file_size) * 100 if file_size > 0 else 0
                    logger.info(f"Job {job_id}: Transfer progress: {progress:.1f}%")
        
        logger.info(f"Job {job_id}: Transfer complete. File uploaded to: {gcs_path}")
        
        # Generate signed URL with 1-hour expiry
        signed_url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(hours=GCS_SIGNED_URL_EXPIRY_HOURS),
            method="GET"
        )
        
        logger.info(f"Job {job_id}: Generated signed URL (expires in {GCS_SIGNED_URL_EXPIRY_HOURS} hour)")
        
        return gcs_path, signed_url
        
    except Exception as e:
        logger.error(f"Job {job_id}: Error during Drive to GCS transfer: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to transfer file to temporary storage: {str(e)}"
        )


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "audio-transcriber-assemblyai",
        "timestamp": datetime.now().isoformat()
    }


@app.post("/transcribe-assemblyai", response_model=TranscriptionResponse)
async def transcribe_with_assemblyai(request: AssemblyAIRequest):
    """
    Simplified transcription endpoint that leverages AssemblyAI's capabilities:
    1. Get Google Drive download URL
    2. Send to AssemblyAI with webhook
    3. Return immediately (AssemblyAI handles everything else)
    """
    job_id = generate_job_id()
    logger.info(f"Job {job_id}: Starting AssemblyAI transcription")
    
    try:
        # Extract file ID
        file_id = request.drive_file_id
        if not file_id and request.drive_file_url:
            file_id = extract_file_id_from_url(request.drive_file_url)
        
        logger.info(f"Job {job_id}: Processing file ID: {file_id}")
        
        # Get file info from Google Drive
        drive_service = get_drive_service()
        _, file_name = get_drive_download_url(drive_service, file_id)
        
        # Use provided file name if available, otherwise use Drive name
        final_file_name = request.file_name or file_name
        
        logger.info(f"Job {job_id}: File name: {final_file_name}")
        
        # Transfer file from Drive to GCS with streaming
        logger.info(f"Job {job_id}: Transferring file to temporary storage...")
        gcs_path, signed_url = await transfer_drive_to_gcs_streaming(
            drive_service, file_id, final_file_name, job_id
        )
        
        # Build webhook URL with metadata
        metadata = {
            "job_id": job_id,
            "drive_file_id": file_id,
            "file_name": final_file_name,
            "source_folder": request.source_folder,
            "transcription_folder": request.transcription_folder,
            "processed_folder": request.processed_folder,
            "gcs_temp_path": gcs_path,  # Add GCS path for potential cleanup tracking
        }
        
        webhook_with_metadata = build_webhook_with_metadata(request.webhook_url, metadata)
        logger.info(f"Job {job_id}: Webhook URL with metadata: {webhook_with_metadata}")
        
        # Create AssemblyAI provider
        if not ASSEMBLYAI_API_KEY:
            raise HTTPException(
                status_code=500,
                detail="AssemblyAI API key not configured"
            )
        
        provider = TranscriptionFactory.create_provider(
            'assemblyai',
            api_key=ASSEMBLYAI_API_KEY,
            model=request.model
        )
        
        # Create transcription job with AssemblyAI using the signed URL
        # Note: We use the internal method to get the transcript ID
        transcript_config = {
            'model': request.model,
            'language': request.language,
            'prompt': request.prompt,
            'speaker_diarization': request.speaker_diarization,
            'webhook_url': webhook_with_metadata,
        }
        
        # Remove None values
        transcript_config = {k: v for k, v in transcript_config.items() if v is not None}
        
        logger.info(f"Job {job_id}: Creating AssemblyAI transcript with config: {transcript_config}")
        
        # Create transcript job with the GCS signed URL
        transcript_id = await provider._create_transcript(signed_url, **transcript_config)
        
        logger.info(f"Job {job_id}: AssemblyAI transcript created: {transcript_id}")
        
        # Return immediately - AssemblyAI will handle the rest
        return TranscriptionResponse(
            job_id=job_id,
            transcript_id=transcript_id,
            status="processing",
            message="Transcription job created. Results will be sent to webhook when complete.",
            webhook_url=webhook_with_metadata
        )
        
    except TranscriptionError as e:
        logger.error(f"Job {job_id}: Transcription error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Job {job_id}: Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@app.get("/job/{job_id}/status")
async def get_job_status(job_id: str, transcript_id: Optional[str] = None):
    """
    Check the status of a transcription job
    Note: With AssemblyAI webhooks, this is optional since results go directly to n8n
    """
    if not transcript_id:
        return {
            "job_id": job_id,
            "status": "unknown",
            "message": "Transcript ID required to check status"
        }
    
    try:
        provider = TranscriptionFactory.create_provider(
            'assemblyai',
            api_key=ASSEMBLYAI_API_KEY
        )
        
        # Poll transcript status
        result = await provider._poll_transcript(transcript_id)
        
        return {
            "job_id": job_id,
            "transcript_id": transcript_id,
            "status": result.get('status'),
            "duration_seconds": result.get('audio_duration', 0) / 1000.0,
            "language": result.get('language_code'),
            "confidence": result.get('confidence'),
            "message": "Transcription completed" if result.get('status') == 'completed' else "Processing"
        }
        
    except Exception as e:
        logger.error(f"Error checking status: {str(e)}")
        return {
            "job_id": job_id,
            "transcript_id": transcript_id,
            "status": "error",
            "message": str(e)
        }


@app.get("/test-webhook")
async def test_webhook():
    """Test endpoint to verify webhook functionality"""
    test_metadata = {
        "job_id": "test_123",
        "drive_file_id": "abc123",
        "file_name": "test_audio.mp3",
        "source_folder": "folder1",
        "transcription_folder": "folder2",
        "processed_folder": "folder3"
    }
    
    test_webhook_url = "https://example.com/webhook/test"
    webhook_with_metadata = build_webhook_with_metadata(test_webhook_url, test_metadata)
    
    return {
        "original_webhook": test_webhook_url,
        "webhook_with_metadata": webhook_with_metadata,
        "metadata": test_metadata,
        "message": "This shows how metadata is appended to the webhook URL"
    }


if __name__ == "__main__":
    # For local development
    uvicorn.run(app, host="0.0.0.0", port=8080)