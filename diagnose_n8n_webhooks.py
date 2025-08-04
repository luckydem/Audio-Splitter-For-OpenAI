#!/usr/bin/env python3
"""
Diagnostic script for n8n webhook issues
Helps identify common problems with n8n webhook endpoints
"""

import asyncio
import json
import aiohttp
from datetime import datetime
from urllib.parse import urlparse, parse_qs

async def diagnose_n8n_webhook(webhook_url: str):
    """Comprehensive diagnosis of n8n webhook issues"""
    
    print(f"\n🔍 Diagnosing n8n Webhook: {webhook_url}")
    print("=" * 70)
    
    # Parse URL components
    parsed = urlparse(webhook_url)
    print(f"\n📍 URL Analysis:")
    print(f"   Scheme: {parsed.scheme}")
    print(f"   Host: {parsed.netloc}")
    print(f"   Path: {parsed.path}")
    
    # Check for common n8n patterns
    is_resume_url = any(pattern in webhook_url.lower() for pattern in ['/resume', '/executions/'])
    is_webhook_url = '/webhook' in webhook_url.lower()
    
    print(f"\n🎯 URL Type Detection:")
    print(f"   Is n8n webhook URL: {is_webhook_url}")
    print(f"   Is n8n resume URL: {is_resume_url}")
    
    if is_resume_url:
        print("\n⚠️  WARNING: This appears to be an n8n resume URL")
        print("   Resume URLs are temporary and expire after the workflow execution completes")
        print("   They're meant for immediate use and cannot be reused later")
    
    # Test various HTTP methods
    print(f"\n🧪 Testing HTTP Methods:")
    
    timeout_config = aiohttp.ClientTimeout(total=10, connect=5)
    
    async with aiohttp.ClientSession(timeout=timeout_config) as session:
        # Test HEAD request
        try:
            async with session.head(webhook_url, allow_redirects=False) as response:
                print(f"   HEAD: {response.status} - {response.reason}")
                if response.status == 405:
                    print("         (Method not allowed - endpoint exists)")
        except Exception as e:
            print(f"   HEAD: Failed - {str(e)}")
        
        # Test GET request
        try:
            async with session.get(webhook_url, allow_redirects=False) as response:
                print(f"   GET:  {response.status} - {response.reason}")
                if response.status == 405:
                    print("         (Method not allowed - webhook only accepts POST)")
                elif response.status == 404:
                    print("         ❌ Endpoint not found - URL may be invalid or expired")
                elif response.status == 200:
                    print("         ✅ Endpoint responds to GET")
        except Exception as e:
            print(f"   GET:  Failed - {str(e)}")
        
        # Test POST request with minimal payload
        try:
            test_payload = {"test": True, "timestamp": datetime.now().isoformat()}
            async with session.post(webhook_url, json=test_payload, allow_redirects=False) as response:
                print(f"   POST: {response.status} - {response.reason}")
                
                if response.status == 200:
                    print("         ✅ Webhook accepts POST requests")
                elif response.status == 404:
                    print("         ❌ Webhook URL not found - likely expired or invalid")
                elif response.status == 409:
                    print("         ⚠️  Conflict - workflow may already be running")
                elif response.status == 500:
                    print("         ❌ Server error - n8n may have internal issues")
                elif response.status in [301, 302, 307, 308]:
                    redirect_location = response.headers.get('Location', 'Not provided')
                    print(f"         ↗️  Redirects to: {redirect_location}")
                
                # Try to get response body for more details
                try:
                    response_text = await response.text()
                    if response_text and response.status != 200:
                        print(f"\n📄 Response Details:")
                        print(f"   {response_text[:500]}..." if len(response_text) > 500 else f"   {response_text}")
                except:
                    pass
                    
        except Exception as e:
            print(f"   POST: Failed - {str(e)}")
            if "ClientConnectorError" in str(type(e)):
                print("         ❌ Connection failed - check if n8n is running and accessible")
    
    # Provide recommendations
    print(f"\n💡 Recommendations:")
    
    if is_resume_url and any(status in str(locals()) for status in ['404', 'expired']):
        print("   1. Resume URLs expire after use. Get a fresh URL from n8n")
        print("   2. Consider using a webhook node instead of resume URLs for reliability")
        print("   3. Make sure to call the resume URL immediately after receiving it")
    
    if is_webhook_url:
        print("   1. Ensure the webhook is active in your n8n workflow")
        print("   2. Check if the workflow is enabled and not paused")
        print("   3. Verify the webhook path matches exactly (case-sensitive)")
    
    if parsed.scheme == 'http' and 'localhost' not in parsed.netloc:
        print("   ⚠️  Using HTTP instead of HTTPS - consider upgrading for security")
    
    print("\n✅ Diagnosis complete!")

async def test_webhook_delivery(webhook_url: str):
    """Test actual webhook delivery with a realistic payload"""
    
    print(f"\n📤 Testing Webhook Delivery: {webhook_url}")
    print("=" * 70)
    
    # Create a realistic payload
    payload = {
        "job_id": f"diagnostic_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "status": "completed",
        "file_name": "diagnostic_test.mp3",
        "file_size_mb": 10.5,
        "transcription_text": "This is a diagnostic test from the n8n webhook diagnostic tool.",
        "total_duration_seconds": 60.0,
        "processing_method": "direct_transcription",
        "chunks_processed": 1,
        "processing_time_seconds": 15.2,
        "transcription_url": "https://example.com/diagnostic-test.txt",
        "webhook_delivered": None
    }
    
    print(f"📦 Payload size: {len(json.dumps(payload))} bytes")
    
    timeout_config = aiohttp.ClientTimeout(total=30, connect=10)
    
    try:
        async with aiohttp.ClientSession(timeout=timeout_config) as session:
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'n8n-Webhook-Diagnostic/1.0'
            }
            
            print(f"🚀 Sending POST request...")
            start_time = datetime.now()
            
            async with session.post(webhook_url, json=payload, headers=headers) as response:
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                
                print(f"\n📊 Response:")
                print(f"   Status: {response.status} - {response.reason}")
                print(f"   Duration: {duration:.2f}s")
                print(f"   Headers: {dict(response.headers)}")
                
                response_text = await response.text()
                if response_text:
                    print(f"\n📄 Response Body:")
                    try:
                        # Try to parse as JSON for pretty printing
                        response_json = json.loads(response_text)
                        print(json.dumps(response_json, indent=2)[:1000])
                    except:
                        print(response_text[:1000])
                
                if response.status == 200:
                    print("\n✅ Webhook delivery successful!")
                    return True
                else:
                    print(f"\n❌ Webhook delivery failed with status {response.status}")
                    return False
                    
    except asyncio.TimeoutError:
        print(f"\n❌ Request timed out after 30 seconds")
        return False
    except Exception as e:
        print(f"\n❌ Request failed: {type(e).__name__}: {str(e)}")
        return False

async def main():
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python diagnose_n8n_webhooks.py <webhook_url> [--test-delivery]")
        print("\nExamples:")
        print("  python diagnose_n8n_webhooks.py https://n8n.example.com/webhook/abc123")
        print("  python diagnose_n8n_webhooks.py https://n8n.example.com/webhook/abc123 --test-delivery")
        sys.exit(1)
    
    webhook_url = sys.argv[1]
    test_delivery = "--test-delivery" in sys.argv
    
    # Run diagnosis
    await diagnose_n8n_webhook(webhook_url)
    
    # Optionally test delivery
    if test_delivery:
        await test_webhook_delivery(webhook_url)

if __name__ == "__main__":
    asyncio.run(main())