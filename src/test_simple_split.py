#!/usr/bin/env python3
"""
Simple test script to verify basic ffmpeg splitting works
"""
import subprocess
import time
import os
import sys

def simple_split_test(input_file, output_dir):
    """Test basic ffmpeg splitting without all the complexity"""
    print(f"Testing simple split of: {input_file}")
    
    # Create a simple 30-second chunk
    output_file = os.path.join(output_dir, "test_chunk.wav")
    
    cmd = [
        'ffmpeg',
        '-y',
        '-i', input_file,
        '-ss', '0',
        '-t', '30',
        '-vn',
        '-c:a', 'pcm_s16le',
        '-ar', '16000',
        '-ac', '1',
        output_file
    ]
    
    print(f"Command: {' '.join(cmd)}")
    
    start_time = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    duration = time.time() - start_time
    
    if result.returncode == 0:
        size_mb = os.path.getsize(output_file) / (1024 * 1024)
        print(f"SUCCESS: Created {size_mb:.1f}MB chunk in {duration:.2f} seconds")
    else:
        print(f"FAILED: {result.stderr}")
    
    return result.returncode == 0

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python test_simple_split.py <input_file> <output_dir>")
        sys.exit(1)
    
    simple_split_test(sys.argv[1], sys.argv[2])