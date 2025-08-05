"""
Factory for creating transcription providers
"""
import os
import logging
from typing import Dict, Optional, Any
from enum import Enum

from .base import TranscriptionProvider, TranscriptionError
from .openai_provider import OpenAIProvider
from .assemblyai_provider import AssemblyAIProvider

logger = logging.getLogger(__name__)


class ProviderType(Enum):
    """Supported transcription providers"""
    OPENAI = "openai"
    ASSEMBLYAI = "assemblyai"
    AUTO = "auto"  # Automatic selection based on file characteristics


class TranscriptionFactory:
    """Factory for creating and managing transcription providers"""
    
    _providers: Dict[ProviderType, TranscriptionProvider] = {}
    
    @classmethod
    def create_provider(
        cls,
        provider_type: str | ProviderType,
        api_key: Optional[str] = None,
        **config
    ) -> TranscriptionProvider:
        """
        Create or get a transcription provider
        
        Args:
            provider_type: Type of provider (openai, assemblyai, auto)
            api_key: API key for the provider (can use env vars)
            **config: Provider-specific configuration
            
        Returns:
            TranscriptionProvider instance
            
        Raises:
            TranscriptionError: If provider creation fails
        """
        # Convert string to enum
        if isinstance(provider_type, str):
            try:
                provider_type = ProviderType(provider_type.lower())
            except ValueError:
                raise TranscriptionError(f"Invalid provider type: {provider_type}")
        
        # Handle AUTO selection (will be implemented later)
        if provider_type == ProviderType.AUTO:
            raise NotImplementedError("Automatic provider selection not yet implemented")
        
        # Check if provider already exists
        if provider_type in cls._providers:
            return cls._providers[provider_type]
        
        # Get API key from environment if not provided
        if not api_key:
            if provider_type == ProviderType.OPENAI:
                api_key = os.getenv('OPENAI_API_KEY')
            elif provider_type == ProviderType.ASSEMBLYAI:
                api_key = os.getenv('ASSEMBLYAI_API_KEY')
            
            if not api_key:
                raise TranscriptionError(f"No API key provided for {provider_type.value}")
        
        # Create provider instance
        try:
            if provider_type == ProviderType.OPENAI:
                provider = OpenAIProvider(api_key, **config)
            elif provider_type == ProviderType.ASSEMBLYAI:
                provider = AssemblyAIProvider(api_key, **config)
            else:
                raise TranscriptionError(f"Unknown provider type: {provider_type}")
            
            # Cache provider instance
            cls._providers[provider_type] = provider
            logger.info(f"Created {provider_type.value} provider")
            
            return provider
            
        except Exception as e:
            raise TranscriptionError(f"Failed to create {provider_type.value} provider: {str(e)}")
    
    @classmethod
    def get_provider(cls, provider_type: str | ProviderType) -> Optional[TranscriptionProvider]:
        """
        Get an existing provider instance
        
        Args:
            provider_type: Type of provider
            
        Returns:
            Provider instance or None if not created
        """
        if isinstance(provider_type, str):
            try:
                provider_type = ProviderType(provider_type.lower())
            except ValueError:
                return None
        
        return cls._providers.get(provider_type)
    
    @classmethod
    def select_optimal_provider(
        cls,
        file_size: int,
        duration: Optional[float] = None,
        features_required: Optional[set] = None,
        cost_sensitive: bool = True
    ) -> ProviderType:
        """
        Select optimal provider based on file characteristics and requirements
        
        Args:
            file_size: File size in bytes
            duration: Audio duration in seconds (optional)
            features_required: Set of required features (optional)
            cost_sensitive: Whether to optimize for cost (default: True)
            
        Returns:
            Recommended provider type
        """
        # Simple selection logic for now
        # Can be enhanced with more sophisticated rules
        
        file_size_mb = file_size / (1024 * 1024)
        
        # If file is small enough for OpenAI and no special features needed
        if file_size_mb <= 25 and not features_required:
            # OpenAI is simpler for small files (no polling required)
            return ProviderType.OPENAI
        
        # If file is large or needs special features
        if file_size_mb > 25:
            # AssemblyAI handles large files without chunking
            return ProviderType.ASSEMBLYAI
        
        # Check feature requirements
        if features_required:
            assemblyai_only_features = {
                'entity_detection', 'sentiment_analysis', 'auto_chapters',
                'pii_redaction', 'direct_url_support', 'custom_prompts'
            }
            
            if features_required.intersection(assemblyai_only_features):
                return ProviderType.ASSEMBLYAI
        
        # Duration-based selection
        if duration:
            if duration > 3600:  # > 1 hour
                # AssemblyAI is more cost-effective for long content
                return ProviderType.ASSEMBLYAI if cost_sensitive else ProviderType.OPENAI
        
        # Default to OpenAI for small, simple files
        return ProviderType.OPENAI
    
    @classmethod
    def clear_cache(cls):
        """Clear cached provider instances"""
        cls._providers.clear()
        logger.info("Cleared provider cache")
    
    @classmethod
    def get_provider_info(cls, provider_type: str | ProviderType) -> Dict[str, Any]:
        """
        Get information about a provider
        
        Args:
            provider_type: Type of provider
            
        Returns:
            Dictionary with provider information
        """
        if isinstance(provider_type, str):
            try:
                provider_type = ProviderType(provider_type.lower())
            except ValueError:
                raise TranscriptionError(f"Invalid provider type: {provider_type}")
        
        if provider_type == ProviderType.OPENAI:
            return {
                'name': 'OpenAI Whisper',
                'max_file_size_mb': 25,
                'max_duration_hours': 3,
                'requires_chunking': True,
                'supports_url': False,
                'pricing_per_minute': 0.006,
                'features': {
                    'language_detection', 'language_specification',
                    'prompt_injection', 'temperature_control'
                }
            }
        elif provider_type == ProviderType.ASSEMBLYAI:
            return {
                'name': 'AssemblyAI',
                'max_file_size_mb': 5120,  # 5GB
                'max_duration_hours': 10,
                'requires_chunking': False,
                'supports_url': True,
                'pricing_per_hour': 0.37,
                'features': {
                    'language_detection', 'speaker_diarization', 'entity_detection',
                    'sentiment_analysis', 'auto_chapters', 'pii_redaction',
                    'custom_prompts', 'direct_url_support'
                }
            }
        else:
            raise TranscriptionError(f"Unknown provider type: {provider_type}")