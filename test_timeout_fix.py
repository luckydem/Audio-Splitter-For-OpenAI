#!/usr/bin/env python3
"""
Test script to verify the timeout fix is working
"""
import requests
import json
import time

# Service URL
SERVICE_URL = "https://audio-splitter-ey3mdkeuya-uc.a.run.app"

def test_health():
    """Test the health endpoint"""
    print("Testing health endpoint...")
    response = requests.get(f"{SERVICE_URL}/")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.status_code == 200

def test_timeout_config():
    """Check timeout configuration"""
    print("\nChecking Cloud Run timeout configuration...")
    import subprocess
    result = subprocess.run(
        ["gcloud", "run", "services", "describe", "audio-splitter", 
         "--region=us-central1", "--format=value(spec.template.spec.timeoutSeconds)"],
        capture_output=True, text=True
    )
    timeout = int(result.stdout.strip())
    print(f"Cloud Run timeout: {timeout} seconds ({timeout/60:.1f} minutes)")
    return timeout

if __name__ == "__main__":
    print("Audio Splitter Timeout Fix Test")
    print("=" * 50)
    
    # Test health
    if test_health():
        print("✅ Service is healthy")
    else:
        print("❌ Service health check failed")
    
    # Check timeout
    timeout = test_timeout_config()
    if timeout >= 3600:
        print("✅ Timeout is set to maximum (60 minutes)")
    else:
        print(f"⚠️  Timeout is only {timeout} seconds, should be 3600")
    
    print("\nNOTE: For files that take longer than 60 minutes to process,")
    print("consider implementing:")
    print("1. Background job processing with Cloud Tasks")
    print("2. Chunked processing with progress tracking")
    print("3. Webhook-based async processing")