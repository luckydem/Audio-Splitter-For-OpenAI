# Cloud Run Timeout Fix Implementation Summary

## Date: 2025-08-04

## Overview
This document summarizes the high-priority fixes implemented to address network timeout issues and FFmpeg processing failures in the Cloud Run audio splitting service.

## Issues Addressed

### 1. OpenAI API Timeouts
- **Problem**: `TimeoutError('The write operation timed out')` when uploading chunks to OpenAI
- **Root Cause**: 5-minute timeout was insufficient for large audio chunks

### 2. FFmpeg Processing Timeouts  
- **Problem**: FFmpeg operations timing out after 300 seconds
- **Root Cause**: Large WAV files taking too long to process

### 3. Network Connection Issues
- **Problem**: Intermittent connection failures
- **Root Cause**: No connection pooling or retry logic

## Implemented Solutions

### 1. Enhanced Timeout Configuration (`audio_splitter_drive.py`)

#### Added Configuration Constants:
```python
OPENAI_API_TIMEOUT = 600  # 10 minutes to match Cloud Run timeout
OPENAI_CONNECT_TIMEOUT = 30  # 30 seconds to establish connection
OPENAI_READ_TIMEOUT = 300  # 5 minutes to read response
FFMPEG_TIMEOUT = 600  # 10 minutes for FFmpeg operations
```

#### Connection Pool Configuration:
```python
CONNECTION_LIMIT = 10
CONNECTION_LIMIT_PER_HOST = 5
```

#### Format-Specific Chunk Size Limits:
```python
CHUNK_SIZE_LIMITS = {
    'wav': 5,    # Reduced from 10MB to 5MB for faster processing
    'm4a': 20,   # Keep at 20MB for m4a
    'mp3': 20,   # Keep at 20MB for mp3
    'default': 10
}
```

### 2. Retry Logic with Exponential Backoff

#### Implemented `with_retry` Decorator:
- 5 retry attempts with delays: [2s, 4s, 8s, 16s, 32s]
- 10% jitter added to prevent thundering herd
- Special handling for rate limits (429 status)
- Retries on network errors and timeouts
- Applied to all OpenAI API calls

### 3. Connection Pooling

#### Added to All OpenAI API Sessions:
```python
connector = aiohttp.TCPConnector(
    limit=CONNECTION_LIMIT,
    limit_per_host=CONNECTION_LIMIT_PER_HOST,
    force_close=True  # Force close connections to avoid hanging
)
```

### 4. FFmpeg Optimizations (`split_audio.py`)

#### Added Threading Support:
```python
FFMPEG_THREADS = 2  # Use 2 threads for encoding
```

#### Updated All FFmpeg Commands:
- Added `-threads 2` flag to all format encoders
- Increased timeout from 300s to 600s
- Optimized for multi-core processing

## Modified Functions

### `audio_splitter_drive.py`:
1. `transcribe_chunks_parallel()` - Added connection pooling and increased timeouts
2. `transcribe_single_chunk()` - Added @with_retry decorator
3. `transcribe_single_chunk_direct()` - Added @with_retry decorator and connection pooling
4. `transcribe_file_directly()` - Added @with_retry decorator and connection pooling
5. `process_file_async()` - Updated to use format-specific chunk size limits

### `split_audio.py`:
1. Updated all FFmpeg commands to use threading
2. Increased all subprocess timeouts to 600s
3. Added configuration constants

## Testing Status
- Syntax validation: ✅ Passed
- Import validation: ✅ Passed
- Backup created: ✅ `audio_splitter_drive_backup.py`

## Deployment Instructions

1. Deploy the updated code to Cloud Run:
   ```bash
   ./deployment/deploy.sh
   ```

2. Monitor the logs after deployment:
   ```bash
   gcloud logging tail --filter="resource.type=cloud_run_revision AND resource.labels.service_name=audio-splitter" --format="value(timestamp,jsonPayload.message)"
   ```

3. Test with a problematic file to verify fixes

## Expected Improvements

1. **Reduced Timeout Errors**: 10-minute timeouts should handle large files
2. **Better Recovery**: Retry logic will handle transient network issues
3. **Faster Processing**: 
   - WAV chunks reduced to 5MB
   - FFmpeg multi-threading enabled
4. **More Stable Connections**: Connection pooling prevents hanging connections

## Monitoring Recommendations

1. Track metrics:
   - OpenAI API response times
   - Retry attempt frequency
   - FFmpeg processing duration by format
   
2. Set alerts for:
   - Error rate > 10% over 5 minutes
   - Average processing time > 5 minutes
   - Repeated timeout errors

## Next Steps (Medium Priority)

1. Implement circuit breaker pattern
2. Add comprehensive monitoring with OpenTelemetry
3. Optimize Cloud Run scaling configuration
4. Consider implementing a job queue for long-running tasks