#!/usr/bin/env python3
"""
Quick webhook test using httpbin.org
Tests the improved webhook functionality with a real endpoint
"""

import asyncio
import json
import sys
import os

# Add the current directory to the path so we can import our module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

try:
    from audio_splitter_drive import send_webhook, test_webhook_connectivity, is_n8n_resume_url
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure you have all required dependencies installed:")
    print("pip install aiohttp fastapi pydantic")
    sys.exit(1)

async def test_real_webhook():
    """Test with httpbin.org which provides real HTTP responses"""
    
    print("🧪 Quick Webhook Test with httpbin.org")
    print("=" * 45)
    
    # Test payload similar to what the service would send
    test_payload = {
        "job_id": "test_20240804_123456",
        "status": "completed",
        "file_name": "test_audio.mp3",
        "transcription_text": "This is a test transcription from the improved webhook system.",
        "total_duration_seconds": 120.5,
        "processing_method": "direct_transcription",
        "chunks_processed": 1,
        "processing_time_seconds": 45.2,
        "transcription_url": "https://storage.googleapis.com/test-bucket/transcription.txt",
        "webhook_delivered": None
    }
    
    # Test with httpbin.org (should work)
    webhook_url = "https://httpbin.org/post"
    
    print(f"🔗 Testing webhook URL: {webhook_url}")
    print(f"📦 Payload size: {len(json.dumps(test_payload))} bytes")
    
    # Test connectivity first
    print("\n1️⃣ Testing connectivity...")
    connectivity_result = await test_webhook_connectivity(webhook_url)
    print(f"   ✅ Reachable: {connectivity_result['reachable']}")
    print(f"   📊 Status: {connectivity_result['status_code']}")
    print(f"   ⏱️ Response time: {connectivity_result['response_time']:.2f}s" if connectivity_result['response_time'] else "N/A")
    
    # Test actual webhook delivery
    print("\n2️⃣ Testing webhook delivery...")
    success = await send_webhook(
        webhook_url, 
        test_payload,
        max_retries=2,
        timeout=10,
        test_connectivity=False  # We already tested above
    )
    
    if success:
        print("   ✅ Webhook delivered successfully!")
    else:
        print("   ❌ Webhook delivery failed!")
    
    # Test n8n URL detection
    print("\n3️⃣ Testing n8n URL detection...")
    test_n8n_urls = [
        "https://httpbin.org/post",  # Not n8n
        "https://n8n.example.com/webhook/abc123",  # n8n
        "https://app.n8n.cloud/webhook/def456/resume"  # n8n
    ]
    
    for url in test_n8n_urls:
        is_n8n = is_n8n_resume_url(url)
        print(f"   {'🎯' if is_n8n else '🌐'} {url} -> n8n: {is_n8n}")
    
    print("\n4️⃣ Testing error scenarios...")
    
    # Test 404 URL
    error_url = "https://httpbin.org/status/404"
    print(f"   Testing 404 URL: {error_url}")
    success_404 = await send_webhook(
        error_url,
        {"test": "404_scenario"},
        max_retries=1,
        timeout=5
    )
    print(f"   Result: {'❌ Failed as expected' if not success_404 else '⚠️ Unexpected success'}")
    
    print("\n🏁 Quick webhook test completed!")
    return success

if __name__ == "__main__":
    try:
        result = asyncio.run(test_real_webhook())
        if result:
            print("✅ All webhook improvements are working correctly!")
            sys.exit(0)
        else:
            print("❌ Some webhook functionality may need attention")
            sys.exit(1)
    except Exception as e:
        print(f"💥 Test failed with error: {e}")
        sys.exit(1)