# DriveScribe - Audio Transcription Services

A Google Cloud Run audio transcription system with two distinct services: a complex Whisper API service with chunking, and a simplified AssemblyAI service for direct file processing.

## 🚀 Quick Start

**AssemblyAI Service (Recommended):**
```bash
cd services/assemblyai-transcriber
./deploy.sh
```

**Test the service:**
```bash
curl https://audio-transcriber-assemblyai-[hash].us-central1.run.app/health
```

## 📁 Project Structure

```
DriveScribe/
├── services/
│   ├── whisper-chunking/           # Complex service with FFmpeg + chunking
│   │   ├── audio_splitter_drive.py # OpenAI Whisper with 25MB chunking
│   │   ├── split_audio.py          # FFmpeg audio processing
│   │   └── deploy.sh               # Deploy: 8GB RAM, 8 CPU
│   └── assemblyai-transcriber/     # Simple service (90% less code)
│       ├── audio_transcriber_assemblyai.py  # Direct AssemblyAI integration
│       ├── transcription/          # Provider abstraction layer
│       └── deploy.sh               # Deploy: 512MB RAM, 1 CPU
├── config/
│   └── service-account-key.json    # Shared: audio-splitter-drive@duhworks
└── .claude/
    └── agents                      # Claude Code agent configurations
```

## 🎯 Service Comparison

| Feature | Whisper Chunking | AssemblyAI |
|---------|------------------|------------|
| **File Size Limit** | 25MB (chunked) | 5GB direct |
| **WMA Support** | ❌ (converts via FFmpeg) | ✅ Native |
| **Processing** | Complex chunking + merging | Single API call |
| **Cost per hour** | $0.36 | $0.65 |
| **Memory Usage** | 8GB | 512MB |
| **Dependencies** | FFmpeg, Python, heavy | Python only, lightweight |
| **Speed** | 10-15 min for 2hr file | 2-4 min for 2hr file |

## 🔧 n8n Integration

### AssemblyAI HTTP Request Node:
```json
{
  "drive_file_id": "{{ $json.id }}",
  "webhook_url": "https://n8n.e-bud.app/webhook/split-and-transcribe-completed",
  "file_name": "{{ $json.file_name }}",
  "model": "slam-1",
  "source_folder": "{{ $json.source_folder }}",
  "transcription_folder": "{{ $json.transcription_folder }}",
  "processed_folder": "{{ $json.processed_folder }}"
}
```

### Retrieve Transcript:
```json
{
  "method": "GET",
  "url": "https://api.assemblyai.com/v2/transcript/{{ $json.body.transcript_id }}",
  "headers": {
    "Authorization": "Bearer {{ $vars.ASSEMBLYAI_API_KEY }}"
  }
}
```

## 🏗️ Architecture

### AssemblyAI Service Flow:
1. **n8n** → HTTP POST to Cloud Run service
2. **Cloud Run** → Stream file from Google Drive to GCS temporary storage
3. **Cloud Run** → Generate 1-hour signed URL for file
4. **Cloud Run** → Submit to AssemblyAI with webhook URL + metadata
5. **AssemblyAI** → Process file and call webhook when complete
6. **n8n** → Receive webhook with transcript_id
7. **n8n** → Fetch transcript text via AssemblyAI API

### Key Features:
- **1-hour temporary storage** in GCS with auto-cleanup
- **Webhook metadata pass-through** via URL query parameters
- **Shared drive support** with `supportsAllDrives=True`
- **Model selection**: `universal`, `slam-1`, `conformer-2`

## 🔑 Environment Setup

### Required Service Account:
- **Name**: `audio-splitter-drive@duhworks.iam.gserviceaccount.com`
- **Permissions**: Google Drive access, GCS access, signed URL generation
- **Key file**: `config/service-account-key.json`

### Required Environment Variables:
```bash
export ASSEMBLYAI_API_KEY="your-32-char-api-key"
export GCS_BUCKET_NAME="audio-splitter-uploads"
```

## 🚦 Service Status

### Currently Deployed:
- ✅ **AssemblyAI Service**: `audio-transcriber-assemblyai` (active)
- ❌ **Whisper Service**: Deleted (was `audio-splitter`)

### Service URLs:
- **AssemblyAI**: https://audio-transcriber-assemblyai-453383149276.us-central1.run.app
- **Health Check**: `/health`
- **Test Webhook**: `/test-webhook`

## 🔧 Development

### Deploy AssemblyAI Service:
```bash
cd services/assemblyai-transcriber
./deploy.sh
```

### Deploy Whisper Service (if needed):
```bash
cd services/whisper-chunking
./deploy.sh
```

### Monitor Logs:
```bash
gcloud run services logs read audio-transcriber-assemblyai --region us-central1 --limit 50
```

## 📝 API Models

**AssemblyAI Models:**
- `"universal"` - Multi-language auto-detection (default)
- `"slam-1"` - Best accuracy for English
- `"conformer-2"` - Balanced speed/accuracy

## 💰 Cost Comparison

**Example: 2-hour meeting file**
- **Whisper**: $0.72 (chunking overhead + processing time)
- **AssemblyAI**: $1.30 (but 5x faster, no chunking complexity)

## 🗂️ File Organization

- **Production code**: Each service is self-contained in `services/`
- **Shared resources**: `config/` for service account
- **Documentation**: This README + `CLAUDE.md` for AI assistance

## 🚀 Next Steps

1. **Production**: Use AssemblyAI service for new workflows
2. **Legacy support**: Keep Whisper service for existing workflows that need it
3. **Cost optimization**: Monitor usage and adjust retention policies
4. **Feature expansion**: Add more AssemblyAI features (speaker diarization, summaries)

---

**Last Updated**: August 2025  
**Active Service**: AssemblyAI Transcriber  
**Status**: Production Ready ✅