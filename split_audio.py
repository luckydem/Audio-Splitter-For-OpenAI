import os
import math
import subprocess
import argparse
import ffmpeg

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

def calculate_chunk_duration(bitrate_bps, max_mb):
    """
    Calculate max chunk duration in seconds given a max file size in MB and bitrate
    """
    max_bits = max_mb * 8 * 1024 * 1024  # MB to bits
    return max_bits / bitrate_bps       # seconds

def get_output_format(codec_name):
    """
    Determine the appropriate output format and codec based on input codec
    """
    # Mapping of common audio codecs to container formats and FFmpeg encoder names
    CODEC_FORMAT_MAP = {
        'aac': ('.m4a', 'aac'),
        'alac': ('.m4a', 'alac'),
        'mp3': ('.mp3', 'libmp3lame'),
        'vorbis': ('.ogg', 'libvorbis'),
        'opus': ('.opus', 'libopus'), 
        'flac': ('.flac', 'flac'),
        'wav': ('.wav', 'pcm_s16le'),
        'pcm_s16le': ('.wav', 'pcm_s16le'),
        'pcm_s24le': ('.wav', 'pcm_s24le'),
        'wma': ('.wma', 'wmav2'),
    }
    
    # Default to MP3 if codec is not in our map
    return CODEC_FORMAT_MAP.get(codec_name, ('.mp3', 'libmp3lame'))

def split_audio(input_file, chunk_duration, output_dir):
    """
    Use ffmpeg to split the audio file into chunks of chunk_duration seconds
    """
    duration, bitrate, codec_name = get_audio_info(input_file)
    num_chunks = math.ceil(duration / chunk_duration)
    
    # Get the appropriate output format and codec
    output_ext, output_codec = get_output_format(codec_name)
    
    for i in range(num_chunks):
        start_time = i * chunk_duration
        output_path = os.path.join(output_dir, f'chunk_{i+1:03d}{output_ext}')
        print(f"Exporting {output_path}")  # Maintain original stdout format

        try:
            # First try to copy the stream without re-encoding
            subprocess.run([
                'ffmpeg',
                '-y',
                '-i', input_file,
                '-ss', str(start_time),
                '-t', str(chunk_duration),
                '-c', 'copy',
                output_path
            ], check=True, stderr=subprocess.DEVNULL)  # Suppress FFmpeg output
        except subprocess.CalledProcessError:
            # If stream copy fails, fall back to re-encoding
            try:
                subprocess.run([
                    'ffmpeg',
                    '-y',
                    '-i', input_file,
                    '-ss', str(start_time),
                    '-t', str(chunk_duration),
                    '-c:a', output_codec,
                    output_path
                ], check=True, stderr=subprocess.DEVNULL)  # Suppress FFmpeg output
            except subprocess.CalledProcessError:
                # Final fallback to MP3 if everything else fails
                output_path = os.path.join(output_dir, f'chunk_{i+1:03d}.mp3')
                print(f"Exporting {output_path}")  # Print new path if format changes
                subprocess.run([
                    'ffmpeg',
                    '-y',
                    '-i', input_file,
                    '-ss', str(start_time),
                    '-t', str(chunk_duration),
                    '-c:a', 'libmp3lame',
                    output_path
                ], check=True, stderr=subprocess.DEVNULL)

def main():
    parser = argparse.ArgumentParser(description="Split audio file into chunks while preserving format.")
    parser.add_argument('--input', required=True, help='Path to input audio file')
    parser.add_argument('--output', required=True, help='Output directory')
    parser.add_argument('--maxmb', type=int, default=20, help='Max size in MB per chunk (default: 20)')
    parser.add_argument('--verbose', action='store_true', help='Show detailed processing information')
    args = parser.parse_args()

    input_file = args.input
    output_dir = args.output
    max_size_mb = args.maxmb

    if not os.path.exists(input_file):
        raise FileNotFoundError(f"Input file not found: {input_file}")

    os.makedirs(output_dir, exist_ok=True)

    if args.verbose:
        print(f"Analyzing {input_file}...")
        duration, bitrate, codec_name = get_audio_info(input_file)
        chunk_duration = calculate_chunk_duration(bitrate, max_size_mb)
        print(f"Input codec: {codec_name}")
        print(f"Estimated chunk duration: {chunk_duration:.2f} seconds")
    else:
        duration, bitrate, codec_name = get_audio_info(input_file)
        chunk_duration = calculate_chunk_duration(bitrate, max_size_mb)

    split_audio(input_file, chunk_duration, output_dir)
    print("✅ Done.")

if __name__ == '__main__':
    main()