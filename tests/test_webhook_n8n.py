#!/usr/bin/env python3
"""
Test webhook functionality specifically for n8n integration
Helps diagnose webhook delivery issues with n8n workflows
"""

import asyncio
import json
import sys
import os
import argparse
from datetime import datetime

# Add the current directory to the path so we can import our module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

try:
    from audio_splitter_drive import send_webhook, test_webhook_connectivity, is_n8n_resume_url
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure you have all required dependencies installed:")
    print("pip install aiohttp fastapi pydantic")
    sys.exit(1)

async def test_n8n_webhook(webhook_url: str, test_type: str = "minimal"):
    """Test n8n webhook with different payload types"""
    
    print(f"🧪 Testing n8n Webhook: {webhook_url}")
    print("=" * 60)
    
    # First, analyze the URL
    print(f"📍 URL Analysis:")
    print(f"   Is n8n URL: {is_n8n_resume_url(webhook_url)}")
    
    # Test connectivity
    print(f"\n🔌 Testing Connectivity...")
    connectivity = await test_webhook_connectivity(webhook_url)
    print(f"   Reachable: {connectivity['reachable']}")
    print(f"   Status Code: {connectivity['status_code']}")
    print(f"   Response Time: {connectivity['response_time']:.2f}s" if connectivity['response_time'] else "N/A")
    if connectivity['error']:
        print(f"   ⚠️  Error: {connectivity['error']}")
    
    # Prepare test payloads
    payloads = {
        "minimal": {
            "status": "test",
            "message": "Testing webhook connectivity"
        },
        "typical": {
            "job_id": f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "status": "completed",
            "file_name": "test_audio.mp3",
            "transcription_text": "This is a test transcription.",
            "processing_time_seconds": 10.5
        },
        "full": {
            "job_id": f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "status": "completed",
            "file_name": "test_audio.mp3",
            "file_size_mb": 19.8,
            "transcription_text": "This is a complete test transcription with all fields populated.",
            "total_duration_seconds": 120.5,
            "processing_method": "direct_transcription",
            "chunks_processed": 1,
            "processing_time_seconds": 45.2,
            "transcription_url": "https://storage.googleapis.com/test-bucket/transcription.txt",
            "webhook_delivered": None,
            "metadata": {
                "format": "m4a",
                "bitrate": "128k",
                "sample_rate": 44100
            }
        }
    }
    
    payload = payloads.get(test_type, payloads["minimal"])
    
    print(f"\n📦 Testing with {test_type} payload:")
    print(f"   Payload size: {len(json.dumps(payload))} bytes")
    print(f"   Payload preview: {json.dumps(payload, indent=2)[:200]}...")
    
    # Test webhook delivery
    print(f"\n🚀 Sending webhook...")
    success = await send_webhook(
        webhook_url,
        payload,
        max_retries=3,
        timeout=30,
        test_connectivity=False  # Already tested above
    )
    
    print(f"\n📊 Results:")
    print(f"   Delivery Status: {'✅ SUCCESS' if success else '❌ FAILED'}")
    
    return success

async def test_multiple_webhooks(webhook_urls: list):
    """Test multiple webhook URLs"""
    print(f"🧪 Testing {len(webhook_urls)} webhook URLs")
    print("=" * 60)
    
    results = []
    for i, url in enumerate(webhook_urls, 1):
        print(f"\n📍 Test {i}/{len(webhook_urls)}")
        success = await test_n8n_webhook(url, "minimal")
        results.append((url, success))
        
        if i < len(webhook_urls):
            print("\n⏳ Waiting 2 seconds before next test...")
            await asyncio.sleep(2)
    
    print("\n📊 Summary:")
    print("=" * 60)
    for url, success in results:
        status = "✅" if success else "❌"
        print(f"{status} {url}")
    
    return results

def main():
    parser = argparse.ArgumentParser(description="Test n8n webhook functionality")
    parser.add_argument("webhook_url", nargs="?", help="n8n webhook URL to test")
    parser.add_argument("--type", choices=["minimal", "typical", "full"], default="typical",
                       help="Type of payload to test (default: typical)")
    parser.add_argument("--multiple", action="store_true", help="Test multiple URLs from stdin")
    parser.add_argument("--example", action="store_true", help="Show example n8n webhook URLs")
    
    args = parser.parse_args()
    
    if args.example:
        print("Example n8n webhook URLs:")
        print("  - https://your-n8n.domain.com/webhook/abc123def456")
        print("  - https://app.n8n.cloud/webhook/abc123/resume")
        print("  - http://localhost:5678/webhook-test/abc123")
        sys.exit(0)
    
    if args.multiple:
        print("Enter webhook URLs (one per line, Ctrl+D when done):")
        urls = []
        try:
            while True:
                url = input().strip()
                if url:
                    urls.append(url)
        except EOFError:
            pass
        
        if not urls:
            print("No URLs provided")
            sys.exit(1)
            
        asyncio.run(test_multiple_webhooks(urls))
    else:
        if not args.webhook_url:
            parser.print_help()
            print("\nError: webhook_url is required unless using --multiple or --example")
            sys.exit(1)
        
        result = asyncio.run(test_n8n_webhook(args.webhook_url, args.type))
        sys.exit(0 if result else 1)

if __name__ == "__main__":
    main()