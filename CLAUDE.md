# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an n8n audio processing automation system designed to split large audio files into smaller chunks for OpenAI Whisper transcription. The system is optimized for Raspberry Pi 4 performance.

## Key Commands

### Audio Splitting
```bash
# Basic usage
python src/split_audio.py --input /path/to/audio.wma --output /tmp/

# Optimized with streaming (recommended for n8n workflows)
python src/split_audio.py --input file.wma --output /tmp/ --stream

# With custom settings
python src/split_audio.py --input audio.wma --output chunks/ --maxmb 20 --format m4a --quality medium --verbose
```

### Virtual Environment
```bash
# Activate virtual environment before running scripts
source .venv/bin/activate
```

### Log Management
```bash
# Keep logs from last 30 days
python src/cleanup_logs.py --days 30

# Keep only 10 most recent logs
python src/cleanup_logs.py --count 10
```

## Architecture

### Core Components

1. **src/split_audio.py**: Main audio splitting script
   - Handles multiple input formats (MP3, WAV, FLAC, OGG, M4A, WMA)
   - Smart format selection for Pi 4 performance (WMA→WAV is 5-10x faster than WMA→M4A)
   - Supports streaming JSON output for immediate chunk availability
   - 20MB default chunk size with safety margin for OpenAI's 25MB limit

2. **n8n Workflows Structure**:
   ```
   Main Workflow → Split Audio Sub-workflow → Transcribe Audio Sub-workflow
   ```
   - Split Audio creates chunks and optionally streams them
   - Transcribe processes chunks (can be parallel or sequential)
   - Results merge back to main workflow

3. **JavaScript Parsers**:
   - `n8n_parser_streaming.js`: Universal parser supporting legacy and JSON streaming formats
   - `n8n_parser_improved.js`: Legacy format parser
   - `n8n_merge_transcriptions.js`: Aggregates transcription results

### Key Design Decisions

1. **Format Optimization**: The script automatically selects output format based on input type and Pi performance characteristics. WAV is preferred for WMA inputs due to 5-10x faster processing.

2. **Streaming Mode**: The `--stream` flag enables JSON line output, allowing n8n to process chunks as they're created rather than waiting for all chunks.

3. **Chunk Size Calculation**: Uses format-specific bitrate calculations with 20% safety margin to ensure chunks stay under OpenAI's 25MB limit.

## n8n Integration Points

### Updating Existing Workflows

To enable streaming optimization:
1. Add `--stream` flag to the Execute Command node in Split Audio sub-workflow
2. Replace the parser code with `n8n_parser_streaming.js` content
3. No changes needed to Transcribe or Main workflows

### Workflow Variables
- `file_path`: Path to audio file in n8n binary data directory
- `transcribe_single_chunk_workflow_id`: ID of single chunk transcriber (for parallel setup)

### Output Formats
- Legacy: `Exporting /path/to/chunk`
- Streaming JSON: `{"chunk_number": 1, "status": "completed", "output_path": "/tmp/chunk_001.wav"}`
- Final JSON: Complete file list with metadata

## Performance Considerations

- WMA→WAV conversion is 5-10x faster than WMA→M4A on Pi 4
- Streaming mode allows parallel transcription while splitting continues
- Default 20MB chunks with safety margin for reliable OpenAI API calls
- Logs are written to `logs/` directory with rotation support

## FFmpeg Dependency

The system requires FFmpeg installed:
```bash
sudo apt-get install ffmpeg  # Debian/Ubuntu/Raspberry Pi OS
```

## Logging and Monitoring

- Use the cloud run log monitor agent every time I want to monitor logs

## Project Structure

The project follows best practices with organized folder structure:

- **src/**: Core application source code (audio_splitter_drive.py, split_audio.py)
- **tests/**: All test scripts and diagnostic tools
- **config/**: Configuration files (service-account-key.json)
- **deployment/**: Docker, Cloud Build, and deployment scripts
- **docs/**: Documentation and setup guides
- **workflows/**: External platform integrations (n8n workflows)
- **scripts/**: Development utilities and setup scripts
- **legacy/**: Deprecated code kept for reference

### Development Commands

```bash
# Setup development environment
./scripts/setup-dev.sh

# Run tests
python tests/test_enhanced_endpoint.py

# Deploy to Cloud Run
./deployment/deploy.sh
```

See PROJECT_STRUCTURE.md for detailed folder organization.