#!/bin/bash

# Deploy script for AssemblyAI transcription service
# This deploys a simplified service that sends audio directly to AssemblyAI

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}AssemblyAI Audio Transcriber Deployment${NC}"
echo "========================================"

# Check if required environment variables are set
if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}Error: PROJECT_ID environment variable not set${NC}"
    echo "Please run: export PROJECT_ID=your-gcp-project-id"
    exit 1
fi

if [ -z "$ASSEMBLYAI_API_KEY" ]; then
    echo -e "${RED}Error: ASSEMBLYAI_API_KEY environment variable not set${NC}"
    echo "Please run: export ASSEMBLYAI_API_KEY=your-assemblyai-api-key"
    exit 1
fi

# Configuration
SERVICE_NAME="audio-transcriber-assemblyai"
REGION="us-central1"
SERVICE_ACCOUNT_NAME="audio-splitter-drive"
GCS_BUCKET_NAME="${GCS_BUCKET_NAME:-audio-splitter-uploads}"

echo "Project ID: $PROJECT_ID"
echo "Service: $SERVICE_NAME"
echo "Region: $REGION"
echo "GCS Bucket: $GCS_BUCKET_NAME"
echo ""

# Ensure we're using the right project
gcloud config set project $PROJECT_ID

# Check if Artifact Registry repository exists
echo "Checking Artifact Registry repository..."
if ! gcloud artifacts repositories describe audio-splitter --location=$REGION &>/dev/null; then
    echo "Creating Artifact Registry repository..."
    gcloud artifacts repositories create audio-splitter \
        --repository-format=docker \
        --location=$REGION \
        --description="Audio processing services"
fi

# Check if service account exists
echo "Checking service account..."
if ! gcloud iam service-accounts describe $SERVICE_ACCOUNT_NAME@$PROJECT_ID.iam.gserviceaccount.com &>/dev/null; then
    echo "Creating service account..."
    gcloud iam service-accounts create $SERVICE_ACCOUNT_NAME \
        --display-name="Audio Splitter Service Account"
    
    # Grant necessary permissions
    gcloud projects add-iam-policy-binding $PROJECT_ID \
        --member="serviceAccount:$SERVICE_ACCOUNT_NAME@$PROJECT_ID.iam.gserviceaccount.com" \
        --role="roles/storage.objectAdmin"
fi

# Setup GCS bucket and lifecycle rules
echo "Setting up GCS bucket..."
if ! gcloud storage buckets describe gs://$GCS_BUCKET_NAME &>/dev/null; then
    echo "Creating GCS bucket: $GCS_BUCKET_NAME"
    gcloud storage buckets create gs://$GCS_BUCKET_NAME \
        --location=$REGION \
        --project=$PROJECT_ID
else
    echo "GCS bucket already exists: $GCS_BUCKET_NAME"
fi

# Check and add lifecycle rule for temp files
echo "Checking GCS lifecycle rules..."
LIFECYCLE_EXISTS=$(gcloud storage buckets describe gs://$GCS_BUCKET_NAME --format="value(lifecycle.rule[0].action.type)" 2>/dev/null || echo "")

if [ "$LIFECYCLE_EXISTS" != "Delete" ]; then
    echo "Adding lifecycle rule for automatic cleanup..."
    cat > /tmp/lifecycle.json << EOF
{
  "lifecycle": {
    "rule": [
      {
        "action": {"type": "Delete"},
        "condition": {
          "age": 1,
          "matchesPrefix": ["temp-audio/"]
        }
      }
    ]
  }
}
EOF
    gcloud storage buckets update gs://$GCS_BUCKET_NAME --lifecycle-file=/tmp/lifecycle.json
    rm /tmp/lifecycle.json
    echo "✅ Lifecycle rule added: temp-audio/* files will be deleted after 1 day"
else
    echo "✅ Lifecycle rule already exists"
fi

echo ""
echo -e "${YELLOW}Note: GCS lifecycle works on daily granularity. Files are deleted after 1 day.${NC}"
echo -e "${YELLOW}The 1-hour signed URLs ensure files can't be accessed after 1 hour.${NC}"
echo ""

# Build and deploy using Cloud Build
echo -e "${YELLOW}Starting Cloud Build deployment...${NC}"
gcloud builds submit \
    --config=cloudbuild-assemblyai.yaml \
    --substitutions=_ASSEMBLYAI_API_KEY="$ASSEMBLYAI_API_KEY",_GCS_BUCKET_NAME="$GCS_BUCKET_NAME" \
    .

# Get the service URL
echo ""
echo -e "${GREEN}Deployment complete!${NC}"
echo ""
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --format='value(status.url)')
echo "Service URL: $SERVICE_URL"
echo ""
echo "Test the service:"
echo "  curl $SERVICE_URL/health"
echo ""
echo "Test webhook metadata:"
echo "  curl $SERVICE_URL/test-webhook"
echo ""
echo "Example usage:"
echo "  curl -X POST $SERVICE_URL/transcribe-assemblyai \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{"
echo "      \"drive_file_id\": \"your-file-id\","
echo "      \"webhook_url\": \"https://your-n8n-instance.com/webhook/abc123\","
echo "      \"file_name\": \"audio.mp3\","
echo "      \"source_folder\": \"inbox\","
echo "      \"transcription_folder\": \"transcriptions\","
echo "      \"processed_folder\": \"processed\""
echo "    }'"