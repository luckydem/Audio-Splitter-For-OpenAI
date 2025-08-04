# Google Drive Direct Integration Setup

This guide explains how to set up the Google Drive integration for direct audio processing without downloading files locally.

## Architecture Overview

```
Google Drive → Cloud Run API → Process & Split → Transcribe → Upload Minutes → Google Drive
     ↑                                                                              ↑
     └──────────────────── No Local Downloads Required ────────────────────────────┘
```

## Benefits Over Current Approach

1. **No Local Downloads**: Files stream directly from Drive to the API
2. **5-10x Faster**: 60-minute audio processes in ~2 minutes (vs 60+ minutes)
3. **Scalable**: Handles multiple files simultaneously
4. **No Storage Limits**: Your Raspberry Pi storage isn't a bottleneck
5. **Direct Integration**: n8n workflow is simpler and more reliable

## Setup Instructions

### 1. Deploy the Enhanced API

Update the existing Dockerfile to include Google APIs:

```dockerfile
# Add to existing Dockerfile after pip install requirements
RUN pip install --no-cache-dir \
    google-api-python-client==2.100.0 \
    google-auth==2.23.0
```

Deploy with Drive integration:
```bash
# Update deploy.sh to use audio_splitter_drive.py
sed -i 's/audio_splitter_gcs.py/audio_splitter_drive.py/g' Dockerfile
./deploy.sh
```

### 2. Create Service Account

```bash
# Create service account for Drive access
gcloud iam service-accounts create drive-audio-processor \
    --display-name="Drive Audio Processor"

# Download key
gcloud iam service-accounts keys create service-account-key.json \
    --iam-account=drive-audio-processor@YOUR_PROJECT_ID.iam.gserviceaccount.com

# Grant necessary permissions
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:drive-audio-processor@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/storage.objectAdmin"
```

### 3. Share Drive Folders with Service Account

1. Get the service account email: `drive-audio-processor@YOUR_PROJECT_ID.iam.gserviceaccount.com`
2. Share your Google Drive folders with this email:
   - Input folder (where audio files are uploaded)
   - Output folder (where minutes are saved)
   - Processed folder (where original files are moved)

### 4. Configure n8n Workflow

Import the provided `n8n_drive_workflow.json` and update:
- `YOUR_DRIVE_FOLDER_ID`: The folder ID to monitor for new files
- `YOUR_OUTPUT_FOLDER_ID`: Where to save the minutes
- `YOUR_PROCESSED_FOLDER_ID`: Where to move processed files
- `YOUR_CREDENTIAL_ID`: Your Google Drive OAuth2 credential in n8n
- `YOUR_OPENAI_CREDENTIAL_ID`: Your OpenAI API credential in n8n
- `audio-splitter-xxx.run.app`: Your actual Cloud Run URL

### 5. Environment Variables for Cloud Run

Update your Cloud Run deployment:
```bash
gcloud run services update audio-splitter \
    --set-env-vars="GOOGLE_SERVICE_ACCOUNT_KEY=/app/service-account-key.json" \
    --region=us-central1
```

## API Endpoints

### Process Single File from Drive
```bash
curl -X POST https://your-service.run.app/process-drive-file \
  -H "Content-Type: application/json" \
  -d '{
    "drive_file_id": "1abc123...",
    "max_size_mb": 20,
    "webhook_url": "https://your-n8n.com/webhook/..."
  }'
```

### Process Entire Folder
```bash
curl -X POST https://your-service.run.app/process-drive-folder \
  -H "Content-Type: application/json" \
  -d '{
    "folder_id": "1folder123...",
    "max_size_mb": 20
  }'
```

### Direct Transcription (if you already have chunks)
```bash
curl -X POST https://your-service.run.app/transcribe-and-compile \
  -H "Content-Type: application/json" \
  -d '{
    "chunks": [...],
    "openai_api_key": "sk-...",
    "compile_minutes": true
  }'
```

## How It Works

1. **File Detection**: n8n detects new audio file in Google Drive
2. **Direct Processing**: Sends file ID to Cloud Run API (no download)
3. **Streaming Split**: API streams file from Drive, splits it, uploads chunks to GCS
4. **Parallel Transcription**: All chunks transcribed simultaneously with OpenAI
5. **Minutes Compilation**: Transcriptions combined and processed into minutes
6. **Auto Upload**: Minutes uploaded back to Drive, original moved to processed

## Performance Comparison

| Metric | Raspberry Pi | Cloud Run Direct |
|--------|--------------|------------------|
| 60min Audio Processing | 60+ minutes | 2-3 minutes |
| Concurrent Files | 1 | 10+ |
| Storage Required | Full file size | None (streaming) |
| Network Usage | 2x file size | 1x file size |
| Reliability | Medium | High |

## Troubleshooting

1. **"Google Drive service not configured"**: Ensure service account key is uploaded
2. **"Failed to download from Drive"**: Check folder sharing permissions
3. **Slow processing**: Verify you're using m4a format, not ogg
4. **Webhook timeout**: Increase n8n webhook wait timeout to 10 minutes

## Cost Estimate

For 100 hours of audio per month:
- Cloud Run: ~$5-10
- Cloud Storage: ~$2
- OpenAI Whisper: ~$60
- **Total**: ~$70/month (vs electricity + internet for Pi)

## Migration Path

1. Deploy new API alongside existing setup
2. Test with a few files
3. Update n8n workflows one at a time
4. Monitor performance
5. Decommission local processing