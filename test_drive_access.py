#!/usr/bin/env python3
"""
Test Google Drive access for the service account
Lists all files and folders accessible to the service account
"""

import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
import json

# Path to service account key
SERVICE_ACCOUNT_KEY = "service-account-key.json"

# Initialize credentials
credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_KEY,
    scopes=['https://www.googleapis.com/auth/drive.readonly']
)

# Build Drive service
drive_service = build('drive', 'v3', credentials=credentials)

print("Testing Google Drive access for service account...")
print(f"Service account email: {credentials.service_account_email}")
print("-" * 80)

try:
    # List all files accessible to the service account
    print("\nListing all accessible files and folders:")
    
    # Query for all files
    results = drive_service.files().list(
        pageSize=100,
        fields="files(id, name, mimeType, parents, permissions, shared)",
        orderBy="modifiedTime desc"
    ).execute()
    
    files = results.get('files', [])
    
    if not files:
        print("No files found. The service account may not have access to any files.")
    else:
        print(f"\nFound {len(files)} accessible items:\n")
        
        # Separate folders and files
        folders = []
        regular_files = []
        
        for file in files:
            if file['mimeType'] == 'application/vnd.google-apps.folder':
                folders.append(file)
            else:
                regular_files.append(file)
        
        # Display folders
        if folders:
            print("FOLDERS:")
            for folder in folders:
                print(f"  📁 {folder['name']}")
                print(f"     ID: {folder['id']}")
                print(f"     Shared: {folder.get('shared', False)}")
                print()
        
        # Display files
        if regular_files:
            print("\nFILES:")
            for file in regular_files:
                print(f"  📄 {file['name']}")
                print(f"     ID: {file['id']}")
                print(f"     Type: {file['mimeType']}")
                print(f"     Shared: {file.get('shared', False)}")
                print()
    
    # Test access to the specific file from your workflow
    print("\n" + "-" * 80)
    print("\nTesting access to specific file: 1zhAUIDpYSA3FNxBhKQWT0sp9RssUhN7R")
    
    try:
        file_metadata = drive_service.files().get(
            fileId='1zhAUIDpYSA3FNxBhKQWT0sp9RssUhN7R',
            fields='id, name, mimeType, size, parents, permissions'
        ).execute()
        
        print(f"✅ SUCCESS: Can access file '{file_metadata['name']}'")
        print(f"   Size: {int(file_metadata.get('size', 0)) / (1024*1024):.2f} MB")
        print(f"   Type: {file_metadata['mimeType']}")
        
        # Check permissions
        if 'permissions' in file_metadata:
            print("\n   Permissions:")
            for perm in file_metadata['permissions']:
                print(f"   - {perm.get('type')}: {perm.get('role')}")
                if perm.get('emailAddress'):
                    print(f"     Email: {perm['emailAddress']}")
                    
    except Exception as e:
        print(f"❌ ERROR: Cannot access file")
        print(f"   Error: {str(e)}")
        
        # Try to get more details about the error
        if hasattr(e, 'resp'):
            print(f"   HTTP Status: {e.resp.status}")
            print(f"   Details: {e.resp.reason}")

    # Query for shared drives
    print("\n" + "-" * 80)
    print("\nChecking for shared drives access:")
    
    try:
        shared_drives = drive_service.drives().list(
            pageSize=10
        ).execute()
        
        drives = shared_drives.get('drives', [])
        if drives:
            print(f"Found {len(drives)} shared drives:")
            for drive in drives:
                print(f"  - {drive['name']} (ID: {drive['id']})")
        else:
            print("No shared drives accessible.")
    except Exception as e:
        print(f"Error listing shared drives: {str(e)}")

except Exception as e:
    print(f"\nError accessing Drive API: {str(e)}")
    if hasattr(e, 'resp'):
        print(f"HTTP Status: {e.resp.status}")
        print(f"Details: {e.resp.reason}")

print("\n" + "-" * 80)
print("Test complete.")