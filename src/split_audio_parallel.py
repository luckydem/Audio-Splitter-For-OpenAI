#!/usr/bin/env python3
"""
Parallel audio splitter for faster processing on multi-core systems
"""
import os
import subprocess
import concurrent.futures
import time
from datetime import datetime
import logging
from pathlib import Path
import multiprocessing

def process_chunk(args):
    """
    Process a single chunk - designed to be run in parallel
    """
    input_file, chunk_num, start_time, duration, output_path, total_chunks = args
    
    logger = logging.getLogger(f'chunk_{chunk_num}')
    
    cmd = [
        'ffmpeg',
        '-y',
        '-ss', str(start_time),  # Input seeking (fast)
        '-i', input_file,
        '-t', str(duration),
        '-vn',
        '-c:a', 'pcm_s16le',  # 16-bit PCM
        '-ar', '16000',       # 16kHz for speech (Whisper native)
        '-ac', '1',           # Mono for speech transcription
        '-loglevel', 'error',  # Reduce ffmpeg verbosity
        output_path
    ]
    
    start = time.time()
    logger.info(f"[CHUNK {chunk_num}/{total_chunks}] Starting at position {start_time:.2f}s")
    
    try:
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            stdin=subprocess.DEVNULL,
            timeout=300
        )
        
        elapsed = time.time() - start
        
        if result.returncode == 0:
            file_size = os.path.getsize(output_path) / (1024 * 1024)
            logger.info(f"[CHUNK {chunk_num}/{total_chunks}] SUCCESS: {file_size:.1f} MB in {elapsed:.2f}s")
            return (chunk_num, True, output_path, elapsed)
        else:
            logger.error(f"[CHUNK {chunk_num}/{total_chunks}] FAILED after {elapsed:.2f}s: {result.stderr}")
            return (chunk_num, False, None, elapsed)
            
    except subprocess.TimeoutExpired:
        logger.error(f"[CHUNK {chunk_num}/{total_chunks}] TIMEOUT after 300s")
        return (chunk_num, False, None, 300)
    except Exception as e:
        logger.error(f"[CHUNK {chunk_num}/{total_chunks}] ERROR: {str(e)}")
        return (chunk_num, False, None, 0)

def split_audio_parallel(input_file, chunk_duration, output_dir, num_chunks, total_duration, 
                        max_workers=None, logger=None):
    """
    Split audio file into chunks using parallel processing
    """
    if not logger:
        logger = logging.getLogger('audio_splitter')
    
    # Determine optimal number of workers
    if max_workers is None:
        # Use CPU count but leave some headroom
        max_workers = min(multiprocessing.cpu_count() - 1, num_chunks, 8)
    
    logger.info(f"Starting parallel processing with {max_workers} workers for {num_chunks} chunks")
    
    # Prepare all chunk arguments
    chunk_args = []
    for i in range(num_chunks):
        start_time = i * chunk_duration
        
        # For the last chunk, adjust duration
        if i == num_chunks - 1:
            actual_duration = total_duration - start_time
        else:
            actual_duration = chunk_duration
            
        output_path = os.path.join(output_dir, f'chunk_{i+1:03d}.wav')
        
        # Print for n8n compatibility
        print(f"Exporting {output_path}")
        
        chunk_args.append((
            input_file,
            i + 1,
            start_time,
            actual_duration,
            output_path,
            num_chunks
        ))
    
    # Process chunks in parallel
    successfully_created = []
    start_time = time.time()
    
    with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
        # Submit all jobs
        future_to_chunk = {executor.submit(process_chunk, args): args[1] for args in chunk_args}
        
        # Process completed chunks as they finish
        for future in concurrent.futures.as_completed(future_to_chunk):
            chunk_num, success, output_path, elapsed = future.result()
            
            if success:
                successfully_created.append(output_path)
                logger.info(f"Chunk {chunk_num} completed successfully")
            else:
                logger.error(f"Chunk {chunk_num} failed")
    
    total_elapsed = time.time() - start_time
    logger.info(f"Parallel processing completed: {len(successfully_created)}/{num_chunks} chunks in {total_elapsed:.2f}s")
    logger.info(f"Average time per chunk: {total_elapsed/max(len(successfully_created), 1):.2f}s")
    logger.info(f"Theoretical sequential time: {total_elapsed * max_workers:.2f}s")
    logger.info(f"Speedup factor: {(total_elapsed * max_workers) / total_elapsed:.1f}x")
    
    return successfully_created

# Add this function to split_audio.py to enable parallel mode
def split_audio_with_parallel_option(input_file, chunk_duration, output_dir, output_format='wav', 
                                   quality='medium', verbose=False, logger=None, stream_mode=False,
                                   parallel=False, max_workers=None):
    """
    Wrapper to use either sequential or parallel processing
    """
    if not logger:
        logger = logging.getLogger('audio_splitter')
    
    # Get audio info
    from split_audio import get_audio_info
    duration, bitrate, codec_name = get_audio_info(input_file)
    num_chunks = math.ceil(duration / chunk_duration)
    
    if parallel and output_format == 'wav':
        # Use parallel processing for WAV format (which is what we're using)
        logger.info(f"Using PARALLEL processing for {num_chunks} chunks")
        return split_audio_parallel(input_file, chunk_duration, output_dir, 
                                  num_chunks, duration, max_workers, logger)
    else:
        # Fall back to sequential processing
        logger.info(f"Using SEQUENTIAL processing for {num_chunks} chunks")
        from split_audio import split_audio
        return split_audio(input_file, chunk_duration, output_dir, output_format, 
                         quality, verbose, logger, stream_mode)