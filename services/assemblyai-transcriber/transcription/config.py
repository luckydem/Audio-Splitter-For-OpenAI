"""
Configuration management for transcription providers
"""
import os
import json
from typing import Dict, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum

from .factory import ProviderType


class SelectionStrategy(Enum):
    """Provider selection strategies"""
    COST_OPTIMIZED = "cost_optimized"      # Minimize cost
    SPEED_OPTIMIZED = "speed_optimized"    # Minimize processing time
    QUALITY_OPTIMIZED = "quality_optimized" # Maximum accuracy
    MANUAL = "manual"                      # User-specified provider
    AUTO = "auto"                          # Smart selection based on file


@dataclass
class ProviderConfig:
    """Configuration for a transcription provider"""
    enabled: bool = True
    api_key: Optional[str] = None
    model: Optional[str] = None
    language: Optional[str] = None
    features: Dict[str, bool] = None
    
    def __post_init__(self):
        if self.features is None:
            self.features = {}


@dataclass
class TranscriptionConfig:
    """Global transcription configuration"""
    # Provider configurations
    openai: ProviderConfig = None
    assemblyai: ProviderConfig = None
    
    # Selection strategy
    selection_strategy: SelectionStrategy = SelectionStrategy.AUTO
    default_provider: ProviderType = ProviderType.ASSEMBLYAI
    
    # File size thresholds (in MB)
    small_file_threshold: float = 25.0  # Files under this use OpenAI
    large_file_threshold: float = 100.0  # Files over this use AssemblyAI
    
    # Feature preferences
    require_speaker_diarization: bool = False
    require_word_timestamps: bool = True
    require_language_detection: bool = True
    
    # Cost preferences
    max_cost_per_hour: Optional[float] = None
    prefer_free_tier: bool = False
    
    # Performance preferences
    max_processing_time_ratio: float = 0.5  # Max 0.5x real-time
    allow_chunking: bool = True
    
    def __post_init__(self):
        # Initialize provider configs if not provided
        if self.openai is None:
            self.openai = ProviderConfig(
                api_key=os.getenv('OPENAI_API_KEY'),
                model='whisper-1'
            )
        
        if self.assemblyai is None:
            self.assemblyai = ProviderConfig(
                api_key=os.getenv('ASSEMBLYAI_API_KEY'),
                model='universal',
                features={
                    'speaker_diarization': True,
                    'auto_chapters': False,
                    'entity_detection': False,
                    'sentiment_analysis': False
                }
            )
    
    @classmethod
    def from_env(cls) -> 'TranscriptionConfig':
        """Create configuration from environment variables"""
        config = cls()
        
        # Override with environment variables if present
        if os.getenv('TRANSCRIPTION_STRATEGY'):
            try:
                config.selection_strategy = SelectionStrategy(os.getenv('TRANSCRIPTION_STRATEGY'))
            except ValueError:
                pass
        
        if os.getenv('DEFAULT_TRANSCRIPTION_PROVIDER'):
            try:
                config.default_provider = ProviderType(os.getenv('DEFAULT_TRANSCRIPTION_PROVIDER'))
            except ValueError:
                pass
        
        # Provider-specific settings
        if os.getenv('OPENAI_MODEL'):
            config.openai.model = os.getenv('OPENAI_MODEL')
        
        if os.getenv('ASSEMBLYAI_MODEL'):
            config.assemblyai.model = os.getenv('ASSEMBLYAI_MODEL')
        
        return config
    
    @classmethod
    def from_file(cls, file_path: str) -> 'TranscriptionConfig':
        """Load configuration from JSON file"""
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        # Parse provider configs
        if 'openai' in data:
            data['openai'] = ProviderConfig(**data['openai'])
        
        if 'assemblyai' in data:
            data['assemblyai'] = ProviderConfig(**data['assemblyai'])
        
        # Parse strategy
        if 'selection_strategy' in data:
            data['selection_strategy'] = SelectionStrategy(data['selection_strategy'])
        
        if 'default_provider' in data:
            data['default_provider'] = ProviderType(data['default_provider'])
        
        return cls(**data)
    
    def to_file(self, file_path: str):
        """Save configuration to JSON file"""
        data = asdict(self)
        
        # Convert enums to strings
        data['selection_strategy'] = self.selection_strategy.value
        data['default_provider'] = self.default_provider.value
        
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def select_provider(
        self,
        file_size: int,
        duration: Optional[float] = None,
        features_required: Optional[set] = None
    ) -> ProviderType:
        """
        Select provider based on configuration and file characteristics
        
        Args:
            file_size: File size in bytes
            duration: Audio duration in seconds
            features_required: Set of required features
            
        Returns:
            Selected provider type
        """
        file_size_mb = file_size / (1024 * 1024)
        
        # Manual strategy - always use default
        if self.selection_strategy == SelectionStrategy.MANUAL:
            return self.default_provider
        
        # Check if providers are enabled
        if not self.openai.enabled and self.assemblyai.enabled:
            return ProviderType.ASSEMBLYAI
        elif self.openai.enabled and not self.assemblyai.enabled:
            return ProviderType.OPENAI
        elif not self.openai.enabled and not self.assemblyai.enabled:
            raise ValueError("No providers enabled")
        
        # Cost optimized strategy
        if self.selection_strategy == SelectionStrategy.COST_OPTIMIZED:
            # AssemblyAI is generally more cost-effective for longer content
            if duration and duration > 1800:  # > 30 minutes
                return ProviderType.ASSEMBLYAI
            elif file_size_mb <= 25:
                return ProviderType.OPENAI
            else:
                return ProviderType.ASSEMBLYAI
        
        # Speed optimized strategy
        elif self.selection_strategy == SelectionStrategy.SPEED_OPTIMIZED:
            # OpenAI for small files (no polling needed)
            # AssemblyAI for large files (no chunking needed)
            if file_size_mb <= 25:
                return ProviderType.OPENAI
            else:
                return ProviderType.ASSEMBLYAI
        
        # Quality optimized strategy
        elif self.selection_strategy == SelectionStrategy.QUALITY_OPTIMIZED:
            # Use AssemblyAI Slam-1 for best quality
            self.assemblyai.model = 'slam-1'
            return ProviderType.ASSEMBLYAI
        
        # Auto strategy (default)
        else:
            # Check feature requirements
            if features_required:
                assemblyai_only = {
                    'entity_detection', 'sentiment_analysis', 
                    'auto_chapters', 'pii_redaction', 'direct_url_support'
                }
                if features_required.intersection(assemblyai_only):
                    return ProviderType.ASSEMBLYAI
            
            # Size-based selection
            if file_size_mb <= self.small_file_threshold:
                return ProviderType.OPENAI
            elif file_size_mb >= self.large_file_threshold:
                return ProviderType.ASSEMBLYAI
            else:
                # Medium files - consider other factors
                if self.require_speaker_diarization:
                    return ProviderType.ASSEMBLYAI
                elif duration and duration > 3600:  # > 1 hour
                    return ProviderType.ASSEMBLYAI
                else:
                    return self.default_provider


# Global configuration instance
_config: Optional[TranscriptionConfig] = None


def get_config() -> TranscriptionConfig:
    """Get the global transcription configuration"""
    global _config
    if _config is None:
        # Try to load from file first
        config_file = os.getenv('TRANSCRIPTION_CONFIG_FILE', 'transcription_config.json')
        if os.path.exists(config_file):
            _config = TranscriptionConfig.from_file(config_file)
        else:
            # Fall back to environment variables
            _config = TranscriptionConfig.from_env()
    return _config


def set_config(config: TranscriptionConfig):
    """Set the global transcription configuration"""
    global _config
    _config = config


def reset_config():
    """Reset configuration to defaults"""
    global _config
    _config = None