# Urgent Timeout Fix for Chunk Processing

## Problem
The audio splitter is timing out when processing large files (87+ minutes) that create 36 chunks, even with the 60-minute Cloud Run timeout.

## Root Cause
1. Sequential processing: Chunks are created first, THEN transcribed
2. Only 6 workers for parallel processing when we have 8 CPUs
3. No streaming/progressive processing of chunks

## Immediate Fixes Applied

### 1. Cloud Run Timeout Increased
- ✅ Increased from 600s (10 min) to 3600s (60 min) - the maximum allowed
- This gives more time but doesn't solve the root issue

### 2. Code Optimizations Already Applied
- ✅ Reduced WAV chunks to 5MB (from 10MB)
- ✅ Added FFmpeg multi-threading
- ✅ Increased OpenAI timeouts to 600s
- ✅ Added retry logic with exponential backoff
- ✅ Connection pooling for API calls

## Recommended Solutions

### Option 1: Increase Worker Count (Quick Fix)
Change line 698 in `audio_splitter_drive.py`:
```python
# From:
6        # max_workers - use 6 on our 8-CPU instance

# To:
8        # max_workers - use all 8 CPUs
```

### Option 2: Stream Processing (Better Solution)
Modify the processing to transcribe chunks as they're created:
1. Create chunks 1-4 → Start transcribing them
2. While transcribing, create chunks 5-8
3. Continue this pattern

### Option 3: Async Job Processing (Best Solution)
For files > 30 minutes:
1. Return job ID immediately
2. Process in background
3. Send results via webhook when complete

## Current Workarounds

For immediate use:
1. **Split large files manually** before processing
2. **Process in batches** - upload 30-minute segments
3. **Use direct file upload** instead of Google Drive for faster processing

## Testing
The service is now configured with:
- 60-minute timeout (maximum)
- All optimization fixes deployed
- Health check: https://audio-splitter-ey3mdkeuya-uc.a.run.app/

For files that still timeout, implement Option 3 (async processing) as the permanent solution.