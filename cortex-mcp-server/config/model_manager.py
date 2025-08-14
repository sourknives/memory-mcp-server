"""
AI Model management system for the cortex mcp server.

This module provides comprehensive model management including:
- Automatic model downloads
- Model updates and version management
- Model health checks and validation
- Storage management and cleanup
"""

import os
import logging
import json
import hashlib
import subprocess
import threading
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import requests
from packaging import version

logger = logging.getLogger(__name__)


@dataclass
class ModelMetadata:
    """Metadata for a model."""
    name: str
    type: str  # 'embedding', 'llm'
    version: Optional[str] = None
    size_bytes: Optional[int] = None
    download_url: Optional[str] = None
    local_path: Optional[str] = None
    checksum: Optional[str] = None
    downloaded_at: Optional[datetime] = None
    last_used: Optional[datetime] = None
    auto_update: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        # Convert datetime objects to ISO strings
        if self.downloaded_at:
            data['downloaded_at'] = self.downloaded_at.isoformat()
        if self.last_used:
            data['last_used'] = self.last_used.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ModelMetadata':
        """Create from dictionary."""
        # Convert ISO strings back to datetime objects
        if 'downloaded_at' in data and data['downloaded_at']:
            data['downloaded_at'] = datetime.fromisoformat(data['downloaded_at'])
        if 'last_used' in data and data['last_used']:
            data['last_used'] = datetime.fromisoformat(data['last_used'])
        return cls(**data)


class ModelDownloadError(Exception):
    """Exception raised when model download fails."""
    pass


class ModelValidationError(Exception):
    """Exception raised when model validation fails."""
    pass


class ModelManager:
    """
    Manages AI models including downloads, updates, and cleanup.
    """
    
    # Known embedding models with metadata
    EMBEDDING_MODELS = {
        'all-MiniLM-L6-v2': {
            'size_mb': 22,
            'dimensions': 384,
            'description': 'Fast and efficient, good for most use cases'
        },
        'all-mpnet-base-v2': {
            'size_mb': 420,
            'dimensions': 768,
            'description': 'Higher quality embeddings, slower'
        },
        'all-distilroberta-v1': {
            'size_mb': 290,
            'dimensions': 768,
            'description': 'Good balance of speed and quality'
        },
        'paraphrase-MiniLM-L6-v2': {
            'size_mb': 22,
            'dimensions': 384,
            'description': 'Optimized for paraphrase detection'
        },
        'paraphrase-mpnet-base-v2': {
            'size_mb': 420,
            'dimensions': 768,
            'description': 'High quality paraphrase embeddings'
        }
    }
    
    # Known LLM models for Ollama
    LLM_MODELS = {
        'llama3.2:1b': {
            'size_mb': 1300,
            'description': 'Lightweight Llama model, good for basic tasks'
        },
        'llama3.2:3b': {
            'size_mb': 2000,
            'description': 'Balanced Llama model, better quality'
        },
        'qwen2.5:0.5b': {
            'size_mb': 395,
            'description': 'Ultra-lightweight model, very fast'
        },
        'qwen2.5:1.5b': {
            'size_mb': 934,
            'description': 'Small but capable model'
        },
        'phi3.5:3.8b': {
            'size_mb': 2200,
            'description': 'Microsoft Phi model, good reasoning'
        },
        'gemma2:2b': {
            'size_mb': 1600,
            'description': 'Google Gemma model, efficient'
        }
    }
    
    def __init__(self, cache_dir: str = "./models"):
        """
        Initialize model manager.
        
        Args:
            cache_dir: Directory to store models and metadata
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.metadata_file = self.cache_dir / "model_metadata.json"
        self.models: Dict[str, ModelMetadata] = {}
        self._lock = threading.RLock()
        
        # Load existing metadata
        self._load_metadata()
        
        logger.info(f"Model manager initialized with cache dir: {cache_dir}")
    
    def _load_metadata(self) -> None:
        """Load model metadata from file."""
        try:
            if self.metadata_file.exists():
                with open(self.metadata_file, 'r') as f:
                    data = json.load(f)
                
                for model_key, model_data in data.items():
                    self.models[model_key] = ModelMetadata.from_dict(model_data)
                
                logger.info(f"Loaded metadata for {len(self.models)} models")
            else:
                logger.info("No existing model metadata found")
                
        except Exception as e:
            logger.error(f"Failed to load model metadata: {e}")
            self.models = {}
    
    def _save_metadata(self) -> None:
        """Save model metadata to file."""
        try:
            data = {}
            for model_key, metadata in self.models.items():
                data[model_key] = metadata.to_dict()
            
            with open(self.metadata_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.debug("Model metadata saved")
            
        except Exception as e:
            logger.error(f"Failed to save model metadata: {e}")
    
    def _get_model_key(self, model_name: str, model_type: str) -> str:
        """Get unique key for model."""
        return f"{model_type}:{model_name}"
    
    def get_model_info(self, model_name: str, model_type: str) -> Optional[ModelMetadata]:
        """
        Get metadata for a model.
        
        Args:
            model_name: Name of the model
            model_type: Type of model ('embedding' or 'llm')
            
        Returns:
            ModelMetadata: Model metadata or None if not found
        """
        model_key = self._get_model_key(model_name, model_type)
        return self.models.get(model_key)
    
    def is_model_available(self, model_name: str, model_type: str) -> bool:
        """
        Check if a model is available locally.
        
        Args:
            model_name: Name of the model
            model_type: Type of model
            
        Returns:
            bool: True if model is available
        """
        model_info = self.get_model_info(model_name, model_type)
        if not model_info:
            return False
        
        if model_type == 'embedding':
            # Check if model directory exists and has files
            if model_info.local_path:
                model_path = Path(model_info.local_path)
                return model_path.exists() and any(model_path.iterdir())
        
        elif model_type == 'llm':
            # Check with Ollama
            return self._check_ollama_model(model_name)
        
        return False
    
    def _check_ollama_model(self, model_name: str) -> bool:
        """Check if Ollama model is available."""
        try:
            result = subprocess.run(
                ['ollama', 'list'],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0 and model_name in result.stdout
        except Exception as e:
            logger.debug(f"Failed to check Ollama model {model_name}: {e}")
            return False
    
    def download_model(
        self,
        model_name: str,
        model_type: str,
        force: bool = False,
        progress_callback: Optional[callable] = None
    ) -> bool:
        """
        Download a model if not already available.
        
        Args:
            model_name: Name of the model
            model_type: Type of model ('embedding' or 'llm')
            force: Force download even if model exists
            progress_callback: Optional callback for progress updates
            
        Returns:
            bool: True if download successful
        """
        with self._lock:
            model_key = self._get_model_key(model_name, model_type)
            
            # Check if already available
            if not force and self.is_model_available(model_name, model_type):
                logger.info(f"Model {model_name} already available")
                return True
            
            try:
                if model_type == 'embedding':
                    return self._download_embedding_model(model_name, progress_callback)
                elif model_type == 'llm':
                    return self._download_llm_model(model_name, progress_callback)
                else:
                    raise ModelDownloadError(f"Unknown model type: {model_type}")
                    
            except Exception as e:
                logger.error(f"Failed to download model {model_name}: {e}")
                return False
    
    def _download_embedding_model(
        self,
        model_name: str,
        progress_callback: Optional[callable] = None
    ) -> bool:
        """Download embedding model using sentence-transformers."""
        try:
            from sentence_transformers import SentenceTransformer
            
            logger.info(f"Downloading embedding model: {model_name}")
            
            if progress_callback:
                progress_callback(f"Starting download of {model_name}", 0)
            
            # Download model
            model = SentenceTransformer(model_name, cache_folder=str(self.cache_dir))
            
            # Get model path
            model_path = self.cache_dir / model_name
            
            # Create metadata
            model_key = self._get_model_key(model_name, 'embedding')
            metadata = ModelMetadata(
                name=model_name,
                type='embedding',
                local_path=str(model_path),
                downloaded_at=datetime.now(),
                last_used=datetime.now()
            )
            
            # Calculate size if possible
            if model_path.exists():
                total_size = sum(f.stat().st_size for f in model_path.rglob('*') if f.is_file())
                metadata.size_bytes = total_size
            
            self.models[model_key] = metadata
            self._save_metadata()
            
            if progress_callback:
                progress_callback(f"Downloaded {model_name}", 100)
            
            logger.info(f"Successfully downloaded embedding model: {model_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to download embedding model {model_name}: {e}")
            raise ModelDownloadError(f"Embedding model download failed: {e}")
    
    def _download_llm_model(
        self,
        model_name: str,
        progress_callback: Optional[callable] = None
    ) -> bool:
        """Download LLM model using Ollama."""
        try:
            logger.info(f"Downloading LLM model: {model_name}")
            
            if progress_callback:
                progress_callback(f"Starting download of {model_name}", 0)
            
            # Check if Ollama is available
            try:
                subprocess.run(['ollama', '--version'], capture_output=True, timeout=5)
            except Exception:
                raise ModelDownloadError("Ollama is not installed or not available")
            
            # Download model
            process = subprocess.Popen(
                ['ollama', 'pull', model_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Monitor progress
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output and progress_callback:
                    # Parse Ollama progress output
                    if 'pulling' in output.lower():
                        progress_callback(f"Pulling {model_name}: {output.strip()}", None)
            
            # Wait for completion
            stdout, stderr = process.communicate()
            
            if process.returncode != 0:
                raise ModelDownloadError(f"Ollama pull failed: {stderr}")
            
            # Create metadata
            model_key = self._get_model_key(model_name, 'llm')
            metadata = ModelMetadata(
                name=model_name,
                type='llm',
                downloaded_at=datetime.now(),
                last_used=datetime.now()
            )
            
            # Get model size from Ollama
            try:
                result = subprocess.run(
                    ['ollama', 'show', model_name],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    # Parse size from output (this is approximate)
                    if model_name in self.LLM_MODELS:
                        metadata.size_bytes = self.LLM_MODELS[model_name]['size_mb'] * 1024 * 1024
            except Exception:
                pass
            
            self.models[model_key] = metadata
            self._save_metadata()
            
            if progress_callback:
                progress_callback(f"Downloaded {model_name}", 100)
            
            logger.info(f"Successfully downloaded LLM model: {model_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to download LLM model {model_name}: {e}")
            raise ModelDownloadError(f"LLM model download failed: {e}")
    
    def validate_model(self, model_name: str, model_type: str) -> bool:
        """
        Validate that a model is working correctly.
        
        Args:
            model_name: Name of the model
            model_type: Type of model
            
        Returns:
            bool: True if model is valid
        """
        try:
            if model_type == 'embedding':
                return self._validate_embedding_model(model_name)
            elif model_type == 'llm':
                return self._validate_llm_model(model_name)
            else:
                return False
                
        except Exception as e:
            logger.error(f"Model validation failed for {model_name}: {e}")
            return False
    
    def _validate_embedding_model(self, model_name: str) -> bool:
        """Validate embedding model by testing encoding."""
        try:
            from sentence_transformers import SentenceTransformer
            
            model = SentenceTransformer(model_name, cache_folder=str(self.cache_dir))
            
            # Test encoding
            test_text = "This is a test sentence."
            embedding = model.encode(test_text)
            
            # Check if embedding is valid
            if embedding is None or len(embedding) == 0:
                return False
            
            logger.debug(f"Embedding model {model_name} validation successful")
            return True
            
        except Exception as e:
            logger.error(f"Embedding model validation failed: {e}")
            return False
    
    def _validate_llm_model(self, model_name: str) -> bool:
        """Validate LLM model by testing generation."""
        try:
            # Test with Ollama
            result = subprocess.run(
                ['ollama', 'run', model_name, 'Hello'],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0 and result.stdout.strip():
                logger.debug(f"LLM model {model_name} validation successful")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"LLM model validation failed: {e}")
            return False
    
    def update_model_usage(self, model_name: str, model_type: str) -> None:
        """
        Update last used timestamp for a model.
        
        Args:
            model_name: Name of the model
            model_type: Type of model
        """
        model_key = self._get_model_key(model_name, model_type)
        if model_key in self.models:
            self.models[model_key].last_used = datetime.now()
            self._save_metadata()
    
    def list_models(self, model_type: Optional[str] = None) -> List[ModelMetadata]:
        """
        List all managed models.
        
        Args:
            model_type: Optional filter by model type
            
        Returns:
            List[ModelMetadata]: List of model metadata
        """
        models = list(self.models.values())
        
        if model_type:
            models = [m for m in models if m.type == model_type]
        
        return sorted(models, key=lambda m: m.last_used or datetime.min, reverse=True)
    
    def get_available_models(self, model_type: str) -> List[str]:
        """
        Get list of available models for download.
        
        Args:
            model_type: Type of model
            
        Returns:
            List[str]: List of available model names
        """
        if model_type == 'embedding':
            return list(self.EMBEDDING_MODELS.keys())
        elif model_type == 'llm':
            return list(self.LLM_MODELS.keys())
        else:
            return []
    
    def get_model_recommendations(self, use_case: str = 'general') -> Dict[str, List[str]]:
        """
        Get model recommendations based on use case.
        
        Args:
            use_case: Use case ('general', 'fast', 'quality', 'minimal')
            
        Returns:
            Dict: Recommended models by type
        """
        recommendations = {
            'embedding': [],
            'llm': []
        }
        
        if use_case == 'fast':
            recommendations['embedding'] = ['all-MiniLM-L6-v2', 'paraphrase-MiniLM-L6-v2']
            recommendations['llm'] = ['qwen2.5:0.5b', 'qwen2.5:1.5b']
        elif use_case == 'quality':
            recommendations['embedding'] = ['all-mpnet-base-v2', 'paraphrase-mpnet-base-v2']
            recommendations['llm'] = ['llama3.2:3b', 'phi3.5:3.8b']
        elif use_case == 'minimal':
            recommendations['embedding'] = ['all-MiniLM-L6-v2']
            recommendations['llm'] = ['qwen2.5:0.5b']
        else:  # general
            recommendations['embedding'] = ['all-MiniLM-L6-v2', 'all-distilroberta-v1']
            recommendations['llm'] = ['llama3.2:1b', 'qwen2.5:1.5b']
        
        return recommendations
    
    def cleanup_unused_models(self, days_unused: int = 30) -> List[str]:
        """
        Clean up models that haven't been used recently.
        
        Args:
            days_unused: Number of days to consider a model unused
            
        Returns:
            List[str]: List of cleaned up model names
        """
        cutoff_date = datetime.now() - timedelta(days=days_unused)
        cleaned_models = []
        
        with self._lock:
            models_to_remove = []
            
            for model_key, metadata in self.models.items():
                if metadata.last_used and metadata.last_used < cutoff_date:
                    try:
                        if metadata.type == 'embedding' and metadata.local_path:
                            # Remove embedding model directory
                            model_path = Path(metadata.local_path)
                            if model_path.exists():
                                import shutil
                                shutil.rmtree(model_path)
                                logger.info(f"Removed unused embedding model: {metadata.name}")
                                cleaned_models.append(metadata.name)
                        
                        elif metadata.type == 'llm':
                            # Remove LLM model with Ollama
                            try:
                                subprocess.run(
                                    ['ollama', 'rm', metadata.name],
                                    capture_output=True,
                                    timeout=30
                                )
                                logger.info(f"Removed unused LLM model: {metadata.name}")
                                cleaned_models.append(metadata.name)
                            except Exception as e:
                                logger.warning(f"Failed to remove LLM model {metadata.name}: {e}")
                        
                        models_to_remove.append(model_key)
                        
                    except Exception as e:
                        logger.error(f"Failed to cleanup model {metadata.name}: {e}")
            
            # Remove from metadata
            for model_key in models_to_remove:
                del self.models[model_key]
            
            if models_to_remove:
                self._save_metadata()
        
        logger.info(f"Cleaned up {len(cleaned_models)} unused models")
        return cleaned_models
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """
        Get storage statistics for models.
        
        Returns:
            Dict: Storage statistics
        """
        stats = {
            'total_models': len(self.models),
            'embedding_models': len([m for m in self.models.values() if m.type == 'embedding']),
            'llm_models': len([m for m in self.models.values() if m.type == 'llm']),
            'total_size_bytes': 0,
            'total_size_mb': 0,
            'cache_dir': str(self.cache_dir),
            'models': []
        }
        
        for metadata in self.models.values():
            model_info = {
                'name': metadata.name,
                'type': metadata.type,
                'size_bytes': metadata.size_bytes or 0,
                'downloaded_at': metadata.downloaded_at.isoformat() if metadata.downloaded_at else None,
                'last_used': metadata.last_used.isoformat() if metadata.last_used else None
            }
            stats['models'].append(model_info)
            
            if metadata.size_bytes:
                stats['total_size_bytes'] += metadata.size_bytes
        
        stats['total_size_mb'] = stats['total_size_bytes'] / (1024 * 1024)
        
        return stats
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on model management system.
        
        Returns:
            Dict: Health check results
        """
        health = {
            'status': 'healthy',
            'issues': [],
            'model_count': len(self.models),
            'cache_dir_exists': self.cache_dir.exists(),
            'metadata_file_exists': self.metadata_file.exists(),
            'ollama_available': False
        }
        
        # Check Ollama availability
        try:
            result = subprocess.run(['ollama', '--version'], capture_output=True, timeout=5)
            health['ollama_available'] = result.returncode == 0
        except Exception:
            health['issues'].append("Ollama not available")
        
        # Check cache directory
        if not self.cache_dir.exists():
            health['issues'].append("Cache directory does not exist")
            health['status'] = 'degraded'
        
        # Validate a sample of models
        sample_models = list(self.models.values())[:3]  # Check first 3 models
        for metadata in sample_models:
            if not self.is_model_available(metadata.name, metadata.type):
                health['issues'].append(f"Model {metadata.name} not available")
                health['status'] = 'degraded'
        
        if len(health['issues']) > 3:
            health['status'] = 'unhealthy'
        
        return health


# Global model manager instance
_model_manager: Optional[ModelManager] = None


def get_model_manager(cache_dir: Optional[str] = None) -> ModelManager:
    """
    Get or create the global model manager instance.
    
    Args:
        cache_dir: Model cache directory (only used on first call)
        
    Returns:
        ModelManager: The model manager instance
    """
    global _model_manager
    
    if _model_manager is None:
        _model_manager = ModelManager(cache_dir or "./models")
    
    return _model_manager


def reset_model_manager() -> None:
    """Reset the global model manager (mainly for testing)."""
    global _model_manager
    _model_manager = None