#!/usr/bin/env python3
"""
Check if chunk boundaries are within file duration
"""
import sys

def check_boundaries():
    # From the logs
    total_duration = 5270.51  # seconds
    chunk_duration = 294.912  # seconds
    num_chunks = 18
    
    print("Audio file analysis:")
    print(f"Total duration: {total_duration:.2f}s ({total_duration/60:.1f} minutes)")
    print(f"Chunk duration: {chunk_duration:.2f}s")
    print(f"Number of chunks: {num_chunks}")
    print()
    
    print("Chunk boundaries:")
    for i in range(num_chunks):
        start = i * chunk_duration
        if i == num_chunks - 1:
            # Last chunk
            actual_duration = total_duration - start
        else:
            actual_duration = chunk_duration
        
        end = start + actual_duration
        
        status = "OK" if end <= total_duration else "EXCEEDS FILE DURATION!"
        
        print(f"Chunk {i+1:2d}: {start:7.2f}s - {end:7.2f}s (duration: {actual_duration:6.2f}s) {status}")
        
        if i == 11:  # Chunk 12 (0-indexed)
            print(f"         ^ This is where it hung!")

if __name__ == "__main__":
    check_boundaries()