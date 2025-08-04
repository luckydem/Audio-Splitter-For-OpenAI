#!/usr/bin/env python3
"""
Test resume URL patterns to understand n8n execution URLs
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

try:
    from audio_splitter_drive import test_webhook_connectivity, is_n8n_resume_url
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)

async def test_resume_url_patterns():
    """Test various n8n resume URL patterns"""
    
    print("🧪 Testing n8n Resume URL Patterns")
    print("=" * 50)
    
    # Example resume URL patterns
    test_urls = [
        "https://n8n.e-bud.app/webhook/12345/transcription-complete",
        "https://n8n.e-bud.app/webhook/abc123def456/transcription-complete", 
        "https://n8n.e-bud.app/webhook/execution-123/resume",
        "https://n8n.e-bud.app/webhook-test/b408dc18-59f6-46c3-b231-f6390d72155a"  # Your static webhook
    ]
    
    for url in test_urls:
        print(f"\n📍 Testing: {url}")
        print(f"   Is n8n resume URL: {is_n8n_resume_url(url)}")
        
        # Test connectivity (but don't expect them to work since they're examples)
        connectivity = await test_webhook_connectivity(url)
        print(f"   Status: {connectivity.get('status_code', 'N/A')}")
        if connectivity.get('error'):
            print(f"   Expected error: {connectivity['error'][:50]}...")

if __name__ == "__main__":
    asyncio.run(test_resume_url_patterns())