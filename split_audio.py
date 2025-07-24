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

def calculate_chunk_duration(bitrate_bps, max_mb, output_bitrate_kbps=192):
    """
    Calculate max chunk duration in seconds given a max file size in MB and bitrate
    Accounts for potential bitrate changes during conversion
    """
    # Use output bitrate if converting to MP3
    effective_bitrate = output_bitrate_kbps * 1000  # Convert to bps
    max_bits = max_mb * 8 * 1024 * 1024  # MB to bits
    # Add 10% safety margin to avoid oversized chunks
    return (max_bits / effective_bitrate) * 0.9

def validate_input_file(filepath):
    """
    Validate that the input file exists and is a supported audio format
    """
    SUPPORTED_EXTENSIONS = {
        '.mp3', '.wav', '.flac', '.ogg', '.m4a', '.aac', '.opus', 
        '.wma', '.mp4', '.webm', '.mkv', '.avi', '.mov'
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

def split_audio(input_file, chunk_duration, output_dir, output_format='mp3', quality='high', verbose=False):
    """
    Use ffmpeg to split the audio file into chunks of chunk_duration seconds
    
    Args:
        input_file: Path to input audio file
        chunk_duration: Duration of each chunk in seconds
        output_dir: Directory to save output chunks
        output_format: Output format (default: mp3 for OpenAI compatibility)
        quality: Audio quality setting ('high', 'medium', 'low')
        verbose: Show detailed output
    """
    duration, bitrate, codec_name = get_audio_info(input_file)
    num_chunks = math.ceil(duration / chunk_duration)
    
    # Quality presets for MP3 (optimized for speech transcription)
    quality_settings = {
        'high': {'bitrate': '192k', 'sample_rate': '44100'},
        'medium': {'bitrate': '128k', 'sample_rate': '44100'},
        'low': {'bitrate': '96k', 'sample_rate': '22050'}
    }
    
    settings = quality_settings.get(quality, quality_settings['high'])
    
    if verbose:
        print(f"Input format: {codec_name}", file=sys.stderr)
        print(f"Output format: {output_format.upper()} @ {settings['bitrate']} bitrate", file=sys.stderr)
        print(f"Creating {num_chunks} chunks of ~{chunk_duration:.1f} seconds each", file=sys.stderr)
    
    successfully_created = []
    
    for i in range(num_chunks):
        start_time = i * chunk_duration
        output_path = os.path.join(output_dir, f'chunk_{i+1:03d}.{output_format}')
        
        # IMPORTANT: Maintain original stdout format for n8n compatibility
        print(f"Exporting {output_path}")
        
        try:
            # Build ffmpeg command based on output format
            if output_format == 'mp3':
                cmd = [
                    'ffmpeg',
                    '-y',  # Overwrite output files
                    '-i', input_file,
                    '-ss', str(start_time),
                    '-t', str(chunk_duration),
                    '-vn',  # No video
                    '-c:a', 'libmp3lame',  # MP3 codec
                    '-b:a', settings['bitrate'],  # Audio bitrate
                    '-ar', settings['sample_rate'],  # Sample rate
                    '-ac', '2',  # Stereo output
                    output_path
                ]
            elif output_format == 'wav':
                cmd = [
                    'ffmpeg',
                    '-y',
                    '-i', input_file,
                    '-ss', str(start_time),
                    '-t', str(chunk_duration),
                    '-vn',
                    '-c:a', 'pcm_s16le',
                    '-ar', '44100',
                    '-ac', '2',
                    output_path
                ]
            elif output_format == 'm4a':
                cmd = [
                    'ffmpeg',
                    '-y',
                    '-i', input_file,
                    '-ss', str(start_time),
                    '-t', str(chunk_duration),
                    '-vn',
                    '-c:a', 'aac',
                    '-b:a', settings['bitrate'],
                    '-ar', settings['sample_rate'],
                    '-ac', '2',
                    output_path
                ]
            
            # Run ffmpeg with error capture
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"Warning: Error processing chunk {i+1}", file=sys.stderr)
                if verbose:
                    print(f"FFmpeg error: {result.stderr}", file=sys.stderr)
            else:
                successfully_created.append(output_path)
                
        except Exception as e:
            print(f"Failed to create chunk {i+1}: {str(e)}", file=sys.stderr)
            continue
    
    return successfully_created

def main():
    parser = argparse.ArgumentParser(
        description="Split audio files for OpenAI transcription API.",
        epilog="Supported formats: MP3, WAV, FLAC, OGG, M4A, WMA, and more. Outputs to MP3 by default."
    )
    parser.add_argument('--input', required=True, help='Path to input audio file')
    parser.add_argument('--output', required=True, help='Output directory')
    parser.add_argument('--maxmb', type=int, default=20, 
                       help='Max size in MB per chunk (default: 20, OpenAI limit: 25)')
    parser.add_argument('--format', default='mp3', choices=['mp3', 'wav', 'm4a'],
                       help='Output format (default: mp3 for best OpenAI compatibility)')
    parser.add_argument('--quality', default='high', choices=['high', 'medium', 'low'],
                       help='Audio quality (default: high)')
    parser.add_argument('--verbose', action='store_true', help='Show detailed processing information')
    args = parser.parse_args()

    input_file = args.input
    output_dir = args.output
    max_size_mb = args.maxmb
    
    # Validate input
    try:
        validate_input_file(input_file)
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Validate max size
    if max_size_mb > 25:
        print("Warning: OpenAI's maximum file size is 25MB. Consider using --maxmb 25 or less.", file=sys.stderr)
    elif max_size_mb < 1:
        print("Error: Maximum chunk size must be at least 1MB", file=sys.stderr)
        sys.exit(1)
    
    # Create output directory
    try:
        os.makedirs(output_dir, exist_ok=True)
    except OSError as e:
        print(f"Error creating output directory: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        if args.verbose:
            print(f"Analyzing {input_file}...", file=sys.stderr)
        
        # Get audio information
        duration, bitrate, codec_name = get_audio_info(input_file)
        
        # Calculate chunk duration based on output format bitrate
        output_bitrate = {'high': 192, 'medium': 128, 'low': 96}[args.quality]
        chunk_duration = calculate_chunk_duration(bitrate, max_size_mb, output_bitrate)
        
        if args.verbose:
            file_size_mb = os.path.getsize(input_file) / (1024 * 1024)
            print(f"File size: {file_size_mb:.1f} MB", file=sys.stderr)
            print(f"Duration: {duration:.1f} seconds ({duration/60:.1f} minutes)", file=sys.stderr)
            print(f"Input codec: {codec_name}", file=sys.stderr)
            print(f"Estimated chunk duration: {chunk_duration:.2f} seconds", file=sys.stderr)
        
        if chunk_duration < 10:
            print("Warning: Chunk duration is very short. Consider using a lower quality setting.", file=sys.stderr)
        
        # Split the audio
        created_files = split_audio(input_file, chunk_duration, output_dir, args.format, args.quality, args.verbose)
        
        # Print completion message (maintaining original format)
        print("✅ Done.")
        
        # Additional info to stderr if verbose
        if args.verbose and created_files:
            print(f"\nSuccessfully created {len(created_files)} chunks", file=sys.stderr)
            
            # Check if any chunks are oversized
            for f in created_files:
                size_mb = os.path.getsize(f) / (1024 * 1024)
                if size_mb > 25:
                    print(f"Warning: {os.path.basename(f)} is {size_mb:.1f} MB (exceeds OpenAI limit)", file=sys.stderr)
            
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc(file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
