# Audio File Splitter for OpenAI Transcription

A Python script that splits large audio files into smaller chunks suitable for OpenAI's transcription API, which has a 25MB file size limit.

## Features

- Splits audio files based on file size limits (default 20MB)
- Supports multiple input formats: MP3, WAV, FLAC, OGG, M4A, WMA, and more
- Outputs to M4A format by default for optimal OpenAI compatibility and compression
- Configurable output format (MP3, WAV, M4A) and quality settings
- Maintains n8n workflow compatibility with structured output
- Smart chunk size calculation to prevent oversized files

## Prerequisites

1. **Python 3.6+**
2. **FFmpeg** installed on your system
   - Ubuntu/Debian: `sudo apt-get install ffmpeg`
   - macOS: `brew install ffmpeg`
   - Windows: Download from [ffmpeg.org](https://ffmpeg.org/download.html)

## Installation

1. Clone this repository:
   ```bash
   git clone <your-repo-url>
   cd scripts
   ```

2. Create a virtual environment (recommended):
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

Basic usage:
```bash
python split_audio.py --input /path/to/audio.wma --output /path/to/output_dir
```

With options:
```bash
python split_audio.py --input audio.wma --output chunks/ --maxmb 20 --format m4a --quality medium --verbose
```

### Options

- `--input`: Path to input audio file (required)
- `--output`: Output directory for chunks (required)
- `--maxmb`: Maximum size in MB per chunk (default: 20, max recommended: 25)
- `--format`: Output format - mp3, wav, or m4a (default: m4a)
- `--quality`: Audio quality - high, medium, or low (default: medium)
- `--verbose`: Show detailed processing information
- `--no-log`: Disable logging to file (logs are enabled by default)

## n8n Integration

The script outputs "Exporting /path/to/chunk" messages to stdout for easy parsing in n8n workflows. Use the included `n8n_parser_improved.js` for robust parsing:

```javascript
const filePaths = $('Execute Audio Splitter Script').first().json.stdout
    .split("\n")
    .filter(line => line.includes("Exporting "))
    .map(line => line.replace("Exporting ", "").trim());
```

## Output Quality Settings

- **High**: 192 kbps, 44.1 kHz (best quality, larger files)
- **Medium**: 128 kbps, 44.1 kHz (recommended - good quality/size balance)
- **Low**: 96 kbps, 22.05 kHz (smallest files, may affect transcription quality)

**Note**: M4A format is ~30% more efficient than MP3, so M4A at medium quality often provides better results than MP3 at the same bitrate.

## Logging

The script automatically creates detailed logs in the `logs/` directory with timestamps. Each execution creates a new log file named `audio_splitter_YYYYMMDD_HHMMSS.log`.

**Log contents include:**
- Script execution details and parameters
- Input file analysis results
- Processing progress for each chunk
- Error messages and warnings
- Processing summary with file sizes
- Performance metrics

**Managing log files:**
```bash
# Keep logs from last 30 days
python cleanup_logs.py --days 30

# Keep only the 10 most recent log files
python cleanup_logs.py --count 10
```

To disable logging, use the `--no-log` flag:
```bash
python split_audio.py --input audio.wma --output chunks/ --no-log
```

**Format Recommendations:**
- **M4A (default)**: Best compression efficiency, smaller files, fully compatible with OpenAI
- **MP3**: Universal compatibility, slightly larger files than M4A
- **WAV**: Uncompressed, largest files but highest quality

## Troubleshooting

1. **"No audio stream found in the file"**: The input file may be corrupted or not contain audio
2. **Chunks exceed 25MB**: Try using `--quality medium` or `--quality low`
3. **FFmpeg not found**: Ensure FFmpeg is installed and in your system PATH
4. **Check the logs**: Look in the `logs/` directory for detailed error information

## Serverless Deployment (Google Cloud Run)

Deploy the audio splitter as a serverless API on Google Cloud Run for scalable, on-demand processing.

### Features

- **RESTful API** with FastAPI
- **Google Cloud Storage** integration for file storage
- **Signed URLs** for secure file downloads
- **Webhook notifications** for async processing
- **Auto-scaling** with Cloud Run

### Quick Deploy

1. **Prerequisites**:
   ```bash
   # Install Google Cloud SDK
   curl https://sdk.cloud.google.com | bash
   
   # Authenticate
   gcloud auth login
   gcloud config set project YOUR_PROJECT_ID
   ```

2. **Update deployment script**:
   ```bash
   # Edit deploy.sh and set your project ID
   sed -i 's/your-project-id/YOUR_PROJECT_ID/g' deploy.sh
   ```

3. **Deploy to Cloud Run**:
   ```bash
   ./deploy.sh
   ```

### API Endpoints

#### Upload and Split Audio
```bash
curl -X POST \
  -F "file=@audio.mp3" \
  -F "max_size_mb=20" \
  -F "output_format=m4a" \
  https://your-service.run.app/split
```

**Response**:
```json
{
  "job_id": "20250729115940_audio.mp3",
  "status": "completed",
  "total_chunks": 5,
  "chunks": [
    {
      "chunk_number": 1,
      "filename": "chunk_001.m4a",
      "size_mb": 19.8,
      "download_url": "https://storage.googleapis.com/..."
    }
  ]
}
```

#### Process File from GCS
```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "gcs_path": "gs://my-bucket/audio.mp3",
    "max_size_mb": 20,
    "webhook_url": "https://myapp.com/webhook"
  }' \
  https://your-service.run.app/split-from-gcs
```

### n8n Integration

Replace your Execute Command node with an HTTP Request node:

1. **Method**: POST
2. **URL**: `https://your-service.run.app/split`
3. **Send Binary Data**: Enable
4. **Binary Property**: Select your audio file
5. **Options** > **Query Parameters**:
   - `max_size_mb`: 20
   - `output_format`: m4a

### Architecture Options

1. **Basic API** (`audio_splitter_api.py`):
   - Simple file upload/download
   - Temporary local storage
   - Good for testing

2. **GCS-Integrated API** (`audio_splitter_gcs.py`):
   - Direct Google Cloud Storage integration
   - Signed URLs for secure access
   - Production-ready with webhooks

### Configuration

Environment variables for Cloud Run:
- `GCS_BUCKET_NAME`: Storage bucket for chunks
- `SIGNED_URL_EXPIRY_HOURS`: URL expiration time (default: 24)
- `PORT`: Server port (default: 8080)

### Performance

- **Memory**: 2GB (configurable in cloudbuild.yaml)
- **CPU**: 2 vCPUs
- **Timeout**: 10 minutes
- **Concurrency**: 10 requests per instance
- **Auto-scaling**: 0-100 instances

### Monitoring

View logs and metrics:
```bash
# View logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=audio-splitter" --limit 50

# View metrics in Cloud Console
gcloud run services describe audio-splitter --region=us-central1
```

### Cost Optimization

- Files are automatically deleted after 7 days
- Cloud Run scales to zero when not in use
- Use `--max-instances` to control costs

## Storage Configuration & Retention

### Current Setup

The service uses Google Cloud Storage bucket `audio-splitter-chunks-duhworks` with the following structure:

```
audio-splitter-chunks-duhworks/
├── chunks/                    # Audio file chunks
│   └── {job_id}/
│       ├── chunk_001.m4a
│       ├── chunk_002.m4a
│       └── ...
└── transcriptions/           # Transcription results
    └── {job_id}/
        └── full_transcript.txt
```

### Retention Policy

**Default: 7 days** - All files (chunks and transcriptions) are automatically deleted after 7 days.

### Changing Retention Without Downtime

#### Method 1: Quick Update via gsutil (No rebuild required)

```bash
# View current lifecycle policy
gsutil lifecycle get gs://audio-splitter-chunks-duhworks

# Change to 30 days retention
cat > lifecycle.json << EOF
{
  "lifecycle": {
    "rule": [
      {
        "action": {"type": "Delete"},
        "condition": {"age": 30}
      }
    ]
  }
}
EOF
gsutil lifecycle set lifecycle.json gs://audio-splitter-chunks-duhworks
rm lifecycle.json

# Verify the change
gsutil lifecycle get gs://audio-splitter-chunks-duhworks
```

#### Method 2: Different Retention for Chunks vs Transcriptions

```bash
# Keep chunks for 7 days, transcriptions for 90 days
cat > lifecycle.json << EOF
{
  "lifecycle": {
    "rule": [
      {
        "action": {"type": "Delete"},
        "condition": {
          "age": 7,
          "matchesPrefix": ["chunks/"]
        }
      },
      {
        "action": {"type": "Delete"},
        "condition": {
          "age": 90,
          "matchesPrefix": ["transcriptions/"]
        }
      }
    ]
  }
}
EOF
gsutil lifecycle set lifecycle.json gs://audio-splitter-chunks-duhworks
rm lifecycle.json
```

#### Method 3: Archive to Cheaper Storage

```bash
# Move to Nearline storage after 30 days, delete after 365 days
cat > lifecycle.json << EOF
{
  "lifecycle": {
    "rule": [
      {
        "action": {
          "type": "SetStorageClass",
          "storageClass": "NEARLINE"
        },
        "condition": {
          "age": 30,
          "matchesStorageClass": ["STANDARD"]
        }
      },
      {
        "action": {"type": "Delete"},
        "condition": {"age": 365}
      }
    ]
  }
}
EOF
gsutil lifecycle set lifecycle.json gs://audio-splitter-chunks-duhworks
rm lifecycle.json
```

### Other Runtime Configuration Changes (No Rebuild)

#### 1. Change Signed URL Expiry Time

```bash
# Update Cloud Run environment variable (default: 24 hours)
gcloud run services update audio-splitter-drive \
  --update-env-vars SIGNED_URL_EXPIRY_HOURS=48 \
  --region us-central1
```

#### 2. Update Bucket Name

```bash
# Create new bucket
gsutil mb -p duhworks -c STANDARD -l us-central1 gs://new-bucket-name

# Update Cloud Run service
gcloud run services update audio-splitter-drive \
  --update-env-vars GCS_BUCKET_NAME=new-bucket-name \
  --region us-central1
```

#### 3. Change Chunk Storage Prefix

```bash
gcloud run services update audio-splitter-drive \
  --update-env-vars GCS_CHUNK_PREFIX=audio-chunks/ \
  --region us-central1
```

### Monitoring Storage Usage

```bash
# View bucket size
gsutil du -sh gs://audio-splitter-chunks-duhworks

# View detailed usage by folder
gsutil du -h gs://audio-splitter-chunks-duhworks/*

# List old files that will be deleted soon
gsutil ls -L gs://audio-splitter-chunks-duhworks/** | grep -B1 "Creation time" | grep -B1 "$(date -d '6 days ago' '+%Y-%m-%d')"
```

### Best Practices

1. **For Production**: Use 30-90 day retention for transcriptions, 7-14 days for audio chunks
2. **For Compliance**: Implement separate buckets with different retention policies
3. **For Cost Optimization**: 
   - Use lifecycle rules to transition to cheaper storage classes
   - Monitor bucket size regularly
   - Consider shorter retention for large audio files

### Storage Costs

With current 7-day retention:
- Standard storage: ~$0.020/GB/month
- Effective cost with 7-day retention: ~$0.0047/GB
- Example: Processing 100GB/month costs ~$0.47 in storage

## License

This project is licensed under the MIT License.