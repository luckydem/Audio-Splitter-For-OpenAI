# n8n Workflows

This directory contains n8n workflow definitions for automated audio transcription processing.

## Current Workflow

### `audio_transcription_workflow_v2.json`

**Latest workflow for the asynchronous Cloud Run API (v3.0)**

**Features:**
- ✅ Single API call for complete processing
- ✅ Automatic smart file processing (direct transcription for small files, splitting for large files)
- ✅ Asynchronous background processing with webhook completion
- ✅ Detailed job status and time estimates
- ✅ Comprehensive transcription metadata

**Workflow Steps:**
1. **Google Drive Trigger** - Monitors folder for new audio files
2. **Process & Transcribe Audio** - Sends file to Cloud Run API with OpenAI key
3. **Store Job Info** - Preserves job details and estimates
4. **Wait for Transcription** - Waits for webhook completion notification
5. **Format Transcription** - Formats transcript with metadata
6. **Upload Transcription to Drive** - Saves formatted transcript to Google Drive
7. **Move to Processed Folder** - Archives original audio file

**Performance:**
- Small files (≤25MB): Direct transcription (~70% faster)
- Large files: Parallel chunk processing (~50% faster)
- Non-blocking: n8n can process multiple files simultaneously

## Setup Instructions

1. **Import the workflow** into your n8n instance
2. **Update credentials** for Google Drive OAuth2 API
3. **Configure folder IDs**:
   - Monitor folder: `1VK53SB0fOp7cqfbOrILlQPFsbQEahW68` 
   - Output folder: `1Yei83415nIxPGK1g4IGzMH_Zxfs5rkhh`
   - Processed folder: Replace `YOUR_PROCESSED_FOLDER_ID`
4. **Update API key** in the "Process & Transcribe Audio" node
5. **Test** with a small audio file

## API Response Format

**Initial Response:**
```json
{
  "job_id": "20250804073015_1DHzzYcN",
  "status": "processing",
  "file_name": "meeting.m4a",
  "file_size_mb": 15.2,
  "processing_method": "direct_transcription",
  "estimated_chunks": 1,
  "estimated_processing_time_seconds": 38,
  "message": "File is 15.2MB and compatible - will transcribe directly"
}
```

**Webhook Completion:**
```json
{
  "job_id": "20250804073015_1DHzzYcN",
  "status": "completed",
  "file_name": "meeting.m4a", 
  "transcription_text": "Full transcription text...",
  "total_duration_seconds": 720,
  "processing_method": "direct_transcription",
  "chunks_processed": 1,
  "processing_time_seconds": 15.2,
  "transcription_url": "https://storage.googleapis.com/..."
}
```

## Migration from v1

**Removed components:**
- ❌ Two-step process (process → transcribe)
- ❌ Manual chunk handling in n8n
- ❌ Parser JavaScript files
- ❌ Transcription merging logic

**New benefits:**
- ✅ 50-70% faster processing
- ✅ Automatic error handling
- ✅ Better logging and monitoring
- ✅ Simplified workflow management

## Troubleshooting

1. **Webhook timeouts**: Check Cloud Run logs for processing status
2. **API key issues**: Verify OpenAI API key has sufficient credits
3. **Permission errors**: Ensure service account has access to shared drives
4. **Large files**: Monitor processing time estimates and bucket storage

For detailed configuration options, see the main [README.md](../README.md#storage-configuration--retention).