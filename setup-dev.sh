#!/bin/bash
# Development environment setup script

echo "🔧 Setting up development environment for Audio Splitter..."

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv .venv
else
    echo "✅ Virtual environment already exists"
fi

# Activate virtual environment
echo "🔌 Activating virtual environment..."
source .venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install development requirements
echo "📚 Installing development requirements..."
pip install -r requirements-dev.txt

# Check if FFmpeg is installed
if ! command -v ffmpeg &> /dev/null; then
    echo "⚠️  WARNING: FFmpeg is not installed!"
    echo "   Please install FFmpeg:"
    echo "   - Ubuntu/Debian: sudo apt-get install ffmpeg"
    echo "   - macOS: brew install ffmpeg"
    echo "   - Windows: Download from https://ffmpeg.org/download.html"
else
    echo "✅ FFmpeg is installed: $(ffmpeg -version | head -n1)"
fi

echo ""
echo "✨ Development environment setup complete!"
echo ""
echo "To activate the environment in the future, run:"
echo "  source .venv/bin/activate"
echo ""
echo "To run tests:"
echo "  python test_webhook_quick.py"
echo "  python test_webhook_n8n.py <webhook_url>"
echo ""
echo "To deploy to Cloud Run:"
echo "  ./deploy.sh"