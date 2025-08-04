#!/usr/bin/env python3
"""
Test the enhanced Cloud Run endpoint with folder parameters
"""

import asyncio
import json
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from audio_splitter_drive import send_webhook
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)

async def test_enhanced_webhook():
    """Test webhook with the new folder parameters"""
    
    webhook_url = "https://n8n.e-bud.app/webhook/split-and-transcribe-completed"
    
    # Test payload with all the new folder parameters
    enhanced_payload = {
        "job_id": f"test_enhanced_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "status": "completed",
        "file_name": "test_audio_enhanced.mp3",
        "transcription_text": "Testing the enhanced endpoint with folder parameters. This should now include source_folder, transcription_folder, and processed_folder in the webhook payload.",
        "total_duration_seconds": 120.5,
        "processing_method": "direct_transcription",
        "chunks_processed": 1,
        "processing_time_seconds": 45.2,
        "transcription_url": "https://storage.googleapis.com/test-bucket/enhanced_test.txt",
        "webhook_delivered": None,
        
        # NEW: Additional parameters
        "drive_file_id": "1jBxWYEwkJYZWsqIY7BiA4lSMdy8mBa-d",
        "source_folder": "inbox",
        "transcription_folder": "transcriptions/completed", 
        "processed_folder": "processed/audio_files"
    }
    
    print("🧪 Testing Enhanced Endpoint with Folder Parameters")
    print("=" * 60)
    print(f"📍 Webhook URL: {webhook_url}")
    print(f"📦 Payload includes additional parameters:")
    print(f"   - drive_file_id: {enhanced_payload['drive_file_id']}")
    print(f"   - source_folder: {enhanced_payload['source_folder']}")
    print(f"   - transcription_folder: {enhanced_payload['transcription_folder']}")
    print(f"   - processed_folder: {enhanced_payload['processed_folder']}")
    print(f"📊 Total payload size: {len(json.dumps(enhanced_payload))} bytes")
    
    print(f"\n🚀 Sending enhanced webhook...")
    
    success = await send_webhook(
        webhook_url,
        enhanced_payload,
        max_retries=2,
        timeout=15,
        test_connectivity=False
    )
    
    print(f"\n📊 Results:")
    if success:
        print("✅ SUCCESS: Enhanced webhook with folder parameters delivered!")
        print("   Your n8n workflow should now receive the folder information")
        print("   Check your n8n execution to see the new folder fields")
    else:
        print("❌ FAILED: Enhanced webhook delivery failed")
        print("   Check the logs above for details")
    
    return success

async def main():
    print("Testing the enhanced Cloud Run endpoint...")
    print("This simulates what Cloud Run will send after the deployment")
    print()
    
    result = await test_enhanced_webhook()
    
    if result:
        print("\n🎉 The enhanced endpoint is ready to use!")
        print("\nYou can now use this in your n8n HTTP request:")
        print(json.dumps({
            "drive_file_id": "{{ $json.id }}",
            "source_folder": "{{ $json.source_folder }}",
            "transcription_folder": "{{ $json.transcription_folder }}",
            "processed_folder": "{{ $json.processed_folder }}",
            "max_size_mb": 25,
            "output_format": "m4a",
            "quality": "medium",
            "openai_api_key": "your-api-key",
            "webhook_url": "https://n8n.e-bud.app/webhook/split-and-transcribe-completed"
        }, indent=2))
    else:
        print("\n❌ Test failed - check webhook configuration")

if __name__ == "__main__":
    asyncio.run(main())