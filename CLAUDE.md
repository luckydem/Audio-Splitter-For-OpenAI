# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with this repository.

## Project Overview

DriveScribe is a Google Cloud Run audio transcription system with two services:
1. **AssemblyAI Service** (recommended): Direct WMA file processing, 90% simpler
2. **Whisper Service** (legacy): Complex chunking with FFmpeg for OpenAI API

## 🏗️ Current Architecture

### Active Service: AssemblyAI Transcriber
- **Location**: `services/assemblyai-transcriber/`
- **Main file**: `audio_transcriber_assemblyai.py`
- **Deployed as**: `audio-transcriber-assemblyai` on Cloud Run
- **URL**: https://audio-transcriber-assemblyai-453383149276.us-central1.run.app

### Legacy Service: Whisper Chunking
- **Location**: `services/whisper-chunking/`
- **Main file**: `audio_splitter_drive.py`
- **Status**: Available but not deployed
- **Use case**: When chunking is specifically needed

## 🔑 Key Technical Details

### Service Account
- **Single account used by both services**: `audio-splitter-drive@duhworks.iam.gserviceaccount.com`
- **Key location**: `config/service-account-key.json`
- **Permissions**: Google Drive access, GCS access, signed URL generation
- **Shared drives**: Enabled with `supportsAllDrives=True`

### AssemblyAI Integration
- **API Endpoint**: `https://api.assemblyai.com/v2/transcript` (singular, not plural)
- **Authentication**: `Authorization: Bearer {32-char-api-key}`
- **File handling**: Streams Drive → GCS → AssemblyAI (no memory limits)
- **Temporary storage**: GCS with 1-hour signed URLs, 1-day cleanup

### Important API Details
- **Webhook metadata**: Passed via URL query parameters
- **Models available**: `universal`, `slam-1`, `conformer-2`
- **File limits**: 5GB max, no duration limit
- **Format support**: Native WMA support (no conversion needed)

## 🛠️ Development Commands

### Deploy AssemblyAI Service
```bash
cd services/assemblyai-transcriber
./deploy.sh
```

### Deploy Whisper Service (if needed)
```bash
cd services/whisper-chunking
./deploy.sh
```

### Monitor Logs
```bash
gcloud run services logs read audio-transcriber-assemblyai --region us-central1 --limit 50
```

### Check Service Status
```bash
curl https://audio-transcriber-assemblyai-453383149276.us-central1.run.app/health
```

## 🔧 Configuration Management

### Environment Variables (Cloud Run)
- `ASSEMBLYAI_API_KEY`: 32-character API key
- `GCS_BUCKET_NAME`: "audio-splitter-uploads"
- `GOOGLE_APPLICATION_CREDENTIALS`: "config/service-account-key.json"

### GCS Configuration
- **Bucket**: `audio-splitter-uploads`
- **Temp path**: `temp-audio/{job_id}/{filename}`
- **URL expiry**: 1 hour (enforced by signed URLs)
- **Cleanup**: 1 day lifecycle rule (daily granularity minimum)

## 📊 n8n Integration Pattern

### HTTP Request to Start Transcription
```json
{
  "method": "POST",
  "url": "https://audio-transcriber-assemblyai-453383149276.us-central1.run.app/transcribe-assemblyai",
  "body": {
    "drive_file_id": "{{ $json.id }}",
    "webhook_url": "https://n8n.e-bud.app/webhook/split-and-transcribe-completed",
    "file_name": "{{ $json.file_name }}",
    "model": "slam-1",
    "source_folder": "{{ $json.source_folder }}",
    "transcription_folder": "{{ $json.transcription_folder }}",
    "processed_folder": "{{ $json.processed_folder }}"
  }
}
```

### HTTP Request to Get Transcript
```json
{
  "method": "GET", 
  "url": "https://api.assemblyai.com/v2/transcript/{{ $json.body.transcript_id }}",
  "headers": {
    "Authorization": "Bearer {{ $vars.ASSEMBLYAI_API_KEY }}"
  }
}
```

## 🚨 Common Issues & Solutions

### 1. AssemblyAI 404 Errors
- **Problem**: Wrong API endpoint or headers
- **Solution**: Use `/transcript` (singular) with `Authorization: Bearer {key}`

### 2. Google Drive Access Denied
- **Problem**: Service account not shared with Drive files
- **Solution**: Share folders with `audio-splitter-drive@duhworks.iam.gserviceaccount.com`

### 3. Signed URL Generation Fails
- **Problem**: Missing private key for service account
- **Solution**: Ensure `config/service-account-key.json` is in Docker container

### 4. File Not Found in Shared Drives
- **Problem**: Missing `supportsAllDrives=True` parameter
- **Solution**: All Drive API calls include this parameter

## 📁 Code Organization

### Provider Abstraction (`services/assemblyai-transcriber/transcription/`)
- `base.py`: Abstract transcription provider interface
- `assemblyai_provider.py`: AssemblyAI implementation
- `openai_provider.py`: OpenAI implementation (for reference)
- `factory.py`: Provider factory pattern
- `config.py`: Configuration management

### Main Service (`services/assemblyai-transcriber/`)
- `audio_transcriber_assemblyai.py`: FastAPI service with endpoints
- `Dockerfile`: Lightweight container (no FFmpeg)
- `requirements.txt`: Minimal dependencies
- `deploy.sh`: Cloud Run deployment script

## 🔍 Debugging & Monitoring

### Log Analysis
```bash
# Recent errors
gcloud run services logs read audio-transcriber-assemblyai --region us-central1 --limit 50 | grep -i error

# Specific job tracking
gcloud run services logs read audio-transcriber-assemblyai --region us-central1 --limit 50 | grep "Job aai_"

# Performance monitoring
gcloud run services logs read audio-transcriber-assemblyai --region us-central1 --limit 50 | grep "Transfer progress"
```

### Health Checks
- **Service health**: `curl {service-url}/health`
- **Webhook test**: `curl {service-url}/test-webhook`
- **AssemblyAI API**: `curl -H "Authorization: Bearer {key}" https://api.assemblyai.com/v2/transcript/{id}`

## 🎯 Performance Characteristics

### AssemblyAI Service
- **Memory**: 512MB (vs 8GB for Whisper service)
- **CPU**: 1 vCPU (vs 8 for Whisper service)
- **Timeout**: 5 minutes (vs 60 minutes for Whisper service)
- **Processing**: 2-4 minutes for 2-hour file
- **Complexity**: ~300 lines of code vs ~1500 for Whisper service

### Cost Comparison (2-hour file)
- **AssemblyAI**: $1.30 transcription + minimal compute costs
- **Whisper**: $0.72 transcription + significant compute costs for chunking

## 📋 Deployment Checklist

When deploying or updating services:

1. ✅ Check service account permissions
2. ✅ Verify environment variables are set
3. ✅ Confirm GCS bucket exists and has lifecycle rules
4. ✅ Test with health endpoint
5. ✅ Verify webhook metadata pass-through
6. ✅ Test with actual Drive file
7. ✅ Monitor logs for first few transcriptions

## 🔄 Git Branch Strategy

- **Main branch**: `master`
- **Feature branch**: `feature/assemblyai-integration` (current)
- **Deployment**: Always deploy from committed code
- **Rollback**: Keep previous service versions available in Cloud Run

## 🚀 Future Enhancements

### Potential Improvements
- Add speaker diarization options
- Implement automatic summaries
- Add PII redaction capabilities
- Create unified API supporting both providers
- Add cost optimization features

### Architecture Evolution
- Consider separating webhook handler into separate service
- Add job queue for very large files
- Implement circuit breaker patterns for reliability

## 🔮 Planned Migration (Priority Task)

### Project Migration to DriveScribe
**Status**: Planned for next development session
**Goal**: Move from `duhworks` to dedicated `drivescribe` project

#### Key Changes:
- **Project ID**: `duhworks` → `drivescribe`
- **Service Account**: `audio-splitter-drive@duhworks.iam.gserviceaccount.com` → `transcribe@drivescribe.iam.gserviceaccount.com`  
- **GCS Bucket**: `audio-splitter-uploads` → `drivescribe-audio-temp`
- **Services**: Clean deployment in dedicated project

#### Impact on Development:
- All deployment scripts need PROJECT_ID updates
- New service account key will be required
- GCS configuration changes in both services
- n8n webhook URLs will change
- Documentation updates required

#### Migration Priority:
1. **Create new GCP project** and enable APIs
2. **Set up service account** with proper permissions
3. **Update deployment scripts** for both services
4. **Test migration** with non-production workflows
5. **Coordinate with n8n** for webhook URL updates
6. **Full end-to-end testing** before switching production

**⚠️ Remember**: Keep old services running during migration for rollback safety.

---

## 🤖 Claude Code Instructions

### When helping with this project:

1. **Always check current deployment status** before making changes
2. **Use the gcp-cloudrun-diagnostician agent** for Cloud Run issues
3. **Prefer the AssemblyAI service** for new features unless chunking is specifically needed
4. **Remember the service account consolidation** - both services use the same account
5. **Check logs proactively** when testing changes
6. **Use TodoWrite tool** for complex multi-step tasks
7. **Focus on the active service** (AssemblyAI) unless explicitly asked about Whisper

### Common Commands You'll Need
```bash
# Deploy AssemblyAI service
cd services/assemblyai-transcriber && ./deploy.sh

# Check logs
gcloud run services logs read audio-transcriber-assemblyai --region us-central1 --limit 50

# Test service
curl https://audio-transcriber-assemblyai-453383149276.us-central1.run.app/health

# Monitor specific job
gcloud run services logs read audio-transcriber-assemblyai --region us-central1 --limit 50 | grep "Job aai_YYYYMMDD"
```

Remember: The project is now clean, organized, and production-ready. Focus on the AssemblyAI service unless there's a specific need for the Whisper chunking approach.