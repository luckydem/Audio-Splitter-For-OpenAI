# Project Structure

This document outlines the organized folder structure for the Audio Splitter project.

## Directory Structure

```
Audio-Splitter-For-OpenAI/
├── src/                           # Core application source code
│   ├── audio_splitter_drive.py    # Main Cloud Run service with Google Drive integration
│   ├── split_audio.py             # Core audio splitting functionality
│   └── cleanup_logs.py            # Log cleanup utility
├── tests/                         # All test scripts and utilities
│   ├── test_enhanced_endpoint.py  # Test enhanced webhook payload
│   ├── test_webhook_*.py          # Webhook testing suite
│   ├── test_drive_access.py       # Google Drive API testing
│   ├── test_local.sh              # Local testing script
│   └── diagnose_n8n_webhooks.py   # n8n webhook diagnostic tool
├── config/                        # Configuration files
│   └── service-account-key.json   # Google Cloud service account credentials
├── deployment/                    # Deployment related files
│   ├── deploy.sh                  # Cloud Run deployment script
│   ├── docker-compose.dev.yml     # Development Docker configuration
│   ├── Dockerfile                 # Production Docker image
│   └── cloudbuild.yaml           # Google Cloud Build configuration
├── scripts/                       # Utility scripts
│   └── setup-dev.sh              # Development environment setup
├── docs/                          # Documentation
│   ├── GOOGLE_DRIVE_SETUP.md     # Google Drive API setup guide
│   ├── N8N_WORKFLOW_GUIDE.md     # n8n workflow configuration
│   └── WEBHOOK_IMPROVEMENTS.md    # Webhook enhancement documentation
├── workflows/                     # Workflow configurations
│   └── n8n/                      # n8n workflow JSON files
├── legacy/                        # Legacy/deprecated code
│   ├── audio_splitter_api.py     # Original API implementation
│   └── audio_splitter_gcs.py     # Original GCS implementation
├── requirements-production.txt    # Production dependencies (lean)
├── requirements-dev.txt          # Development dependencies (comprehensive)
├── CLAUDE.md                     # Claude Code instructions
└── README.md                     # Main project documentation
```

## Key Principles

1. **Separation of Concerns**: Core application code in `src/`, tests isolated in `tests/`
2. **Configuration Management**: Sensitive configs in `config/`, deployment configs in `deployment/`
3. **Clear Documentation**: All guides and docs in `docs/` folder
4. **Development Support**: Development utilities in `scripts/`, legacy code preserved
5. **Workflow Integration**: Platform-specific workflows organized by platform

## Import Paths

When importing from tests or other modules:

```python
# From tests/ folder
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from audio_splitter_drive import send_webhook

# From deployment scripts
PYTHONPATH="../src:$PYTHONPATH" python script.py
```

## File Categories

- **Core Application**: `src/` - Production code that runs in Cloud Run
- **Testing Infrastructure**: `tests/` - All testing utilities and scripts
- **Configuration**: `config/` - Credentials and configuration files
- **Deployment**: `deployment/` - Docker, Cloud Build, deployment scripts
- **Documentation**: `docs/` - Setup guides and technical documentation
- **Workflows**: `workflows/` - External platform integrations (n8n, GitHub Actions)
- **Development**: `scripts/` - Development environment setup utilities