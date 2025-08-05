#!/bin/bash
# Test script for direct OpenAI API transcription

# Check if API key is provided
if [ -z "$1" ]; then
    echo "Usage: ./test_direct_api.sh YOUR_OPENAI_API_KEY"
    exit 1
fi

API_KEY=$1
FILE="sample-files/250609_0051 BoD Mtg.WMA"

echo "Testing direct transcription of large WMA file..."
echo "File: $FILE"
echo "Size: $(ls -lh "$FILE" | awk '{print $5}')"
echo ""

# Test with the script
python src/transcribe_long_audio.py "$FILE" \
    --api-key "$API_KEY" \
    --output "sample-files/direct_transcript.txt" \
    --language en

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Success! Transcript saved to: sample-files/direct_transcript.txt"
    echo "First 500 characters:"
    head -c 500 "sample-files/direct_transcript.txt"
    echo "..."
else
    echo "❌ Transcription failed"
fi