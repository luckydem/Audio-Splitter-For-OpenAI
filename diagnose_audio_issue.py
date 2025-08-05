#!/usr/bin/env python3
"""
Diagnose audio processing issues by testing different approaches
"""
import subprocess
import time
import sys
import os
import ffmpeg

def get_audio_info(filepath):
    """Get audio file information"""
    try:
        probe = ffmpeg.probe(filepath)
        format_info = probe['format']
        duration = float(format_info['duration'])
        
        audio_stream = next((stream for stream in probe['streams'] 
                            if stream['codec_type'] == 'audio'), None)
        
        print(f"Audio Info:")
        print(f"- Duration: {duration:.2f}s ({duration/60:.1f} minutes)")
        print(f"- Codec: {audio_stream['codec_name']}")
        print(f"- Sample Rate: {audio_stream.get('sample_rate', 'unknown')}")
        print(f"- Channels: {audio_stream.get('channels', 'unknown')}")
        print(f"- Bitrate: {format_info.get('bit_rate', 'unknown')}")
        print()
        
        return duration
    except Exception as e:
        print(f"Error getting audio info: {e}")
        return None

def test_seeking_methods(input_file):
    """Test different seeking methods"""
    
    # Test cases around chunk 12's position
    test_positions = [
        3200,  # Just before chunk 12
        3244,  # Chunk 12 start
        3300,  # Middle of chunk 12  
        3500,  # End of chunk 12
    ]
    
    for position in test_positions:
        print(f"\n--- Testing position {position}s ---")
        
        # Method 1: Input seeking (-ss before -i)
        print("Method 1: Input seeking (-ss before -i)")
        cmd1 = [
            'ffmpeg', '-y',
            '-ss', str(position),
            '-i', input_file,
            '-t', '10',  # Just 10 seconds
            '-vn',
            '-c:a', 'pcm_s16le',
            '-ar', '16000',
            '-ac', '1',
            f'/tmp/test_seek_input_{position}.wav'
        ]
        
        start = time.time()
        try:
            result = subprocess.run(cmd1, capture_output=True, text=True, 
                                  stdin=subprocess.DEVNULL, timeout=10)
            elapsed = time.time() - start
            if result.returncode == 0:
                print(f"  SUCCESS in {elapsed:.2f}s")
            else:
                print(f"  FAILED in {elapsed:.2f}s: {result.stderr[:200]}")
        except subprocess.TimeoutExpired:
            print(f"  TIMEOUT after 10s")
        
        # Method 2: Output seeking (-ss after -i)
        print("Method 2: Output seeking (-ss after -i)")
        cmd2 = [
            'ffmpeg', '-y',
            '-i', input_file,
            '-ss', str(position),
            '-t', '10',
            '-vn',
            '-c:a', 'pcm_s16le',
            '-ar', '16000',
            '-ac', '1',
            f'/tmp/test_seek_output_{position}.wav'
        ]
        
        start = time.time()
        try:
            result = subprocess.run(cmd2, capture_output=True, text=True,
                                  stdin=subprocess.DEVNULL, timeout=10)
            elapsed = time.time() - start
            if result.returncode == 0:
                print(f"  SUCCESS in {elapsed:.2f}s")
            else:
                print(f"  FAILED in {elapsed:.2f}s: {result.stderr[:200]}")
        except subprocess.TimeoutExpired:
            print(f"  TIMEOUT after 10s")

def test_different_durations(input_file):
    """Test if the issue is with the duration"""
    print("\n--- Testing different chunk durations at position 3244s ---")
    
    durations = [10, 30, 60, 120, 180, 240, 294.912]
    
    for duration in durations:
        print(f"\nTesting duration: {duration}s")
        cmd = [
            'ffmpeg', '-y',
            '-i', input_file,
            '-ss', '3244.032',
            '-t', str(duration),
            '-vn',
            '-c:a', 'pcm_s16le',
            '-ar', '16000',
            '-ac', '1',
            f'/tmp/test_duration_{duration}.wav'
        ]
        
        start = time.time()
        try:
            result = subprocess.run(cmd, capture_output=True, text=True,
                                  stdin=subprocess.DEVNULL, timeout=30)
            elapsed = time.time() - start
            if result.returncode == 0:
                size_mb = os.path.getsize(f'/tmp/test_duration_{duration}.wav') / (1024*1024)
                print(f"  SUCCESS: {size_mb:.1f}MB in {elapsed:.2f}s")
            else:
                print(f"  FAILED in {elapsed:.2f}s")
        except subprocess.TimeoutExpired:
            print(f"  TIMEOUT after 30s - Issue confirmed at duration {duration}s")
            break

def main():
    if len(sys.argv) < 2:
        print("Usage: python diagnose_audio_issue.py <input_audio_file>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    
    print(f"Diagnosing audio processing issues for: {input_file}")
    print("="*60)
    
    # Get audio info
    duration = get_audio_info(input_file)
    
    if duration and 3244 + 294 > duration:
        print(f"WARNING: Chunk 12 extends beyond file duration!")
        print(f"Chunk 12 would end at {3244 + 294}s but file is only {duration}s")
        print()
    
    # Run tests
    test_seeking_methods(input_file)
    test_different_durations(input_file)

if __name__ == "__main__":
    main()