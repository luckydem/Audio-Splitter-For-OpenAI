#!/bin/bash
# Deploy script for Google Cloud Run

# Set variables
PROJECT_ID="your-project-id"
REGION="us-central1"
SERVICE_NAME="audio-splitter"
BUCKET_NAME="audio-splitter-chunks"

# Enable required APIs
echo "Enabling required APIs..."
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable storage-component.googleapis.com

# Create GCS bucket if it doesn't exist
echo "Creating GCS bucket..."
gsutil mb -p $PROJECT_ID -c STANDARD -l $REGION gs://$BUCKET_NAME || echo "Bucket already exists"

# Set bucket lifecycle to delete files after 7 days
cat > lifecycle.json << EOF
{
  "lifecycle": {
    "rule": [
      {
        "action": {"type": "Delete"},
        "condition": {"age": 7}
      }
    ]
  }
}
EOF
gsutil lifecycle set lifecycle.json gs://$BUCKET_NAME
rm lifecycle.json

# Build and deploy using Cloud Build
echo "Building and deploying to Cloud Run..."
gcloud builds submit --config cloudbuild.yaml \
  --substitutions=_SERVICE_NAME=$SERVICE_NAME,_REGION=$REGION

# Get the service URL
echo "Getting service URL..."
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --format='value(status.url)')
echo "Service deployed at: $SERVICE_URL"

# Create service account for Cloud Run (optional - for authenticated access)
echo "Creating service account..."
gcloud iam service-accounts create audio-splitter-sa \
  --display-name="Audio Splitter Service Account" || echo "Service account already exists"

# Grant necessary permissions
echo "Granting permissions..."
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:audio-splitter-sa@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/storage.objectAdmin"

# Update Cloud Run service to use service account
gcloud run services update $SERVICE_NAME \
  --service-account=audio-splitter-sa@$PROJECT_ID.iam.gserviceaccount.com \
  --region=$REGION

echo "Deployment complete!"
echo ""
echo "To test the API:"
echo "curl -X POST -F 'file=@audio.mp3' $SERVICE_URL/split"