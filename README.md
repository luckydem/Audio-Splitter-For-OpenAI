# Audio File Splitter for OpenAI Transcription

A Python script that splits large audio files into smaller chunks suitable for OpenAI's transcription API, which has a 25MB file size limit.

## Features

- Splits audio files based on file size limits (default 20MB)
- Supports multiple input formats: MP3, WAV, FLAC, OGG, M4A, WMA, and more
- Outputs to M4A format by default for optimal OpenAI compatibility and compression
- Configurable output format (MP3, WAV, M4A) and quality settings
- Maintains n8n workflow compatibility with structured output
- Smart chunk size calculation to prevent oversized files

## Prerequisites

1. **Python 3.6+**
2. **FFmpeg** installed on your system
   - Ubuntu/Debian: `sudo apt-get install ffmpeg`
   - macOS: `brew install ffmpeg`
   - Windows: Download from [ffmpeg.org](https://ffmpeg.org/download.html)

## Installation

1. Clone this repository:
   ```bash
   git clone <your-repo-url>
   cd scripts
   ```

2. Create a virtual environment (recommended):
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

Basic usage:
```bash
python split_audio.py --input /path/to/audio.wma --output /path/to/output_dir
```

With options:
```bash
python split_audio.py --input audio.wma --output chunks/ --maxmb 20 --format m4a --quality medium --verbose
```

### Options

- `--input`: Path to input audio file (required)
- `--output`: Output directory for chunks (required)
- `--maxmb`: Maximum size in MB per chunk (default: 20, max recommended: 25)
- `--format`: Output format - mp3, wav, or m4a (default: m4a)
- `--quality`: Audio quality - high, medium, or low (default: medium)
- `--verbose`: Show detailed processing information
- `--no-log`: Disable logging to file (logs are enabled by default)

## n8n Integration

The script outputs "Exporting /path/to/chunk" messages to stdout for easy parsing in n8n workflows. Use the included `n8n_parser_improved.js` for robust parsing:

```javascript
const filePaths = $('Execute Audio Splitter Script').first().json.stdout
    .split("\n")
    .filter(line => line.includes("Exporting "))
    .map(line => line.replace("Exporting ", "").trim());
```

## Output Quality Settings

- **High**: 192 kbps, 44.1 kHz (best quality, larger files)
- **Medium**: 128 kbps, 44.1 kHz (recommended - good quality/size balance)
- **Low**: 96 kbps, 22.05 kHz (smallest files, may affect transcription quality)

**Note**: M4A format is ~30% more efficient than MP3, so M4A at medium quality often provides better results than MP3 at the same bitrate.

## Logging

The script automatically creates detailed logs in the `logs/` directory with timestamps. Each execution creates a new log file named `audio_splitter_YYYYMMDD_HHMMSS.log`.

**Log contents include:**
- Script execution details and parameters
- Input file analysis results
- Processing progress for each chunk
- Error messages and warnings
- Processing summary with file sizes
- Performance metrics

**Managing log files:**
```bash
# Keep logs from last 30 days
python cleanup_logs.py --days 30

# Keep only the 10 most recent log files
python cleanup_logs.py --count 10
```

To disable logging, use the `--no-log` flag:
```bash
python split_audio.py --input audio.wma --output chunks/ --no-log
```

**Format Recommendations:**
- **M4A (default)**: Best compression efficiency, smaller files, fully compatible with OpenAI
- **MP3**: Universal compatibility, slightly larger files than M4A
- **WAV**: Uncompressed, largest files but highest quality

## Troubleshooting

1. **"No audio stream found in the file"**: The input file may be corrupted or not contain audio
2. **Chunks exceed 25MB**: Try using `--quality medium` or `--quality low`
3. **FFmpeg not found**: Ensure FFmpeg is installed and in your system PATH
4. **Check the logs**: Look in the `logs/` directory for detailed error information

## License

This project is licensed under the MIT License.