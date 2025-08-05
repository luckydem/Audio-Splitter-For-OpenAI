#!/bin/bash
# Optimized workflow for long WMA files
# 1. Convert WMA to MP3 (reduces size and improves compatibility)
# 2. Use the audio splitter service to transcribe

if [ $# -lt 1 ]; then
    echo "Usage: $0 <wma_file> [drive_url]"
    echo "Example: $0 'audio.wma' 'https://drive.google.com/file/d/...'"
    exit 1
fi

INPUT_FILE="$1"
DRIVE_URL="${2:-}"
OUTPUT_MP3="${INPUT_FILE%.*}.mp3"

echo "=== Optimized WMA Transcription Workflow ==="
echo "Input: $INPUT_FILE"
echo ""

# Step 1: Convert WMA to MP3
echo "Step 1: Converting WMA to MP3..."
ffmpeg -i "$INPUT_FILE" \
    -c:a libmp3lame \
    -b:a 48k \
    -ar 22050 \
    -ac 1 \
    "$OUTPUT_MP3" -y

if [ $? -ne 0 ]; then
    echo "❌ Conversion failed"
    exit 1
fi

# Get file sizes
ORIGINAL_SIZE=$(ls -lh "$INPUT_FILE" | awk '{print $5}')
NEW_SIZE=$(ls -lh "$OUTPUT_MP3" | awk '{print $5}')

echo "✅ Conversion complete!"
echo "Original: $ORIGINAL_SIZE"
echo "Converted: $NEW_SIZE"
echo ""

# Step 2: Option A - Upload to Google Drive and use the service
if [ -n "$DRIVE_URL" ]; then
    echo "Step 2: Use the audio splitter service"
    echo "1. Upload $OUTPUT_MP3 to Google Drive"
    echo "2. Use the service at: https://audio-splitter-ey3mdkeuya-uc.a.run.app"
    echo "3. The service will handle chunking and transcription"
else
    # Step 2: Option B - Use local chunking
    echo "Step 2: Process locally"
    echo "Run: python src/split_audio.py --input \"$OUTPUT_MP3\" --output chunks/ --maxmb 20"
fi