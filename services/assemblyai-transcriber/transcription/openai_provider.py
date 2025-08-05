"""
OpenAI Whisper API transcription provider
"""
import os
import asyncio
import aiohttp
import logging
from typing import Dict, List, Optional, Set, Any
from datetime import datetime
import time

from .base import TranscriptionProvider, TranscriptionResult, TranscriptionError, ChunkResult

logger = logging.getLogger(__name__)


class OpenAIProvider(TranscriptionProvider):
    """OpenAI Whisper API transcription provider"""
    
    API_URL = "https://api.openai.com/v1/audio/transcriptions"
    MAX_FILE_SIZE = 25 * 1024 * 1024  # 25MB
    MAX_DURATION = 10800  # 3 hours (practical limit)
    SUPPORTED_FORMATS = {'.mp3', '.mp4', '.mpeg', '.mpga', '.m4a', '.wav', '.webm'}
    
    # Timeout configurations (from existing code)
    API_TIMEOUT = 600  # 10 minutes
    CONNECT_TIMEOUT = 30  # 30 seconds
    READ_TIMEOUT = 300  # 5 minutes
    
    # Connection pool configuration
    CONNECTION_LIMIT = 20
    CONNECTION_LIMIT_PER_HOST = 10
    
    def _validate_config(self) -> None:
        """Validate OpenAI configuration"""
        if not self.api_key:
            raise TranscriptionError("OpenAI API key is required")
        
        # Set default model if not specified
        if 'model' not in self.config:
            self.config['model'] = 'whisper-1'
    
    async def transcribe_file(self, file_path: str, **kwargs) -> TranscriptionResult:
        """Transcribe an audio file using OpenAI Whisper"""
        if not os.path.exists(file_path):
            raise TranscriptionError(f"File not found: {file_path}")
        
        file_size = os.path.getsize(file_path)
        if file_size > self.MAX_FILE_SIZE:
            raise TranscriptionError(
                f"File size {file_size / (1024*1024):.1f}MB exceeds OpenAI limit of 25MB. "
                "Use chunking or a different provider."
            )
        
        start_time = time.time()
        
        # Create connector with connection pooling
        connector = aiohttp.TCPConnector(
            limit=self.CONNECTION_LIMIT,
            limit_per_host=self.CONNECTION_LIMIT_PER_HOST,
            force_close=True
        )
        
        # Create timeout config
        timeout_config = aiohttp.ClientTimeout(
            total=self.API_TIMEOUT,
            sock_connect=self.CONNECT_TIMEOUT,
            sock_read=self.READ_TIMEOUT
        )
        
        async with aiohttp.ClientSession(timeout=timeout_config, connector=connector) as session:
            with open(file_path, 'rb') as audio_file:
                audio_data = audio_file.read()
                filename = os.path.basename(file_path)
                
                # Determine content type
                file_ext = os.path.splitext(filename.lower())[1]
                content_type_map = {
                    '.mp3': 'audio/mpeg',
                    '.mp4': 'audio/mp4',
                    '.m4a': 'audio/mp4',
                    '.wav': 'audio/wav',
                    '.webm': 'audio/webm'
                }
                content_type = content_type_map.get(file_ext, 'audio/mpeg')
                
                # Create form data
                data = aiohttp.FormData()
                data.add_field('file', audio_data, filename=filename, content_type=content_type)
                data.add_field('model', kwargs.get('model', self.config['model']))
                
                # Add optional parameters
                if 'language' in kwargs:
                    data.add_field('language', kwargs['language'])
                if 'prompt' in kwargs:
                    data.add_field('prompt', kwargs['prompt'])
                if 'temperature' in kwargs:
                    data.add_field('temperature', str(kwargs['temperature']))
                
                logger.info(f"Sending {len(audio_data)/(1024*1024):.1f}MB file to OpenAI Whisper API")
                
                try:
                    async with session.post(
                        self.API_URL,
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        data=data
                    ) as resp:
                        processing_time = time.time() - start_time
                        
                        if resp.status == 200:
                            result = await resp.json()
                            logger.info(f"✅ OpenAI transcription successful in {processing_time:.1f}s")
                            
                            # Get audio duration
                            try:
                                # Import here to avoid circular imports
                                from split_audio import get_audio_info
                                duration, _, _ = get_audio_info(file_path)
                            except:
                                # Fallback to estimation
                                duration = self._estimate_duration(file_path, file_size)
                            
                            return TranscriptionResult(
                                text=result['text'],
                                duration=duration,
                                processing_time=processing_time,
                                language=kwargs.get('language'),
                                metadata={
                                    'provider': 'openai',
                                    'model': kwargs.get('model', self.config['model']),
                                    'method': 'direct'
                                }
                            )
                        else:
                            error_text = await resp.text()
                            raise TranscriptionError(f"OpenAI API error: {resp.status} - {error_text}")
                            
                except asyncio.TimeoutError:
                    raise TranscriptionError(f"OpenAI API timeout after {time.time() - start_time:.1f}s")
                except aiohttp.ClientError as e:
                    raise TranscriptionError(f"Network error: {str(e)}")
    
    async def transcribe_url(self, audio_url: str, **kwargs) -> TranscriptionResult:
        """OpenAI doesn't support direct URL transcription, need to download first"""
        raise NotImplementedError(
            "OpenAI doesn't support direct URL transcription. "
            "Download the file first and use transcribe_file()."
        )
    
    async def transcribe_chunks(self, chunks: List[Dict[str, Any]], **kwargs) -> List[ChunkResult]:
        """Transcribe multiple chunks in parallel"""
        # Create connector for parallel requests
        connector = aiohttp.TCPConnector(
            limit=self.CONNECTION_LIMIT,
            limit_per_host=self.CONNECTION_LIMIT_PER_HOST,
            force_close=True
        )
        
        timeout_config = aiohttp.ClientTimeout(
            total=self.API_TIMEOUT,
            sock_connect=self.CONNECT_TIMEOUT,
            sock_read=self.READ_TIMEOUT
        )
        
        async with aiohttp.ClientSession(timeout=timeout_config, connector=connector) as session:
            tasks = []
            for chunk in chunks:
                task = self._transcribe_single_chunk(session, chunk, **kwargs)
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results and handle errors
            chunk_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Chunk {i+1} failed: {str(result)}")
                    # Could implement retry logic here
                    raise TranscriptionError(f"Chunk {i+1} transcription failed: {str(result)}")
                else:
                    chunk_results.append(result)
            
            return chunk_results
    
    async def _transcribe_single_chunk(self, session: aiohttp.ClientSession, 
                                     chunk: Dict[str, Any], **kwargs) -> ChunkResult:
        """Transcribe a single chunk"""
        chunk_num = chunk.get('chunk_number', 0)
        file_path = chunk.get('file_path')
        
        if not file_path or not os.path.exists(file_path):
            raise TranscriptionError(f"Chunk {chunk_num}: Invalid file path")
        
        start_time = time.time()
        
        with open(file_path, 'rb') as audio_file:
            audio_data = audio_file.read()
            filename = os.path.basename(file_path)
            
            # Create form data
            data = aiohttp.FormData()
            data.add_field('file', audio_data, filename=filename)
            data.add_field('model', kwargs.get('model', self.config['model']))
            
            if 'language' in kwargs:
                data.add_field('language', kwargs['language'])
            
            async with session.post(
                self.API_URL,
                headers={"Authorization": f"Bearer {self.api_key}"},
                data=data
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    processing_time = time.time() - start_time
                    
                    return ChunkResult(
                        chunk_number=chunk_num,
                        text=result['text'],
                        start_time=chunk.get('start_time', 0),
                        end_time=chunk.get('end_time', 0),
                        processing_time=processing_time
                    )
                else:
                    error_text = await resp.text()
                    raise TranscriptionError(
                        f"Chunk {chunk_num} - OpenAI API error: {resp.status} - {error_text}"
                    )
    
    def get_file_size_limit(self) -> int:
        """Get OpenAI's file size limit"""
        return self.MAX_FILE_SIZE
    
    def get_duration_limit(self) -> int:
        """Get OpenAI's duration limit"""
        return self.MAX_DURATION
    
    def get_supported_formats(self) -> Set[str]:
        """Get supported audio formats"""
        return self.SUPPORTED_FORMATS
    
    def requires_chunking(self, file_size: int, duration: float = None) -> bool:
        """Check if file requires chunking"""
        # OpenAI requires chunking if file exceeds 25MB
        return file_size > self.MAX_FILE_SIZE
    
    def estimate_cost(self, duration: float) -> float:
        """Estimate OpenAI transcription cost"""
        # OpenAI Whisper pricing: $0.006 per minute
        minutes = duration / 60
        return minutes * 0.006
    
    def get_supported_features(self) -> Set[str]:
        """Get OpenAI supported features"""
        return {
            'language_detection',  # Via omitting language parameter
            'language_specification',
            'prompt_injection',  # Custom vocabulary via prompt
            'temperature_control',
            'multiple_models',  # whisper-1
        }
    
    def _estimate_duration(self, file_path: str, file_size: int) -> float:
        """Estimate audio duration from file size"""
        # This is a rough estimate - in production, use get_audio_info
        # Assume average bitrate of 128kbps for compressed formats
        file_ext = os.path.splitext(file_path.lower())[1]
        
        if file_ext == '.wav':
            # WAV is typically 1411 kbps for CD quality
            bitrate = 1411000
        elif file_ext in ['.mp3', '.m4a']:
            # Compressed formats average ~128 kbps
            bitrate = 128000
        else:
            # Conservative estimate
            bitrate = 128000
        
        # Calculate duration: file_size (bytes) * 8 (bits/byte) / bitrate (bits/second)
        duration = (file_size * 8) / bitrate
        return duration