#!/usr/bin/env python3
"""
Quick test for n8n webhook in test mode
Run this IMMEDIATELY after clicking "Test workflow" in n8n
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

async def quick_test():
    webhook_url = "https://n8n.e-bud.app/webhook-test/split-and-transcribe-completed"
    
    # Minimal payload for quick test
    payload = {
        "status": "test",
        "message": "Quick test after clicking Test workflow button"
    }
    
    print("🚀 Testing webhook IMMEDIATELY after Test workflow click...")
    print(f"📍 URL: {webhook_url}")
    
    success = await send_webhook(
        webhook_url,
        payload,
        max_retries=1,
        timeout=10,
        test_connectivity=False
    )
    
    if success:
        print("✅ SUCCESS! Webhook worked in test mode")
    else:
        print("❌ Failed - you may need to click 'Test workflow' first")
    
    return success

if __name__ == "__main__":
    asyncio.run(quick_test())