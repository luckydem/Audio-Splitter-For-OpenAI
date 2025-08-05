#!/bin/bash
# DriveScribe Project Migration Plan
# This script outlines the migration from duhworks to drivescribe project
# DO NOT RUN AUTOMATICALLY - Use as a reference checklist

set -e

echo "🔮 DriveScribe Project Migration Plan"
echo "===================================="
echo
echo "⚠️  DO NOT RUN THIS SCRIPT AUTOMATICALLY"
echo "⚠️  Use this as a step-by-step reference guide"
echo

# Configuration
OLD_PROJECT="duhworks"
NEW_PROJECT="drivescribe"
OLD_SERVICE_ACCOUNT="audio-splitter-drive@duhworks.iam.gserviceaccount.com"
NEW_SERVICE_ACCOUNT="transcribe@drivescribe.iam.gserviceaccount.com"
OLD_BUCKET="audio-splitter-uploads"
NEW_BUCKET="drivescribe-audio-temp"
REGION="us-central1"

echo "Migration Configuration:"
echo "  Old Project: $OLD_PROJECT"
echo "  New Project: $NEW_PROJECT"
echo "  Old Service Account: $OLD_SERVICE_ACCOUNT"
echo "  New Service Account: $NEW_SERVICE_ACCOUNT"
echo "  Old Bucket: $OLD_BUCKET"
echo "  New Bucket: $NEW_BUCKET"
echo "  Region: $REGION"
echo

echo "📋 Migration Steps Checklist:"
echo

echo "□ Step 1: Create new GCP project"
echo "  gcloud projects create $NEW_PROJECT --name='DriveScribe'"
echo "  gcloud config set project $NEW_PROJECT"
echo

echo "□ Step 2: Enable required APIs"
echo "  gcloud services enable run.googleapis.com"
echo "  gcloud services enable cloudbuild.googleapis.com" 
echo "  gcloud services enable artifactregistry.googleapis.com"
echo "  gcloud services enable storage.googleapis.com"
echo "  gcloud services enable drive.googleapis.com"
echo

echo "□ Step 3: Set up Artifact Registry"
echo "  gcloud artifacts repositories create audio-splitter \\"
echo "    --repository-format=docker \\"
echo "    --location=$REGION \\"
echo "    --description='DriveScribe Docker images'"
echo

echo "□ Step 4: Create service account"
echo "  gcloud iam service-accounts create transcribe \\"
echo "    --display-name='DriveScribe Transcription Service' \\"
echo "    --project=$NEW_PROJECT"
echo

echo "□ Step 5: Grant service account permissions"
echo "  # Storage permissions"
echo "  gcloud projects add-iam-policy-binding $NEW_PROJECT \\"
echo "    --member='serviceAccount:$NEW_SERVICE_ACCOUNT' \\"
echo "    --role='roles/storage.objectAdmin'"
echo
echo "  # Drive API permissions (enable in Google Cloud Console)"
echo "  # https://console.cloud.google.com/apis/credentials"
echo

echo "□ Step 6: Create GCS bucket with lifecycle rules"
echo "  gsutil mb -p $NEW_PROJECT -c STANDARD -l $REGION gs://$NEW_BUCKET"
echo
echo "  # Create lifecycle configuration"
echo "  cat > lifecycle.json << EOF"
echo "  {"
echo '    "lifecycle": {'
echo '      "rule": [{'
echo '        "action": {"type": "Delete"},'
echo '        "condition": {'
echo '          "age": 1,'
echo '          "matchesPrefix": ["temp-audio/"]'
echo '        }'
echo '      }]'
echo '    }'
echo "  }"
echo "  EOF"
echo
echo "  gsutil lifecycle set lifecycle.json gs://$NEW_BUCKET"
echo "  rm lifecycle.json"
echo

echo "□ Step 7: Generate and download service account key"
echo "  gcloud iam service-accounts keys create config/service-account-key-new.json \\"
echo "    --iam-account=$NEW_SERVICE_ACCOUNT"
echo

echo "□ Step 8: Update deployment scripts"
echo "  # Update services/assemblyai-transcriber/deploy.sh"
echo "  # Update services/whisper-chunking/deploy.sh"
echo "  # Change PROJECT_ID, SERVICE_ACCOUNT_NAME, GCS_BUCKET_NAME"
echo

echo "□ Step 9: Update Google Drive sharing"
echo "  # Share Google Drive folders with: $NEW_SERVICE_ACCOUNT"
echo "  # Remove access from: $OLD_SERVICE_ACCOUNT"
echo

echo "□ Step 10: Deploy services to new project"
echo "  cd services/assemblyai-transcriber"
echo "  ./deploy.sh"
echo
echo "  # Test deployment"
echo "  curl https://audio-transcriber-assemblyai-[NEW-HASH].$REGION.run.app/health"
echo

echo "□ Step 11: Update n8n workflows"
echo "  # Update webhook URLs in n8n HTTP Request nodes"
echo "  # Old: https://audio-transcriber-assemblyai-453383149276.us-central1.run.app"
echo "  # New: https://audio-transcriber-assemblyai-[NEW-HASH].us-central1.run.app"
echo

echo "□ Step 12: End-to-end testing"
echo "  # Test with non-production files first"
echo "  # Verify webhook delivery"
echo "  # Check transcript retrieval"
echo

echo "□ Step 13: Production cutover"
echo "  # Switch production n8n workflows to new URLs"
echo "  # Monitor for 24 hours"
echo

echo "□ Step 14: Cleanup old resources"
echo "  # After successful migration (wait 1 week):"
echo "  # gcloud run services delete audio-transcriber-assemblyai --region=$REGION --project=$OLD_PROJECT"
echo "  # gsutil rm -r gs://$OLD_BUCKET/temp-audio/"
echo

echo "🎯 Files to Update:"
echo "  - services/assemblyai-transcriber/deploy.sh (PROJECT_ID, SERVICE_ACCOUNT_NAME, GCS_BUCKET_NAME)"
echo "  - services/whisper-chunking/deploy.sh (PROJECT_ID, SERVICE_ACCOUNT_NAME, GCS_BUCKET_NAME)"
echo "  - config/service-account-key.json (replace with new key)"
echo "  - README.md (update service URLs and project references)"
echo "  - CLAUDE.md (update current architecture section)"
echo

echo "⏱️  Estimated Migration Time: 2-3 hours"
echo "🔒 Risk Level: Medium (requires n8n coordination)"
echo "🔄 Rollback: Keep old services running until verified"
echo

echo "✅ Migration complete when:"
echo "  - New services respond to health checks"
echo "  - n8n workflows updated and tested"
echo "  - End-to-end transcription working"
echo "  - Old services can be safely decommissioned"
echo

echo "📞 Support:"
echo "  - GCP Console: https://console.cloud.google.com"
echo "  - Service URLs: Check Cloud Run console for new URLs"
echo "  - Logs: gcloud run services logs read audio-transcriber-assemblyai --region=$REGION"