#!/usr/bin/env python3
"""
Test script for webhook improvements
Tests various webhook scenarios including n8n URLs and common failure cases
"""

import asyncio
import aiohttp
import json
from datetime import datetime
from audio_splitter_drive import send_webhook, test_webhook_connectivity, is_n8n_resume_url

async def test_webhook_scenarios():
    """Test various webhook scenarios"""
    
    print("🧪 Testing Webhook Improvements")
    print("=" * 50)
    
    # Test URLs (some will fail intentionally)
    test_urls = [
        {
            "name": "Valid Webhook (httpbin)",
            "url": "https://httpbin.org/post",
            "should_work": True
        },
        {
            "name": "404 Error URL",
            "url": "https://httpbin.org/status/404",
            "should_work": False
        },
        {
            "name": "n8n-style URL (fake)",
            "url": "https://n8n.example.com/webhook/abc123def456/executions/resume",
            "should_work": False
        },
        {
            "name": "Invalid URL",
            "url": "not-a-valid-url",
            "should_work": False
        },
        {
            "name": "Connection timeout URL",
            "url": "https://httpstat.us/200?sleep=35000",  # 35s delay to test timeout
            "should_work": False
        }
    ]
    
    test_payload = {
        "job_id": "test_123",
        "status": "completed",
        "file_name": "test_audio.mp3",
        "transcription_text": "This is a test transcription.",
        "processing_time_seconds": 45.2
    }
    
    for i, test_case in enumerate(test_urls, 1):
        print(f"\n{i}. Testing: {test_case['name']}")
        print(f"   URL: {test_case['url']}")
        
        # Test URL detection
        is_n8n = is_n8n_resume_url(test_case['url'])
        print(f"   Detected as n8n URL: {is_n8n}")
        
        # Test connectivity
        print("   🔍 Testing connectivity...")
        try:
            connectivity_result = await test_webhook_connectivity(test_case['url'])
            print(f"   ✅ Connectivity test completed:")
            print(f"      - Reachable: {connectivity_result['reachable']}")
            print(f"      - Status: {connectivity_result['status_code']}")
            if connectivity_result['error']:
                print(f"      - Error: {connectivity_result['error']}")
        except Exception as e:
            print(f"   ❌ Connectivity test failed: {str(e)}")
        
        # Test actual webhook sending (with reduced timeout for faster testing)
        print("   📤 Testing webhook delivery...")
        try:
            start_time = datetime.now()
            success = await send_webhook(
                test_case['url'], 
                test_payload, 
                max_retries=2,  # Reduced for testing
                timeout=10,     # Short timeout for testing
                test_connectivity=False  # We already tested above
            )
            duration = (datetime.now() - start_time).total_seconds()
            
            status = "✅ SUCCESS" if success else "❌ FAILED"
            print(f"   {status} - Webhook delivery took {duration:.1f}s")
            
            if success != test_case['should_work']:
                print(f"   ⚠️  Unexpected result - expected {'success' if test_case['should_work'] else 'failure'}")
            
        except Exception as e:
            print(f"   💥 Exception during webhook test: {str(e)}")
        
        print("   " + "-" * 40)

async def test_n8n_url_patterns():
    """Test n8n URL pattern detection"""
    print("\n🎯 Testing n8n URL Pattern Detection")
    print("=" * 50)
    
    test_patterns = [
        "https://n8n.example.com/webhook/test",
        "https://app.n8n.cloud/webhook/abc123/resume",
        "https://my-n8n.com/api/v1/webhooks/execution-123",
        "https://workflow.company.com/executions/12345/resume",
        "https://regular-api.com/callback",
        "https://httpbin.org/post",
        "https://api.example.com/notifications"
    ]
    
    for url in test_patterns:
        is_n8n = is_n8n_resume_url(url)
        print(f"{'🟢' if is_n8n else '🔴'} {url} -> n8n URL: {is_n8n}")

async def main():
    """Run all webhook tests"""
    await test_n8n_url_patterns()
    await test_webhook_scenarios()
    
    print("\n🏁 Webhook testing completed!")
    print("\nKey improvements implemented:")
    print("- ✅ Comprehensive error logging with status codes and response details")
    print("- ✅ Retry logic with exponential backoff")
    print("- ✅ n8n URL pattern detection")
    print("- ✅ Connectivity pre-testing")
    print("- ✅ Timeout handling")
    print("- ✅ Webhook delivery status tracking")

if __name__ == "__main__":
    asyncio.run(main())