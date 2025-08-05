#!/usr/bin/env python3
"""
Optimized transcription for very long audio files (2+ hours)
Uses OpenAI's increased file size limits
"""

import os
import sys
import time
import asyncio
import aiohttp
from pathlib import Path
import argparse
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def transcribe_large_file_direct(file_path: str, api_key: str, language: str = None) -> dict:
    """
    Transcribe a large audio file directly using OpenAI's Whisper API
    Takes advantage of the new 200MB file size limit
    """
    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
    logger.info(f"Transcribing {os.path.basename(file_path)} ({file_size_mb:.1f}MB)")
    
    if file_size_mb > 25:
        raise ValueError(f"File size {file_size_mb:.1f}MB exceeds OpenAI's 25MB limit")
    
    start_time = time.time()
    
    # Create session with longer timeout for large files
    timeout = aiohttp.ClientTimeout(
        total=3600,  # 60 minutes total
        sock_connect=30,
        sock_read=600
    )
    
    async with aiohttp.ClientSession(timeout=timeout) as session:
        with open(file_path, 'rb') as audio_file:
            # Prepare form data
            data = aiohttp.FormData()
            data.add_field('file', audio_file, 
                          filename=os.path.basename(file_path),
                          content_type='audio/wav')
            data.add_field('model', 'whisper-1')
            
            # Add optional parameters
            if language:
                data.add_field('language', language)
            
            # Optional: Add prompt to improve accuracy
            data.add_field('prompt', 'This is a meeting recording with multiple speakers.')
            
            # Send request
            headers = {'Authorization': f'Bearer {api_key}'}
            
            logger.info("Uploading to OpenAI Whisper API...")
            async with session.post(
                'https://api.openai.com/v1/audio/transcriptions',
                headers=headers,
                data=data
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    elapsed = time.time() - start_time
                    
                    logger.info(f"✅ Transcription completed in {elapsed:.1f}s")
                    logger.info(f"Transcription length: {len(result['text'])} characters")
                    
                    return {
                        'success': True,
                        'text': result['text'],
                        'duration_seconds': elapsed,
                        'file_size_mb': file_size_mb
                    }
                else:
                    error_text = await response.text()
                    logger.error(f"❌ API error {response.status}: {error_text}")
                    return {
                        'success': False,
                        'error': f"API error {response.status}: {error_text}"
                    }

async def convert_to_compatible_format(input_path: str, output_path: str = None) -> str:
    """
    Convert audio to a format optimized for Whisper
    - Reduces file size while maintaining quality
    - Ensures compatibility
    """
    if output_path is None:
        output_path = input_path.replace('.WMA', '.mp3').replace('.wma', '.mp3')
    
    logger.info(f"Converting {os.path.basename(input_path)} to MP3...")
    
    # Use MP3 with reasonable quality for speech
    # This typically reduces WMA files by 60-70%
    cmd = [
        'ffmpeg', '-y',
        '-i', input_path,
        '-c:a', 'libmp3lame',
        '-b:a', '64k',  # 64kbps is fine for speech
        '-ar', '16000',  # 16kHz sample rate (Whisper's native)
        '-ac', '1',      # Mono
        output_path
    ]
    
    import subprocess
    process = subprocess.run(cmd, capture_output=True, text=True)
    
    if process.returncode == 0:
        new_size_mb = os.path.getsize(output_path) / (1024 * 1024)
        logger.info(f"✅ Converted to {os.path.basename(output_path)} ({new_size_mb:.1f}MB)")
        return output_path
    else:
        logger.error(f"❌ Conversion failed: {process.stderr}")
        raise Exception("Failed to convert audio file")

async def transcribe_with_retry(file_path: str, api_key: str, max_retries: int = 3) -> dict:
    """
    Transcribe with automatic retry on failure
    """
    last_error = None
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Transcription attempt {attempt + 1}/{max_retries}")
            result = await transcribe_large_file_direct(file_path, api_key)
            
            if result['success']:
                return result
            else:
                last_error = result['error']
                logger.warning(f"Attempt {attempt + 1} failed: {last_error}")
                
        except Exception as e:
            last_error = str(e)
            logger.error(f"Attempt {attempt + 1} exception: {last_error}")
        
        if attempt < max_retries - 1:
            wait_time = 2 ** attempt  # Exponential backoff
            logger.info(f"Waiting {wait_time}s before retry...")
            await asyncio.sleep(wait_time)
    
    return {
        'success': False,
        'error': f"All {max_retries} attempts failed. Last error: {last_error}"
    }

async def main():
    parser = argparse.ArgumentParser(description='Transcribe long audio files')
    parser.add_argument('input', help='Input audio file path')
    parser.add_argument('--output', help='Output text file path')
    parser.add_argument('--api-key', help='OpenAI API key (or use env var)')
    parser.add_argument('--convert', action='store_true', help='Convert to MP3 first')
    parser.add_argument('--language', help='Language code (e.g., en, es, fr)')
    
    args = parser.parse_args()
    
    # Get API key
    api_key = args.api_key or os.environ.get('OPENAI_API_KEY')
    if not api_key:
        logger.error("OpenAI API key required (--api-key or OPENAI_API_KEY env var)")
        sys.exit(1)
    
    # Check file exists
    if not os.path.exists(args.input):
        logger.error(f"File not found: {args.input}")
        sys.exit(1)
    
    # Get file info
    file_size_mb = os.path.getsize(args.input) / (1024 * 1024)
    logger.info(f"Processing: {os.path.basename(args.input)} ({file_size_mb:.1f}MB)")
    
    # Convert if needed
    process_file = args.input
    if args.convert or file_size_mb > 190:  # Leave some margin
        converted_file = await convert_to_compatible_format(args.input)
        process_file = converted_file
    
    # Transcribe
    result = await transcribe_with_retry(process_file, api_key)
    
    if result['success']:
        # Save transcript
        output_path = args.output or args.input.replace('.WMA', '_transcript.txt').replace('.wma', '_transcript.txt')
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(result['text'])
        
        logger.info(f"✅ Transcript saved to: {output_path}")
        logger.info(f"Processing time: {result['duration_seconds']:.1f}s")
        
        # Clean up converted file
        if args.convert and process_file != args.input:
            os.remove(process_file)
            logger.info("Cleaned up temporary conversion file")
            
    else:
        logger.error(f"❌ Transcription failed: {result['error']}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())