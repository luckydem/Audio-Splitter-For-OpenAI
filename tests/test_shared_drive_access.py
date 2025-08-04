#!/usr/bin/env python3
"""
Test Google Drive access for files in shared drives
"""

import os
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Path to service account key
SERVICE_ACCOUNT_KEY = "service-account-key.json"

# Initialize credentials
credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_KEY,
    scopes=['https://www.googleapis.com/auth/drive.readonly']
)

# Build Drive service
drive_service = build('drive', 'v3', credentials=credentials)

print("Testing access to file in shared drives...")
print("-" * 80)

# The file ID from your workflow
file_id = '1zhAUIDpYSA3FNxBhKQWT0sp9RssUhN7R'

# First, try to get the file with supportsAllDrives parameter
print(f"\nAttempting to access file: {file_id}")
print("Method 1: With supportsAllDrives=True")

try:
    file_metadata = drive_service.files().get(
        fileId=file_id,
        supportsAllDrives=True,
        fields='id, name, mimeType, size, parents, driveId'
    ).execute()
    
    print(f"✅ SUCCESS: Found file '{file_metadata['name']}'")
    print(f"   Size: {int(file_metadata.get('size', 0)) / (1024*1024):.2f} MB")
    print(f"   Type: {file_metadata['mimeType']}")
    if 'driveId' in file_metadata:
        print(f"   Drive ID: {file_metadata['driveId']}")
    if 'parents' in file_metadata:
        print(f"   Parent folders: {file_metadata['parents']}")
        
except Exception as e:
    print(f"❌ ERROR: {str(e)}")

# Search in shared drives
print("\n" + "-" * 80)
print("\nMethod 2: Searching in shared drives")

shared_drives = drive_service.drives().list().execute().get('drives', [])
print(f"Found {len(shared_drives)} shared drives:")
for drive in shared_drives:
    print(f"\n📁 Shared Drive: {drive['name']} (ID: {drive['id']})")
    
    # Search for files in this shared drive
    try:
        results = drive_service.files().list(
            corpora='drive',
            driveId=drive['id'],
            includeItemsFromAllDrives=True,
            supportsAllDrives=True,
            pageSize=10,
            fields="files(id, name, mimeType)"
        ).execute()
        
        files = results.get('files', [])
        if files:
            print(f"   Found {len(files)} files:")
            for f in files[:5]:  # Show first 5 files
                print(f"   - {f['name']} (ID: {f['id'][:8]}...)")
                # Check if this is our target file
                if f['id'] == file_id:
                    print(f"     ⭐ THIS IS THE TARGET FILE!")
        else:
            print("   No files found in this drive")
            
    except Exception as e:
        print(f"   Error listing files: {str(e)}")

# Search for the specific file across all drives
print("\n" + "-" * 80)
print("\nMethod 3: Direct search for file across all locations")

try:
    # Search in all locations including shared drives
    results = drive_service.files().list(
        q=f"'{file_id}' in parents or name contains 'BoD Mtg'",
        includeItemsFromAllDrives=True,
        supportsAllDrives=True,
        corpora='allDrives',
        fields="files(id, name, mimeType, parents)"
    ).execute()
    
    files = results.get('files', [])
    if files:
        print(f"Found {len(files)} files matching search:")
        for f in files:
            print(f"- {f['name']} (ID: {f['id']})")
    else:
        print("No files found matching the search criteria")
        
except Exception as e:
    print(f"Error searching: {str(e)}")

print("\n" + "-" * 80)
print("Test complete.")