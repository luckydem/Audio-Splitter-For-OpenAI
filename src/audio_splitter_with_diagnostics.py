#!/usr/bin/env python3
"""
Enhanced audio splitter with better diagnostics and error handling
"""
import os
import subprocess
import signal
import threading
import time
from datetime import datetime

class FFmpegTimeout(Exception):
    pass

def run_ffmpeg_with_monitoring(cmd, timeout=300, logger=None):
    """
    Run ffmpeg with monitoring and better timeout handling
    """
    process = None
    output_lines = []
    error_lines = []
    
    def target():
        nonlocal process, output_lines, error_lines
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            text=True
        )
        
        # Read output in real-time
        for line in process.stderr:
            error_lines.append(line.strip())
            if logger and len(error_lines) % 10 == 0:
                # Log progress every 10 lines
                logger.debug(f"FFmpeg progress: {line.strip()}")
        
        stdout, _ = process.communicate()
        if stdout:
            output_lines = stdout.strip().split('\n')
    
    thread = threading.Thread(target=target)
    thread.start()
    thread.join(timeout)
    
    if thread.is_alive():
        # Timeout occurred
        if logger:
            logger.error(f"FFmpeg timeout after {timeout}s. Last 10 stderr lines:")
            for line in error_lines[-10:]:
                logger.error(f"  {line}")
        
        # Try graceful termination first
        if process:
            process.terminate()
            thread.join(5)  # Wait 5s for graceful shutdown
            
            if thread.is_alive():
                # Force kill if still running
                process.kill()
                thread.join()
        
        raise FFmpegTimeout(f"FFmpeg timed out after {timeout} seconds")
    
    return process.returncode, '\n'.join(output_lines), '\n'.join(error_lines)

def split_audio_with_diagnostics(input_file, chunk_number, start_time, duration, 
                                output_path, logger=None):
    """
    Split audio with enhanced diagnostics
    """
    # Try input seeking first (faster)
    cmd_input_seek = [
        'ffmpeg',
        '-y',
        '-ss', str(start_time),  # Seek before input (fast seek)
        '-i', input_file,
        '-t', str(duration),
        '-vn',
        '-c:a', 'pcm_s16le',
        '-ar', '16000',
        '-ac', '1',
        output_path
    ]
    
    if logger:
        logger.info(f"[CHUNK {chunk_number}] Attempting fast seek method")
        logger.debug(f"[CHUNK {chunk_number}] Command: {' '.join(cmd_input_seek)}")
    
    try:
        start = time.time()
        returncode, stdout, stderr = run_ffmpeg_with_monitoring(
            cmd_input_seek, 
            timeout=min(duration * 2, 300),  # Timeout based on duration, max 300s
            logger=logger
        )
        elapsed = time.time() - start
        
        if returncode == 0:
            file_size = os.path.getsize(output_path) / (1024 * 1024)
            if logger:
                logger.info(f"[CHUNK {chunk_number}] SUCCESS with fast seek: {file_size:.1f}MB in {elapsed:.2f}s")
            return True
        else:
            if logger:
                logger.warning(f"[CHUNK {chunk_number}] Fast seek failed, trying accurate seek")
                
    except FFmpegTimeout:
        if logger:
            logger.warning(f"[CHUNK {chunk_number}] Fast seek timed out, trying accurate seek")
    
    # Fallback to output seeking (more accurate but slower)
    cmd_output_seek = [
        'ffmpeg',
        '-y',
        '-i', input_file,
        '-ss', str(start_time),  # Seek after input (accurate seek)
        '-t', str(duration),
        '-vn',
        '-c:a', 'pcm_s16le',
        '-ar', '16000',
        '-ac', '1',
        '-v', 'warning',  # Less verbose output
        output_path
    ]
    
    if logger:
        logger.info(f"[CHUNK {chunk_number}] Attempting accurate seek method")
    
    try:
        start = time.time()
        returncode, stdout, stderr = run_ffmpeg_with_monitoring(
            cmd_output_seek,
            timeout=min(duration * 3, 300),  # More time for accurate seek
            logger=logger
        )
        elapsed = time.time() - start
        
        if returncode == 0:
            file_size = os.path.getsize(output_path) / (1024 * 1024)
            if logger:
                logger.info(f"[CHUNK {chunk_number}] SUCCESS with accurate seek: {file_size:.1f}MB in {elapsed:.2f}s")
            return True
        else:
            if logger:
                logger.error(f"[CHUNK {chunk_number}] Both seek methods failed")
                logger.error(f"[CHUNK {chunk_number}] Error: {stderr[-500:]}")
            return False
            
    except FFmpegTimeout as e:
        if logger:
            logger.error(f"[CHUNK {chunk_number}] {str(e)}")
        return False

# Additional diagnostic function
def test_specific_timestamp(input_file, timestamp, logger=None):
    """
    Test if a specific timestamp can be accessed
    """
    test_output = f"/tmp/test_timestamp_{timestamp}.wav"
    
    # Try a very short duration first
    cmd = [
        'ffmpeg',
        '-y',
        '-ss', str(timestamp),
        '-i', input_file,
        '-t', '1',  # Just 1 second
        '-vn',
        '-c:a', 'pcm_s16le',
        '-ar', '16000',
        '-ac', '1',
        test_output
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, 
                              stdin=subprocess.DEVNULL, timeout=10)
        if result.returncode == 0:
            os.remove(test_output)
            return True
        else:
            if logger:
                logger.debug(f"Cannot seek to {timestamp}s: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        if logger:
            logger.debug(f"Timeout seeking to {timestamp}s")
        return False
    except Exception as e:
        if logger:
            logger.debug(f"Error seeking to {timestamp}s: {e}")
        return False