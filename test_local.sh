#!/bin/bash

echo "🐳 Building and starting local Docker development environment..."

# Build and start the service
docker compose -f docker-compose.dev.yml up --build -d

echo "⏳ Waiting for service to start..."
sleep 5

# Test health endpoint
echo "🔍 Testing health endpoint..."
curl -s http://localhost:8081/ | jq '.' || echo "Service not ready yet"

echo ""
echo "✅ Local development server is running at: http://localhost:8081"
echo ""
echo "📋 Available endpoints:"
echo "  GET  /                           - Health check"
echo "  POST /process-drive-file         - Process audio from Google Drive"  
echo "  POST /transcribe-and-compile     - Transcribe chunks"
echo "  POST /process-drive-folder       - Process entire folder"
echo ""
echo "🔧 Development commands:"
echo "  docker compose -f docker-compose.dev.yml logs -f    # View logs"
echo "  docker compose -f docker-compose.dev.yml restart    # Restart service"
echo "  docker compose -f docker-compose.dev.yml down       # Stop service"
echo ""
echo "🧪 Test with a real file:"
echo 'curl -X POST http://localhost:8081/process-drive-file \'
echo '  -H "Content-Type: application/json" \'
echo '  -d '"'"'{'
echo '    "drive_file_id": "1zhAUIDpYSA3FNxBhKQWT0sp9RssUhN7R",'
echo '    "max_size_mb": 25,'
echo '    "output_format": "m4a",'
echo '    "quality": "medium",'
echo '    "skip_transcription": true'
echo '  }'"'"' | jq'"'"