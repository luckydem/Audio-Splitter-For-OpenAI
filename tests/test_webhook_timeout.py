#!/usr/bin/env python3
"""
Test n8n webhook timeout behavior
Simulates the timing of a real audio transcription job
"""

import asyncio
import json
import sys
import os
from datetime import datetime
import time

# Add the current directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

try:
    from audio_splitter_drive import send_webhook, test_webhook_connectivity
except ImportError as e:
    print(f"Import error: {e}")
    print("Please run: source .venv/bin/activate && pip install -r requirements-production.txt")
    sys.exit(1)

async def simulate_transcription_timing(webhook_url: str, delay_seconds: int = 180):
    """Simulate the timing of a real transcription job"""
    
    print(f"🧪 Webhook Timeout Test")
    print(f"📍 URL: {webhook_url}")
    print(f"⏱️  Simulating {delay_seconds}s processing delay (typical for transcription)")
    print("=" * 70)
    
    # Test immediate connectivity
    print("\n1️⃣ Testing immediate connectivity...")
    connectivity = await test_webhook_connectivity(webhook_url)
    print(f"   Reachable: {connectivity['reachable']}")
    print(f"   Status: {connectivity['status_code']}")
    
    if not connectivity['reachable']:
        print("   ❌ Webhook not reachable at start - check URL")
        return False
    
    # Simulate processing delay
    print(f"\n2️⃣ Simulating {delay_seconds}s transcription processing...")
    print("   Progress: ", end="", flush=True)
    
    for i in range(10):
        await asyncio.sleep(delay_seconds / 10)
        print(f"{(i+1)*10}%.. ", end="", flush=True)
    
    print("\n   ✅ Processing complete")
    
    # Test connectivity after delay
    print(f"\n3️⃣ Testing connectivity after {delay_seconds}s delay...")
    connectivity_after = await test_webhook_connectivity(webhook_url)
    print(f"   Reachable: {connectivity_after['reachable']}")
    print(f"   Status: {connectivity_after['status_code']}")
    
    # Try to send webhook
    print("\n4️⃣ Attempting to send webhook with results...")
    test_payload = {
        "job_id": f"timeout_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "status": "completed",
        "file_name": "test_audio.mp3",
        "transcription_text": f"Test completed after {delay_seconds}s delay",
        "processing_time_seconds": delay_seconds,
        "test_type": "timeout_simulation"
    }
    
    success = await send_webhook(
        webhook_url,
        test_payload,
        max_retries=1,
        timeout=10,
        test_connectivity=False
    )
    
    print("\n📊 Results:")
    print(f"   Initial connectivity: {'✅' if connectivity['reachable'] else '❌'}")
    print(f"   After {delay_seconds}s: {'✅' if connectivity_after['reachable'] else '❌'}")
    print(f"   Webhook delivery: {'✅ SUCCESS' if success else '❌ FAILED'}")
    
    if connectivity['reachable'] and not connectivity_after['reachable']:
        print("\n⚠️  TIMEOUT DETECTED: Webhook URL expired during processing!")
        print("   Solution: Increase n8n workflow timeout to at least 10 minutes")
    
    return success

async def test_multiple_delays(webhook_url: str):
    """Test with different delay periods"""
    delays = [30, 120, 240]  # 30s, 2min, 4min
    
    print("🧪 Testing webhook with multiple delay periods")
    print("=" * 70)
    
    for delay in delays:
        print(f"\n📍 Test with {delay}s delay")
        print("-" * 50)
        success = await simulate_transcription_timing(webhook_url, delay)
        
        if not success and delay < delays[-1]:
            print("\n⏸️  Webhook failed. Continue with longer delay? (y/n): ", end="")
            # For automated testing, we'll continue
            print("y (automated)")
            await asyncio.sleep(5)  # Brief pause between tests

async def main():
    if len(sys.argv) < 2:
        print("Usage: python test_webhook_timeout.py <webhook_url> [delay_seconds]")
        print("\nExamples:")
        print("  python test_webhook_timeout.py https://n8n.example.com/webhook/abc123")
        print("  python test_webhook_timeout.py https://n8n.example.com/webhook/abc123 240")
        print("\nTo test multiple delays:")
        print("  python test_webhook_timeout.py https://n8n.example.com/webhook/abc123 --multiple")
        sys.exit(1)
    
    webhook_url = sys.argv[1]
    
    if len(sys.argv) > 2 and sys.argv[2] == "--multiple":
        await test_multiple_delays(webhook_url)
    else:
        delay = int(sys.argv[2]) if len(sys.argv) > 2 else 180
        await simulate_transcription_timing(webhook_url, delay)

if __name__ == "__main__":
    asyncio.run(main())