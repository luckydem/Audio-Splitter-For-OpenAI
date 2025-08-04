# Testing Infrastructure

This folder contains all testing utilities and diagnostic tools for the Audio Splitter project.

## Test Categories

### Webhook Testing
- **test_enhanced_endpoint.py** - Tests the enhanced webhook payload with drive_file_id and folder parameters
- **test_webhook_n8n.py** - Comprehensive n8n webhook testing with different payload types
- **test_webhook_no_head.py** - Tests webhook delivery without HEAD requests (fixes n8n issues)
- **test_webhook_quick.py** - Quick webhook connectivity testing
- **test_webhook_quick_test.py** - Quick test for n8n webhook in test mode
- **test_webhook_timeout.py** - Tests webhook timeouts and retry logic

### Google Drive Testing
- **test_drive_access.py** - Tests Google Drive API access and file operations
- **test_shared_drive_access.py** - Tests shared Google Drive access
- **test_download_file.py** - Tests file download from Google Drive

### Local Testing
- **test_local.sh** - Local development testing script
- **test_quick_local.py** - Quick local functionality tests

### Diagnostic Tools
- **diagnose_n8n_webhooks.py** - Diagnostic tool for n8n webhook issues
- **test_resume_url_pattern.py** - Tests n8n resume URL patterns

## Running Tests

### Prerequisites
```bash
# Setup development environment
../scripts/setup-dev.sh

# Or manually activate virtual environment
source ../.venv/bin/activate
```

### Individual Tests
```bash
# Test enhanced webhook functionality
python test_enhanced_endpoint.py

# Test n8n webhook integration
python test_webhook_n8n.py https://n8n.example.com/webhook/test

# Test Google Drive access
python test_drive_access.py

# Diagnose webhook issues
python diagnose_n8n_webhooks.py https://n8n.example.com/webhook/test
```

### Batch Testing
```bash
# Run local tests
./test_local.sh

# Quick local functionality test
python test_quick_local.py
```

## Test Structure

All Python test files follow this import pattern:
```python
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from audio_splitter_drive import send_webhook, test_webhook_connectivity
```

## Common Test Scenarios

### Webhook Testing
1. **Basic connectivity** - test_webhook_quick.py
2. **n8n integration** - test_webhook_n8n.py
3. **Enhanced payload** - test_enhanced_endpoint.py
4. **Timeout handling** - test_webhook_timeout.py

### Google Drive Testing
1. **File access** - test_drive_access.py
2. **Shared drives** - test_shared_drive_access.py
3. **File download** - test_download_file.py

### Diagnostic Workflow
1. Run diagnose_n8n_webhooks.py to identify issues
2. Use specific test files to validate fixes
3. Run test_enhanced_endpoint.py to verify full functionality

## Environment Variables

Tests may require these environment variables:
- `OPENAI_API_KEY` - For transcription testing
- `GOOGLE_APPLICATION_CREDENTIALS` - For Google Drive API testing
- Or use `../config/service-account-key.json` for service account auth