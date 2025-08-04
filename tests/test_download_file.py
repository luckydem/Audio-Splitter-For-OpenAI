#!/usr/bin/env python3
"""
Test downloading file with shared drive support
"""

import os
import tempfile
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# Path to service account key
SERVICE_ACCOUNT_KEY = "service-account-key.json"

# Initialize credentials
credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_KEY,
    scopes=['https://www.googleapis.com/auth/drive.readonly']
)

# Build Drive service
drive_service = build('drive', 'v3', credentials=credentials)

# The file ID from your workflow
file_id = '1zhAUIDpYSA3FNxBhKQWT0sp9RssUhN7R'

print(f"Testing download of file: {file_id}")
print("-" * 80)

try:
    # Get file metadata (with shared drive support)
    file_metadata = drive_service.files().get(
        fileId=file_id,
        fields='name,size,mimeType',
        supportsAllDrives=True
    ).execute()
    
    print(f"✅ Found file: {file_metadata['name']}")
    print(f"   Size: {int(file_metadata.get('size', 0)) / (1024*1024):.2f} MB")
    print(f"   Type: {file_metadata['mimeType']}")
    
    # Test downloading first 1MB
    print("\nTesting download (first 1MB)...")
    
    # Stream download the file (with shared drive support)
    request = drive_service.files().get_media(fileId=file_id, supportsAllDrives=True)
    
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        downloader = MediaIoBaseDownload(temp_file, request, chunksize=1*1024*1024)  # 1MB chunks
        
        # Download just the first chunk
        status, done = downloader.next_chunk()
        if status:
            print(f"✅ Download progress: {int(status.progress() * 100)}%")
        
        temp_path = temp_file.name
        
    # Check downloaded file
    file_size = os.path.getsize(temp_path) / (1024*1024)
    print(f"✅ Downloaded {file_size:.2f} MB to {temp_path}")
    
    # Clean up
    os.unlink(temp_path)
    print("✅ Test successful! The file can be downloaded with shared drive support.")
    
except Exception as e:
    print(f"❌ Error: {str(e)}")
    if hasattr(e, 'resp'):
        print(f"   HTTP Status: {e.resp.status}")
        print(f"   Details: {e.resp.reason}")

print("-" * 80)