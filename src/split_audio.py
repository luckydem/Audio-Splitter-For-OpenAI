#!/usr/bin/env python3
"""
Audio File Splitter for OpenAI Transcription

This script splits large audio files into smaller chunks suitable for OpenAI's 
transcription API, which has file size limitations. It automatically handles 
various audio formats including WMA and outputs to MP3 format for optimal 
compatibility with OpenAI's services.

Key features:
- Splits audio files based on file size limits (default 20MB)
- Supports multiple input formats (MP3, WAV, FLAC, OGG, M4A, WMA, etc.)
- Outputs to MP3 format by default for maximum compatibility
- Preserves audio quality while optimizing file size
"""

import os
import math
import subprocess
import argparse
import ffmpeg
import sys
from pathlib import Path
import logging
from datetime import datetime
import json

def get_audio_info(filepath):
    """
    Get duration, bitrate and codec information of the audio file using ffmpeg.probe
    """
    probe = ffmpeg.probe(filepath)
    format_info = probe['format']
    duration = float(format_info['duration'])  # in seconds
    bitrate = float(format_info['bit_rate'])   # in bits per second
    
    # Find the audio stream
    audio_stream = next((stream for stream in probe['streams'] 
                        if stream['codec_type'] == 'audio'), None)
    
    if not audio_stream:
        raise ValueError("No audio stream found in the file")
    
    codec_name = audio_stream['codec_name']
    return duration, bitrate, codec_name

def calculate_chunk_duration(bitrate_bps, max_mb, output_format, output_bitrate_kbps=192):
    """
    Calculate max chunk duration in seconds given a max file size in MB and output format
    Accounts for different format characteristics and compression ratios
    """
    # Format-specific bitrate calculations
    if output_format == 'wav':
        # Speech-optimized WAV: 16-bit * 1 channel * 16kHz
        # 16 * 1 * 16000 = 256,000 bps (vs 1,411,200 for CD quality)
        effective_bitrate = 256000  # 16kHz 16-bit mono
    elif output_format == 'flac':
        # FLAC compression for speech WAV (16kHz mono)
        # Typically achieves 50-60% compression on speech
        effective_bitrate = 256000 * 0.5  # ~128kbps
    else:
        # For compressed formats (MP3, M4A, OGG, WebM, MP4)
        effective_bitrate = output_bitrate_kbps * 1000  # Convert to bps
    
    max_bits = max_mb * 8 * 1024 * 1024  # MB to bits
    
    # Add safety margin to avoid oversized chunks (especially important for variable bitrate)
    # Use 5% margin for compressed formats, 10% for uncompressed
    safety_margin = 0.9 if output_format in ['wav', 'flac'] else 0.95
    max_duration = (max_bits / effective_bitrate) * safety_margin
    
    # Minimum chunk duration of 10 seconds to avoid too many tiny files
    # Maximum chunk duration of 300 seconds (5 minutes) to avoid processing timeouts
    return max(min(max_duration, 300.0), 10.0)

def estimate_chunk_size_mb(duration_seconds, output_format, quality='medium'):
    """
    Estimate the chunk size in MB for a given duration and format.
    Used to predict if chunks will exceed the 25MB limit.
    """
    if output_format == 'wav':
        # 16kHz, 16-bit, mono = 256kbps
        size_bytes = (256000 / 8) * duration_seconds
    elif output_format == 'flac':
        # ~50% compression of speech WAV
        size_bytes = (128000 / 8) * duration_seconds
    else:
        # Compressed formats - use quality bitrate
        bitrates = {'high': 128000, 'medium': 64000, 'low': 32000}
        bitrate = bitrates.get(quality, 64000)
        size_bytes = (bitrate / 8) * duration_seconds
    
    return size_bytes / (1024 * 1024)  # Convert to MB

def get_optimal_output_format(input_filepath, user_format=None, detected_codec=None):
    """
    Determine the optimal output format based on input format and OpenAI compatibility.
    Prioritizes performance on Raspberry Pi while maintaining quality.
    """
    # OpenAI Whisper API supported formats (2024)
    OPENAI_SUPPORTED = {'.mp3', '.wav', '.m4a', '.mp4', '.mpeg', '.mpga', '.webm', '.flac', '.ogg'}
    
    # Performance ranking for Pi 4 (fastest to slowest)
    PERFORMANCE_RANKING = {
        'wav': 1,    # Just container change, no encoding
        'mp3': 2,    # Hardware-optimized, widely supported
        'flac': 3,   # Lossless but larger files
        'ogg': 4,    # Good compression, moderate CPU
        'm4a': 5,    # AAC encoding is CPU intensive on Pi
        'webm': 6,   # Complex encoding
        'mp4': 7,    # Video container overhead
    }
    
    # Format compatibility matrix: input -> best OpenAI output
    FORMAT_MAPPING = {
        # Already OpenAI compatible - keep same format for speed
        '.mp3': 'mp3',
        '.wav': 'wav', 
        '.m4a': 'm4a',
        '.flac': 'flac',
        '.ogg': 'ogg',
        '.webm': 'webm',
        '.mp4': 'mp4',
        '.mpeg': 'mp3',  # Convert to MP3 (similar)
        '.mpga': 'mp3',  # Convert to MP3 (similar)
        
        # Not OpenAI compatible - convert to best match
        '.wma': 'wav',   # WMA->WAV is 5-10x faster than MP3 (proven reliable)
        '.aac': 'm4a',   # AAC is M4A codec, just container change
        '.opus': 'ogg',  # Opus->OGG similar codec family
        '.mkv': 'mp3',   # Extract audio to MP3 (compressed)
        '.avi': 'mp3',   # Extract audio to MP3 (compressed)
        '.mov': 'mp4',   # MOV->MP4 similar containers
    }
    
    # Codec to format mapping for files without extensions
    CODEC_MAPPING = {
        'wmav1': 'wav',   # WMA -> WAV is 5-10x faster (proven reliable)
        'wmav2': 'wav',   # WMA -> WAV is 5-10x faster (proven reliable)
        'mp3': 'mp3',
        'aac': 'm4a',
        'vorbis': 'ogg',
        'opus': 'ogg',
        'flac': 'flac',
        'pcm_s16le': 'wav',
    }
    
    input_ext = Path(input_filepath).suffix.lower()
    
    # If user specified format, validate it's OpenAI compatible
    if user_format:
        if f'.{user_format}' not in OPENAI_SUPPORTED:
            raise ValueError(f"Format '{user_format}' is not supported by OpenAI Whisper API")
        return user_format
    
    # Auto-select optimal format
    if input_ext:
        optimal_format = FORMAT_MAPPING.get(input_ext, 'mp3')
    elif detected_codec:
        optimal_format = CODEC_MAPPING.get(detected_codec.lower(), 'mp3')
    else:
        optimal_format = 'mp3'  # Safe default
    
    return optimal_format

def validate_input_file(filepath):
    """
    Validate that the input file exists and is a supported audio format
    """
    SUPPORTED_EXTENSIONS = {
        '.mp3', '.wav', '.flac', '.ogg', '.m4a', '.aac', '.opus', 
        '.wma', '.mp4', '.webm', '.mkv', '.avi', '.mov', '.mpeg', '.mpga'
    }
    
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {filepath}")
    
    if not path.is_file():
        raise ValueError(f"Input path is not a file: {filepath}")
    
    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        print(f"Warning: File extension '{ext}' may not be supported. Attempting to process anyway...", file=sys.stderr)
    
    return True

def split_audio(input_file, chunk_duration, output_dir, output_format='m4a', quality='medium', verbose=False, logger=None, stream_mode=False):
    """
    Use ffmpeg to split the audio file into chunks of chunk_duration seconds
    
    Args:
        input_file: Path to input audio file
        chunk_duration: Duration of each chunk in seconds
        output_dir: Directory to save output chunks
        output_format: Output format (default: m4a for OpenAI compatibility)
        quality: Audio quality setting ('high', 'medium', 'low')
        verbose: Show detailed output
        stream_mode: Emit JSON for each chunk immediately (for n8n integration)
    """
    split_start_time = datetime.now()
    
    if not logger:
        logger = logging.getLogger('audio_splitter')
    
    logger.info(f"[SPLIT_AUDIO] Starting with chunk_duration={chunk_duration}s")
    
    duration, bitrate, codec_name = get_audio_info(input_file)
    num_chunks = math.ceil(duration / chunk_duration)
    
    logger.info(f"[SPLIT_AUDIO] Audio duration={duration:.2f}s, chunk_duration={chunk_duration}s, num_chunks={num_chunks}")
    
    # Quality presets optimized for Whisper API speech transcription
    # Whisper internally uses 16kHz, so we optimize for this
    quality_settings = {
        'high': {'bitrate': '128k', 'sample_rate': '16000'},   # High quality speech
        'medium': {'bitrate': '64k', 'sample_rate': '16000'},  # Optimal for speech  
        'low': {'bitrate': '32k', 'sample_rate': '16000'}      # Minimum for speech
    }
    
    settings = quality_settings.get(quality, quality_settings['high'])
    
    if not logger:
        logger = logging.getLogger('audio_splitter')
    
    if verbose:
        print(f"Input format: {codec_name}", file=sys.stderr)
        print(f"Output format: {output_format.upper()} @ {settings['bitrate']} bitrate", file=sys.stderr)
        print(f"Creating {num_chunks} chunks of ~{chunk_duration:.1f} seconds each", file=sys.stderr)
    
    successfully_created = []
    
    for i in range(num_chunks):
        chunk_start_timestamp = datetime.now()
        start_time = i * chunk_duration
        
        # Debug: Log the calculation inputs
        logger.info(f"[CHUNK {i+1}/{num_chunks}] CALC: i={i}, chunk_duration={chunk_duration:.2f}s, start_time={start_time:.2f}s, total_duration={duration:.2f}s")
        
        # For the last chunk, adjust duration to not exceed file duration
        if i == num_chunks - 1:
            actual_chunk_duration = duration - start_time
            logger.info(f"[CHUNK {i+1}/{num_chunks}] Last chunk: actual_duration = {duration:.2f} - {start_time:.2f} = {actual_chunk_duration:.2f}s")
        else:
            actual_chunk_duration = chunk_duration
            logger.info(f"[CHUNK {i+1}/{num_chunks}] Regular chunk: actual_duration = chunk_duration = {actual_chunk_duration:.2f}s")
            
        output_path = os.path.join(output_dir, f'chunk_{i+1:03d}.{output_format}')
        
        # Stream mode: emit JSON immediately for n8n
        if stream_mode:
            chunk_info = {
                "chunk_number": i + 1,
                "total_chunks": num_chunks,
                "output_path": output_path,
                "start_time": start_time,
                "duration": actual_chunk_duration,
                "status": "processing"
            }
            print(json.dumps(chunk_info), flush=True)
        else:
            # IMPORTANT: Maintain original stdout format for n8n compatibility
            print(f"Exporting {output_path}")
        
        logger.info(f"[CHUNK {i+1}/{num_chunks}] Starting processing")
        logger.info(f"[CHUNK {i+1}/{num_chunks}] Start time: {start_time:.2f}s, Duration: {actual_chunk_duration:.2f}s")
        logger.info(f"[CHUNK {i+1}/{num_chunks}] Output: {output_path}")
        
        try:
            # Debug logging to catch the issue
            logger.info(f"[CHUNK {i+1}/{num_chunks}] DEBUG: start_time={start_time}, actual_chunk_duration={actual_chunk_duration}")
            
            # Build ffmpeg command based on output format
            if output_format == 'mp3':
                cmd = [
                    'ffmpeg',
                    '-y',  # Overwrite output files
                    '-i', input_file,
                    '-ss', str(start_time),
                    '-t', str(actual_chunk_duration),
                    '-vn',  # No video
                    '-c:a', 'libmp3lame',  # MP3 codec
                    '-b:a', settings['bitrate'],  # Audio bitrate
                    '-ar', settings['sample_rate'],  # Sample rate
                    '-ac', '1',  # Mono for speech
                    output_path
                ]
            elif output_format == 'wav':
                # Compressed WAV for speech: 16-bit, 16kHz, mono
                # Reduces file size by ~20x compared to CD quality
                cmd = [
                    'ffmpeg',
                    '-y',
                    '-i', input_file,
                    '-ss', str(start_time),
                    '-t', str(actual_chunk_duration),
                    '-vn',
                    '-c:a', 'pcm_s16le',  # 16-bit PCM
                    '-ar', '16000',       # 16kHz for speech (Whisper native)
                    '-ac', '1',           # Mono for speech transcription
                    output_path
                ]
            elif output_format == 'm4a':
                cmd = [
                    'ffmpeg',
                    '-y',
                    '-i', input_file,
                    '-ss', str(start_time),
                    '-t', str(actual_chunk_duration),
                    '-vn',
                    '-c:a', 'aac',
                    '-b:a', settings['bitrate'],
                    '-ar', settings['sample_rate'],
                    '-ac', '2',
                    output_path
                ]
            elif output_format == 'flac':
                cmd = [
                    'ffmpeg',
                    '-y',
                    '-i', input_file,
                    '-ss', str(start_time),
                    '-t', str(actual_chunk_duration),
                    '-vn',
                    '-c:a', 'flac',
                    '-ar', '16000',      # 16kHz for speech
                    '-ac', '1',          # Mono for speech
                    '-compression_level', '5',  # Default compression
                    output_path
                ]
            elif output_format == 'ogg':
                cmd = [
                    'ffmpeg',
                    '-y',
                    '-i', input_file,
                    '-ss', str(start_time),
                    '-t', str(actual_chunk_duration),
                    '-vn',
                    '-c:a', 'libvorbis',
                    '-b:a', settings['bitrate'],
                    '-ar', settings['sample_rate'],
                    '-ac', '2',
                    output_path
                ]
            elif output_format == 'webm':
                cmd = [
                    'ffmpeg',
                    '-y',
                    '-i', input_file,
                    '-ss', str(start_time),
                    '-t', str(actual_chunk_duration),
                    '-vn',
                    '-c:a', 'libopus',
                    '-b:a', settings['bitrate'],
                    '-ar', '48000',  # Opus works best at 48kHz
                    '-ac', '2',
                    output_path
                ]
            elif output_format == 'mp4':
                cmd = [
                    'ffmpeg',
                    '-y',
                    '-i', input_file,
                    '-ss', str(start_time),
                    '-t', str(actual_chunk_duration),
                    '-vn',
                    '-c:a', 'aac',
                    '-b:a', settings['bitrate'],
                    '-ar', settings['sample_rate'],
                    '-ac', '2',
                    output_path
                ]
            
            # Log the actual ffmpeg command being run
            logger.info(f"[CHUNK {i+1}/{num_chunks}] FFmpeg command: {' '.join(cmd)}")
            
            # Run ffmpeg with error capture and proper stdin handling for containers
            ffmpeg_start = datetime.now()
            result = subprocess.run(cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=300)
            ffmpeg_duration = (datetime.now() - ffmpeg_start).total_seconds()
            
            logger.info(f"[CHUNK {i+1}/{num_chunks}] FFmpeg completed in {ffmpeg_duration:.2f}s")
            
            if result.returncode != 0:
                logger.error(f"[CHUNK {i+1}/{num_chunks}] FFmpeg FAILED: {result.stderr[:500]}")
                print(f"Warning: Error processing chunk {i+1}", file=sys.stderr)
                if verbose:
                    print(f"FFmpeg error: {result.stderr}", file=sys.stderr)
            else:
                file_size = os.path.getsize(output_path) / (1024 * 1024)
                chunk_total_time = (datetime.now() - chunk_start_timestamp).total_seconds()
                logger.info(f"[CHUNK {i+1}/{num_chunks}] SUCCESS: {file_size:.1f} MB in {chunk_total_time:.2f}s total ({ffmpeg_duration:.2f}s ffmpeg)")
                successfully_created.append(output_path)
                
                # Stream mode: emit success status immediately
                if stream_mode:
                    chunk_info = {
                        "chunk_number": i + 1,
                        "total_chunks": num_chunks,
                        "output_path": output_path,
                        "file_size_mb": round(file_size, 2),
                        "status": "completed"
                    }
                    print(json.dumps(chunk_info), flush=True)
                
        except Exception as e:
            logger.error(f"Exception while creating chunk {i+1}: {str(e)}")
            print(f"Failed to create chunk {i+1}: {str(e)}", file=sys.stderr)
            continue
    
    # Log final summary
    total_time = (datetime.now() - split_start_time).total_seconds()
    logger.info(f"[SUMMARY] Completed {len(successfully_created)}/{num_chunks} chunks in {total_time:.2f}s")
    logger.info(f"[SUMMARY] Average time per chunk: {total_time/max(len(successfully_created), 1):.2f}s")
    
    return successfully_created

def setup_logging():
    """
    Set up logging configuration with both file and console handlers
    """
    # Create logs directory if it doesn't exist
    log_dir = Path(__file__).parent / 'logs'
    log_dir.mkdir(exist_ok=True)
    
    # Create log filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = log_dir / f'audio_splitter_{timestamp}.log'
    
    # Configure logging
    logger = logging.getLogger('audio_splitter')
    logger.setLevel(logging.DEBUG)
    
    # File handler - logs everything
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    
    # Console handler - only errors to stderr
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.ERROR)
    console_formatter = logging.Formatter('%(levelname)s: %(message)s')
    console_handler.setFormatter(console_formatter)
    
    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger, log_file

def main():
    # Set up logging first
    logger, log_file = setup_logging()
    
    parser = argparse.ArgumentParser(
        description="Split audio files for OpenAI transcription API.",
        epilog="Supported formats: MP3, WAV, FLAC, OGG, M4A, WMA, and more. Outputs to MP3 by default."
    )
    parser.add_argument('--input', required=True, help='Path to input audio file')
    parser.add_argument('--output', required=True, help='Output directory')
    parser.add_argument('--maxmb', type=int, default=24, 
                       help='Max size in MB per chunk (default: 24, OpenAI limit: 25)')
    parser.add_argument('--format', default='auto', 
                       choices=['auto', 'mp3', 'wav', 'm4a', 'flac', 'ogg', 'webm', 'mp4'],
                       help='Output format (default: auto - selects optimal format based on input)')
    parser.add_argument('--quality', default='medium', choices=['high', 'medium', 'low'],
                       help='Audio quality (default: medium for good quality/size balance)')
    parser.add_argument('--verbose', action='store_true', help='Show detailed processing information')
    parser.add_argument('--no-log', action='store_true', help='Disable logging to file')
    parser.add_argument('--stream', action='store_true', 
                       help='Stream output mode: emit each chunk immediately as JSON for n8n processing')
    parser.add_argument('--output-json', action='store_true',
                       help='Output results as JSON format for n8n integration')
    args = parser.parse_args()
    
    # Log script start
    logger.info("="*60)
    logger.info("Audio splitter script started")
    logger.info(f"Log file: {log_file}")
    logger.info(f"Command line arguments: {vars(args)}")

    input_file = args.input
    output_dir = args.output
    max_size_mb = args.maxmb
    
    # Validate input and get audio info
    try:
        validate_input_file(input_file)
        logger.info(f"Input file validated: {input_file}")
    except (FileNotFoundError, ValueError) as e:
        logger.error(f"Input validation failed: {e}")
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Get audio information early for format detection
    try:
        logger.info("Starting audio analysis...")
        duration, bitrate, codec_name = get_audio_info(input_file)
        logger.info(f"Audio info - Duration: {duration:.1f}s, Bitrate: {bitrate/1000:.0f}kbps, Codec: {codec_name}")
    except Exception as e:
        logger.error(f"Failed to analyze audio file: {e}")
        print(f"Error analyzing audio file: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Determine optimal output format using codec info
    if args.format == 'auto':
        output_format = get_optimal_output_format(input_file, detected_codec=codec_name)
        logger.info(f"Auto-selected output format: {output_format} (based on input: {Path(input_file).suffix or 'codec: ' + codec_name})")
    else:
        output_format = get_optimal_output_format(input_file, args.format)
        logger.info(f"User-specified output format: {output_format}")
    
    # Validate max size
    if max_size_mb > 25:
        logger.warning(f"Max size {max_size_mb}MB exceeds OpenAI's 25MB limit")
        print("Warning: OpenAI's maximum file size is 25MB. Consider using --maxmb 25 or less.", file=sys.stderr)
    elif max_size_mb < 1:
        logger.error(f"Invalid max size: {max_size_mb}MB")
        print("Error: Maximum chunk size must be at least 1MB", file=sys.stderr)
        sys.exit(1)
    
    # Create output directory
    try:
        os.makedirs(output_dir, exist_ok=True)
        logger.info(f"Output directory ready: {output_dir}")
    except OSError as e:
        logger.error(f"Failed to create output directory: {e}")
        print(f"Error creating output directory: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        if args.verbose:
            print(f"Analyzing {input_file}...", file=sys.stderr)
        
        # Calculate chunk duration based on output format - use same bitrates as encoding
        base_bitrates = {'high': 128, 'medium': 64, 'low': 32}  # Match the quality_settings
        output_bitrate = base_bitrates[args.quality]
        
        chunk_duration = calculate_chunk_duration(bitrate, max_size_mb, output_format, output_bitrate)
        num_chunks = math.ceil(duration / chunk_duration)
        logger.info(f"Calculated chunk duration: {chunk_duration:.2f}s, Expected chunks: {num_chunks}")
        
        if args.verbose:
            file_size_mb = os.path.getsize(input_file) / (1024 * 1024)
            print(f"File size: {file_size_mb:.1f} MB", file=sys.stderr)
            print(f"Duration: {duration:.1f} seconds ({duration/60:.1f} minutes)", file=sys.stderr)
            print(f"Input codec: {codec_name} -> Output format: {output_format.upper()}", file=sys.stderr)
            print(f"Target max chunk size: {max_size_mb} MB", file=sys.stderr)
            print(f"Calculated chunk duration: {chunk_duration:.2f} seconds", file=sys.stderr)
            print(f"Expected number of chunks: {num_chunks}", file=sys.stderr)
        
        if chunk_duration < 10:
            logger.warning(f"Short chunk duration: {chunk_duration:.2f}s")
            print("Warning: Chunk duration is very short. Consider using a lower quality setting.", file=sys.stderr)
        
        # Check if chunks might exceed 25MB limit and adjust format if needed
        estimated_size = estimate_chunk_size_mb(chunk_duration, output_format, args.quality)
        if estimated_size > 24 and output_format == 'wav':  # Leave 1MB margin
            logger.info(f"WAV chunks estimated at {estimated_size:.1f}MB - switching to FLAC")
            print(f"Note: WAV chunks would be ~{estimated_size:.1f}MB, switching to FLAC for compression", file=sys.stderr)
            output_format = 'flac'
            # Recalculate with FLAC format
            chunk_duration = calculate_chunk_duration(bitrate, max_size_mb, output_format, output_bitrate)
            num_chunks = math.ceil(duration / chunk_duration)
            estimated_size = estimate_chunk_size_mb(chunk_duration, output_format, args.quality)
            
        if estimated_size > 24:  # Still too large even with FLAC
            logger.warning(f"Chunks still estimated at {estimated_size:.1f}MB - audio may need lower quality")
            print(f"Warning: Chunks estimated at {estimated_size:.1f}MB may exceed 25MB limit", file=sys.stderr)
        
        # Split the audio
        logger.info(f"Starting audio split - Format: {output_format}, Quality: {args.quality}, Stream: {args.stream}")
        created_files = split_audio(input_file, chunk_duration, output_dir, output_format, args.quality, args.verbose, logger, args.stream)
        
        # Handle different output modes
        if args.stream:
            # Stream mode: emit final summary as JSON
            summary = {
                "status": "completed",
                "total_chunks": len(created_files),
                "output_format": output_format,
                "chunks": [os.path.basename(f) for f in created_files]
            }
            print(json.dumps(summary), flush=True)
        elif args.output_json:
            # JSON output mode: full summary
            summary = {
                "status": "success",
                "input_file": input_file,
                "output_dir": output_dir,
                "chunks_created": len(created_files),
                "output_format": output_format,
                "quality": args.quality,
                "max_size_mb": max_size_mb,
                "files": []
            }
            for f in created_files:
                size_mb = os.path.getsize(f) / (1024 * 1024)
                summary['files'].append({
                    'path': f,
                    'filename': os.path.basename(f),
                    'size_mb': round(size_mb, 2)
                })
            print(json.dumps(summary, indent=2))
        else:
            # Print completion message (maintaining original format)
            print("✅ Done.")
        
        # Log summary
        if created_files:
            logger.info(f"Successfully created {len(created_files)} chunks")
            
            # Create summary for log
            summary = {
                'status': 'success',
                'input_file': input_file,
                'output_dir': output_dir,
                'chunks_created': len(created_files),
                'output_format': output_format,
                'quality': args.quality,
                'max_size_mb': max_size_mb,
                'files': []
            }
            
            # Check chunk sizes and log
            oversized_count = 0
            for f in created_files:
                size_mb = os.path.getsize(f) / (1024 * 1024)
                summary['files'].append({
                    'filename': os.path.basename(f),
                    'size_mb': round(size_mb, 2)
                })
                if size_mb > 25:
                    oversized_count += 1
                    logger.warning(f"Oversized chunk: {os.path.basename(f)} is {size_mb:.1f} MB")
                    if args.verbose:
                        print(f"Warning: {os.path.basename(f)} is {size_mb:.1f} MB (exceeds OpenAI limit)", file=sys.stderr)
            
            if oversized_count > 0:
                summary['warnings'] = f"{oversized_count} chunks exceed 25MB limit"
            
            logger.info(f"Processing summary: {json.dumps(summary, indent=2)}")
        else:
            logger.error("No chunks were created")
            
    except Exception as e:
        logger.error(f"Script failed with error: {e}", exc_info=True)
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc(file=sys.stderr)
        sys.exit(1)
    finally:
        logger.info("Audio splitter script finished")
        logger.info("="*60)

if __name__ == '__main__':
    main()
