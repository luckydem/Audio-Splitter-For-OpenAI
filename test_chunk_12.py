#!/usr/bin/env python3
"""
Test script to reproduce chunk 12 processing issue
"""
import subprocess
import time
import sys
import os

def test_chunk_12():
    """
    Test the specific ffmpeg command that hung on chunk 12
    Based on logs: start_time=3244.032, duration=294.91200000000003
    """
    
    if len(sys.argv) < 2:
        print("Usage: python test_chunk_12.py <input_audio_file>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = "/tmp/test_chunk_12.wav"
    
    # The exact command from the logs
    cmd = [
        'ffmpeg',
        '-y',
        '-i', input_file,
        '-ss', '3244.032',  # Start time for chunk 12
        '-t', '294.912',     # Duration
        '-vn',
        '-c:a', 'pcm_s16le',
        '-ar', '16000',
        '-ac', '1',
        output_file
    ]
    
    print(f"Testing ffmpeg command for chunk 12...")
    print(f"Command: {' '.join(cmd)}")
    print(f"This extracts audio from {3244.032}s to {3244.032 + 294.912}s")
    print()
    
    start_time = time.time()
    
    try:
        # Run with a shorter timeout to test
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            timeout=30  # 30 second timeout for testing
        )
        
        elapsed = time.time() - start_time
        
        if result.returncode == 0:
            size_mb = os.path.getsize(output_file) / (1024 * 1024)
            print(f"SUCCESS: Created {size_mb:.1f}MB file in {elapsed:.2f}s")
        else:
            print(f"FAILED after {elapsed:.2f}s")
            print(f"Error: {result.stderr}")
            
    except subprocess.TimeoutExpired:
        elapsed = time.time() - start_time
        print(f"TIMEOUT: Command timed out after {elapsed:.2f}s")
        print("This confirms the hanging issue with chunk 12")
        
        # Try to get more info
        print("\nTrying with verbose ffmpeg output...")
        cmd_verbose = cmd[:-1] + ['-v', 'debug', output_file]
        
        try:
            result = subprocess.run(
                cmd_verbose,
                capture_output=True,
                text=True,
                stdin=subprocess.DEVNULL,
                timeout=10
            )
        except subprocess.TimeoutExpired:
            print("Verbose mode also timed out")
        else:
            print("Verbose output:", result.stderr[-1000:])  # Last 1000 chars
    
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_chunk_12()