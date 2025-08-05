"""
AssemblyAI transcription provider
"""
import os
import asyncio
import aiohttp
import logging
from typing import Dict, List, Optional, Set, Any
from datetime import datetime
import time
import json

from .base import TranscriptionProvider, TranscriptionResult, TranscriptionError, ChunkResult

logger = logging.getLogger(__name__)


class AssemblyAIProvider(TranscriptionProvider):
    """AssemblyAI transcription provider"""
    
    BASE_URL = "https://api.assemblyai.com/v2"
    UPLOAD_URL = f"{BASE_URL}/upload"
    TRANSCRIPT_URL = f"{BASE_URL}/transcript"
    
    MAX_FILE_SIZE = 5 * 1024 * 1024 * 1024  # 5GB
    MAX_DURATION = 36000  # 10 hours
    SUPPORTED_FORMATS = {
        '.mp3', '.mp4', '.mpeg', '.mpga', '.m4a', '.wav', '.webm',
        '.aac', '.flac', '.ogg', '.opus', '.wma', '.amr', '.3gp',
        '.3gpp', '.avi', '.mov', '.wmv', '.flv', '.mkv'
    }
    
    # Available models
    MODELS = {
        'slam-1': {
            'supports_language_detection': False,
            'requires_language': True,
            'supports_prompts': True,
            'description': 'Most advanced model with prompt customization'
        },
        'universal': {
            'supports_language_detection': True,
            'requires_language': False,
            'supports_prompts': False,
            'description': 'General-purpose model supporting 99 languages'
        },
        'universal-streaming': {
            'supports_language_detection': True,
            'requires_language': False,
            'supports_prompts': False,
            'description': 'Optimized for real-time streaming'
        }
    }
    
    def _validate_config(self) -> None:
        """Validate AssemblyAI configuration"""
        if not self.api_key:
            raise TranscriptionError("AssemblyAI API key is required")
        
        # Set default model if not specified
        if 'model' not in self.config:
            self.config['model'] = 'universal'  # Default to universal for auto language detection
        
        # Validate model
        if self.config['model'] not in self.MODELS:
            raise TranscriptionError(f"Invalid model: {self.config['model']}")
    
    async def transcribe_file(self, file_path: str, **kwargs) -> TranscriptionResult:
        """Transcribe an audio file using AssemblyAI"""
        if not os.path.exists(file_path):
            raise TranscriptionError(f"File not found: {file_path}")
        
        start_time = time.time()
        
        # Upload file first
        upload_url = await self._upload_file(file_path)
        
        # Create transcript
        transcript_id = await self._create_transcript(upload_url, **kwargs)
        
        # Poll for completion
        result = await self._poll_transcript(transcript_id)
        
        processing_time = time.time() - start_time
        
        # Parse result into TranscriptionResult
        return self._parse_result(result, processing_time)
    
    async def transcribe_url(self, audio_url: str, **kwargs) -> TranscriptionResult:
        """Transcribe audio from a URL - AssemblyAI supports this natively"""
        start_time = time.time()
        
        # Create transcript directly from URL
        transcript_id = await self._create_transcript(audio_url, **kwargs)
        
        # Poll for completion
        result = await self._poll_transcript(transcript_id)
        
        processing_time = time.time() - start_time
        
        # Parse result into TranscriptionResult
        return self._parse_result(result, processing_time)
    
    async def transcribe_chunks(self, chunks: List[Dict[str, Any]], **kwargs) -> List[ChunkResult]:
        """Transcribe multiple chunks - AssemblyAI doesn't need chunking usually"""
        # For compatibility, we can still handle chunks
        # But this is rarely needed with AssemblyAI's 5GB limit
        
        chunk_results = []
        
        for chunk in chunks:
            if 'file_path' in chunk:
                result = await self.transcribe_file(chunk['file_path'], **kwargs)
            elif 'url' in chunk:
                result = await self.transcribe_url(chunk['url'], **kwargs)
            else:
                raise TranscriptionError(f"Chunk missing file_path or url: {chunk}")
            
            chunk_results.append(ChunkResult(
                chunk_number=chunk.get('chunk_number', 0),
                text=result.text,
                start_time=chunk.get('start_time', 0),
                end_time=chunk.get('end_time', 0),
                confidence=result.confidence,
                processing_time=result.processing_time
            ))
        
        return chunk_results
    
    async def _upload_file(self, file_path: str) -> str:
        """Upload file to AssemblyAI and return upload URL"""
        logger.info(f"Uploading file to AssemblyAI: {file_path}")
        
        async with aiohttp.ClientSession() as session:
            with open(file_path, 'rb') as f:
                file_data = f.read()
            
            file_size_mb = len(file_data) / (1024 * 1024)
            logger.info(f"File size: {file_size_mb:.2f} MB")
            
            headers = {"Authorization": f"Bearer {self.api_key}"}
            
            upload_start = time.time()
            async with session.post(self.UPLOAD_URL, data=file_data, headers=headers) as response:
                upload_time = time.time() - upload_start
                
                if response.status == 200:
                    result = await response.json()
                    upload_url = result['upload_url']
                    logger.info(f"✅ File uploaded successfully in {upload_time:.2f}s")
                    return upload_url
                else:
                    error = await response.text()
                    raise TranscriptionError(f"Upload failed: {response.status} - {error}")
    
    async def _create_transcript(self, audio_url: str, **kwargs) -> str:
        """Create transcript job and return transcript ID"""
        model = kwargs.get('model', self.config['model'])
        model_config = self.MODELS[model]
        
        logger.info(f"Creating transcript job with model: {model}")
        
        # Prepare request data
        data = {
            "audio_url": audio_url,
            "speech_model": model,
            "punctuate": True,
            "format_text": True,
        }
        
        # Add features based on configuration
        if kwargs.get('speaker_diarization', True):
            data["speaker_labels"] = True
        
        if kwargs.get('auto_chapters', False):
            data["auto_chapters"] = True
        
        if kwargs.get('entity_detection', False):
            data["entity_detection"] = True
        
        if kwargs.get('sentiment_analysis', False):
            data["sentiment_analysis"] = True
        
        # Handle language configuration based on model
        language = kwargs.get('language')
        if model == 'slam-1':
            # Slam-1 requires language code
            data["language_code"] = language or "en"
            logger.info(f"Using language: {data['language_code']}")
            
            # Add prompt if provided
            if 'prompt' in kwargs:
                data["prompt"] = kwargs['prompt']
                logger.info(f"Using prompt: {kwargs['prompt'][:100]}...")
        else:
            # Universal models support auto detection
            if language:
                data["language_code"] = language
            else:
                data["language_detection"] = True
        
        # Add webhook if provided
        if 'webhook_url' in kwargs:
            data["webhook_url"] = kwargs['webhook_url']
            if 'webhook_auth_header' in kwargs:
                data["webhook_auth_header_name"] = kwargs['webhook_auth_header']['name']
                data["webhook_auth_header_value"] = kwargs['webhook_auth_header']['value']
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "content-type": "application/json"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(self.TRANSCRIPT_URL, json=data, headers=headers) as response:
                if response.status in (200, 201):
                    result = await response.json()
                    transcript_id = result['id']
                    logger.info(f"✅ Transcript job created: {transcript_id}")
                    return transcript_id
                else:
                    error = await response.text()
                    raise TranscriptionError(f"Transcript creation failed: {response.status} - {error}")
    
    async def _poll_transcript(self, transcript_id: str) -> Dict:
        """Poll for transcript completion"""
        logger.info(f"Polling transcript status for ID: {transcript_id}")
        
        poll_start = time.time()
        poll_count = 0
        
        headers = {"Authorization": f"Bearer {self.api_key}"}
        
        async with aiohttp.ClientSession() as session:
            while True:
                poll_count += 1
                
                async with session.get(
                    f"{self.TRANSCRIPT_URL}/{transcript_id}", 
                    headers=headers
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        status = result['status']
                        
                        if status == 'completed':
                            poll_time = time.time() - poll_start
                            logger.info(
                                f"✅ Transcript completed in {poll_time:.2f}s "
                                f"after {poll_count} polls"
                            )
                            return result
                        elif status == 'error':
                            error_msg = result.get('error', 'Unknown error')
                            raise TranscriptionError(f"Transcript failed: {error_msg}")
                        else:
                            # Status: queued, processing
                            logger.info(f"Status: {status} (poll #{poll_count})")
                    else:
                        error = await response.text()
                        raise TranscriptionError(f"Poll failed: {response.status} - {error}")
                
                # Wait before next poll (with backoff)
                wait_time = min(3 * (1.2 ** min(poll_count, 10)), 30)  # Max 30s
                await asyncio.sleep(wait_time)
    
    def _parse_result(self, result: Dict, processing_time: float) -> TranscriptionResult:
        """Parse AssemblyAI result into TranscriptionResult"""
        # Extract duration from audio_duration field (in milliseconds)
        duration = result.get('audio_duration', 0) / 1000.0  # Convert to seconds
        
        # Build words list if available
        words = None
        if 'words' in result:
            words = [
                {
                    'text': w['text'],
                    'start': w['start'] / 1000.0,  # Convert to seconds
                    'end': w['end'] / 1000.0,
                    'confidence': w.get('confidence')
                }
                for w in result['words']
            ]
        
        # Build segments/utterances if available
        segments = None
        if 'utterances' in result:
            segments = [
                {
                    'text': u['text'],
                    'start': u['start'] / 1000.0,
                    'end': u['end'] / 1000.0,
                    'speaker': u.get('speaker'),
                    'confidence': u.get('confidence')
                }
                for u in result['utterances']
            ]
        
        # Extract speakers if available
        speakers = None
        if 'utterances' in result and any('speaker' in u for u in result['utterances']):
            speaker_set = set(u.get('speaker') for u in result['utterances'] if u.get('speaker'))
            speakers = [{'id': s, 'label': s} for s in sorted(speaker_set)]
        
        return TranscriptionResult(
            text=result['text'],
            duration=duration,
            processing_time=processing_time,
            confidence=result.get('confidence'),
            language=result.get('language_code'),
            words=words,
            segments=segments,
            speakers=speakers,
            metadata={
                'provider': 'assemblyai',
                'model': result.get('speech_model'),
                'transcript_id': result['id'],
                'audio_url': result.get('audio_url'),
                'chapters': result.get('chapters'),
                'entities': result.get('entities'),
                'sentiment_analysis': result.get('sentiment_analysis_results')
            }
        )
    
    def get_file_size_limit(self) -> int:
        """Get AssemblyAI's file size limit"""
        return self.MAX_FILE_SIZE
    
    def get_duration_limit(self) -> int:
        """Get AssemblyAI's duration limit"""
        return self.MAX_DURATION
    
    def get_supported_formats(self) -> Set[str]:
        """Get supported audio formats"""
        return self.SUPPORTED_FORMATS
    
    def requires_chunking(self, file_size: int, duration: float = None) -> bool:
        """Check if file requires chunking - rarely needed with AssemblyAI"""
        # AssemblyAI supports up to 5GB files
        if file_size > self.MAX_FILE_SIZE:
            return True
        
        # Check duration if provided
        if duration and duration > self.MAX_DURATION:
            return True
        
        return False
    
    def estimate_cost(self, duration: float) -> float:
        """Estimate AssemblyAI transcription cost"""
        # AssemblyAI pricing (as of 2025):
        # - First 100 hours/month: ~$0.37/hour
        # - Volume discounts available
        hours = duration / 3600
        
        # Simplified pricing model
        if hours <= 100:
            cost_per_hour = 0.37
        else:
            # Assume 20% volume discount
            cost_per_hour = 0.30
        
        return hours * cost_per_hour
    
    def get_supported_features(self) -> Set[str]:
        """Get AssemblyAI supported features"""
        return {
            'language_detection',      # Auto-detect language (Universal models)
            'language_specification',  # Specify language
            'speaker_diarization',     # Speaker labels
            'word_timestamps',         # Word-level timing
            'auto_punctuation',        # Automatic punctuation
            'profanity_filtering',     # Filter profanity
            'custom_vocabulary',       # Boost specific words
            'entity_detection',        # Detect entities
            'sentiment_analysis',      # Analyze sentiment
            'auto_chapters',          # Generate chapters
            'pii_redaction',          # Redact sensitive info
            'custom_prompts',         # Slam-1 prompts
            'webhook_notifications',   # Async webhooks
            'multiple_models',        # slam-1, universal, etc.
            'direct_url_support',     # No download needed
        }