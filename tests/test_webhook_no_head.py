#!/usr/bin/env python3
"""
Test webhook delivery without HEAD requests (mimics our fix)
"""

import asyncio
import json
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

try:
    from audio_splitter_drive import send_webhook
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)

async def test_webhook_no_head(webhook_url: str):
    """Test webhook delivery without connectivity testing (no HEAD request)"""
    
    print(f"🧪 Testing Webhook Without HEAD Request")
    print(f"📍 URL: {webhook_url}")
    print("=" * 60)
    
    # Create realistic payload like Cloud Run sends
    test_payload = {
        "job_id": f"test_no_head_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "status": "completed",
        "file_name": "test_audio_no_head.mp3",
        "file_size_mb": 10.5,
        "transcription_text": "Testing webhook delivery without HEAD requests. This simulates the Cloud Run fix.",
        "total_duration_seconds": 90.0,
        "processing_method": "direct_transcription",
        "chunks_processed": 1,
        "processing_time_seconds": 25.3,
        "transcription_url": "https://storage.googleapis.com/test-bucket/test.txt",
        "webhook_delivered": None
    }
    
    print(f"📦 Payload size: {len(json.dumps(test_payload))} bytes")
    print(f"🚀 Sending POST request directly (no HEAD test)...")
    
    # Call send_webhook with test_connectivity=False (our fix)
    success = await send_webhook(
        webhook_url,
        test_payload,
        max_retries=3,
        timeout=30,
        test_connectivity=False  # This is our fix - no HEAD request
    )
    
    print(f"\n📊 Results:")
    if success:
        print("✅ SUCCESS: Webhook delivered without HEAD request!")
        print("   This confirms the fix is working")
    else:
        print("❌ FAILED: Webhook still not working")
        print("   Check if n8n webhook is properly configured")
    
    return success

async def main():
    if len(sys.argv) < 2:
        print("Usage: python test_webhook_no_head.py <webhook_url>")
        print("\nExample:")
        print("  python test_webhook_no_head.py https://n8n.e-bud.app/webhook/abc123")
        sys.exit(1)
    
    webhook_url = sys.argv[1]
    await test_webhook_no_head(webhook_url)

if __name__ == "__main__":
    asyncio.run(main())