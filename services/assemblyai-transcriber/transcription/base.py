"""
Base classes and interfaces for transcription providers
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class TranscriptionResult:
    """Unified transcription result across all providers"""
    text: str
    duration: float  # Audio duration in seconds
    processing_time: float  # Processing time in seconds
    confidence: Optional[float] = None
    language: Optional[str] = None
    words: Optional[List[Dict[str, Any]]] = None  # Word-level timestamps
    segments: Optional[List[Dict[str, Any]]] = None  # Segment/sentence-level data
    speakers: Optional[List[Dict[str, Any]]] = None  # Speaker diarization data
    metadata: Optional[Dict[str, Any]] = None  # Provider-specific metadata
    
    @property
    def word_count(self) -> int:
        """Get word count from transcript"""
        if self.words:
            return len(self.words)
        return len(self.text.split())
    
    @property
    def rtf(self) -> float:
        """Real-time factor (processing_time / duration)"""
        if self.duration > 0:
            return self.processing_time / self.duration
        return 0.0


@dataclass
class ChunkResult:
    """Result for a single chunk transcription"""
    chunk_number: int
    text: str
    start_time: float
    end_time: float
    confidence: Optional[float] = None
    processing_time: Optional[float] = None


class TranscriptionError(Exception):
    """Base exception for transcription errors"""
    pass


class TranscriptionProvider(ABC):
    """Abstract base class for all transcription providers"""
    
    def __init__(self, api_key: str, **kwargs):
        """
        Initialize provider with API key and optional configuration
        
        Args:
            api_key: API key for the transcription service
            **kwargs: Provider-specific configuration
        """
        self.api_key = api_key
        self.config = kwargs
        self._validate_config()
    
    @abstractmethod
    def _validate_config(self) -> None:
        """Validate provider-specific configuration"""
        pass
    
    @abstractmethod
    async def transcribe_file(self, file_path: str, **kwargs) -> TranscriptionResult:
        """
        Transcribe an audio file
        
        Args:
            file_path: Path to the audio file
            **kwargs: Provider-specific options (language, model, etc.)
            
        Returns:
            TranscriptionResult object
            
        Raises:
            TranscriptionError: If transcription fails
        """
        pass
    
    @abstractmethod
    async def transcribe_url(self, audio_url: str, **kwargs) -> TranscriptionResult:
        """
        Transcribe audio from a URL
        
        Args:
            audio_url: URL of the audio file
            **kwargs: Provider-specific options
            
        Returns:
            TranscriptionResult object
            
        Raises:
            TranscriptionError: If transcription fails
        """
        pass
    
    @abstractmethod
    async def transcribe_chunks(self, chunks: List[Dict[str, Any]], **kwargs) -> List[ChunkResult]:
        """
        Transcribe multiple audio chunks
        
        Args:
            chunks: List of chunk dictionaries with file paths or URLs
            **kwargs: Provider-specific options
            
        Returns:
            List of ChunkResult objects
            
        Raises:
            TranscriptionError: If transcription fails
        """
        pass
    
    @abstractmethod
    def get_file_size_limit(self) -> int:
        """
        Get maximum file size in bytes supported by this provider
        
        Returns:
            Maximum file size in bytes
        """
        pass
    
    @abstractmethod
    def get_duration_limit(self) -> int:
        """
        Get maximum audio duration in seconds supported by this provider
        
        Returns:
            Maximum duration in seconds
        """
        pass
    
    @abstractmethod
    def get_supported_formats(self) -> Set[str]:
        """
        Get set of supported audio formats (file extensions)
        
        Returns:
            Set of supported extensions (e.g., {'.mp3', '.wav', '.m4a'})
        """
        pass
    
    @abstractmethod
    def requires_chunking(self, file_size: int, duration: float = None) -> bool:
        """
        Check if a file requires chunking based on size and duration
        
        Args:
            file_size: File size in bytes
            duration: Audio duration in seconds (optional)
            
        Returns:
            True if chunking is required
        """
        pass
    
    @abstractmethod
    def estimate_cost(self, duration: float) -> float:
        """
        Estimate transcription cost for given duration
        
        Args:
            duration: Audio duration in seconds
            
        Returns:
            Estimated cost in USD
        """
        pass
    
    def supports_feature(self, feature: str) -> bool:
        """
        Check if provider supports a specific feature
        
        Args:
            feature: Feature name (e.g., 'speaker_diarization', 'word_timestamps')
            
        Returns:
            True if feature is supported
        """
        return feature in self.get_supported_features()
    
    @abstractmethod
    def get_supported_features(self) -> Set[str]:
        """
        Get set of supported features
        
        Returns:
            Set of feature names
        """
        pass
    
    def merge_chunk_results(self, chunk_results: List[ChunkResult]) -> TranscriptionResult:
        """
        Merge multiple chunk results into a single result
        
        Args:
            chunk_results: List of chunk results to merge
            
        Returns:
            Merged TranscriptionResult
        """
        if not chunk_results:
            raise TranscriptionError("No chunk results to merge")
        
        # Sort by chunk number
        sorted_chunks = sorted(chunk_results, key=lambda x: x.chunk_number)
        
        # Merge text
        merged_text = " ".join(chunk.text.strip() for chunk in sorted_chunks)
        
        # Calculate total duration and processing time
        total_duration = sorted_chunks[-1].end_time
        total_processing_time = sum(
            chunk.processing_time for chunk in sorted_chunks 
            if chunk.processing_time is not None
        )
        
        # Average confidence if available
        confidences = [chunk.confidence for chunk in sorted_chunks if chunk.confidence is not None]
        avg_confidence = sum(confidences) / len(confidences) if confidences else None
        
        return TranscriptionResult(
            text=merged_text,
            duration=total_duration,
            processing_time=total_processing_time,
            confidence=avg_confidence,
            metadata={
                'chunk_count': len(chunk_results),
                'method': 'chunked'
            }
        )