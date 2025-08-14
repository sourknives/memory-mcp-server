"""
Embedding service for generating semantic embeddings using sentence-transformers.
"""

import asyncio
import logging
from pathlib import Path
from typing import List, Optional, Union

try:
    import numpy as np
    import torch
    from sentence_transformers import SentenceTransformer
    DEPENDENCIES_AVAILABLE = True
except ImportError as e:
    DEPENDENCIES_AVAILABLE = False
    _MISSING_DEPS = str(e)
    # Create dummy types for type hints
    SentenceTransformer = None
    np = None
    torch = None

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating semantic embeddings using local sentence-transformers models."""
    
    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        cache_dir: Optional[str] = None,
        device: Optional[str] = None
    ):
        """
        Initialize the embedding service.
        
        Args:
            model_name: Name of the sentence-transformers model to use
            cache_dir: Directory to cache downloaded models
            device: Device to run the model on ('cpu', 'cuda', or None for auto)
        """
        if not DEPENDENCIES_AVAILABLE:
            raise ImportError(f"Required dependencies not available: {_MISSING_DEPS}")
            
        self.model_name = model_name
        self.cache_dir = cache_dir or str(Path.home() / ".cache" / "cortex_mcp" / "models")
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self._model: Optional[object] = None
        self._embedding_dim: Optional[int] = None
        
    async def initialize(self) -> None:
        """Initialize the embedding model asynchronously."""
        if self._model is not None:
            return
            
        logger.info(f"Loading embedding model: {self.model_name}")
        
        # Load model in a thread to avoid blocking
        loop = asyncio.get_event_loop()
        self._model = await loop.run_in_executor(
            None,
            self._load_model
        )
        
        # Get embedding dimension
        test_embedding = await self.generate_embedding("test")
        self._embedding_dim = len(test_embedding)
        
        logger.info(f"Embedding model loaded. Dimension: {self._embedding_dim}")
    
    def _load_model(self) -> object:
        """Load the sentence transformer model."""
        return SentenceTransformer(
            self.model_name,
            cache_folder=self.cache_dir,
            device=self.device
        )
    
    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to embed
            
        Returns:
            List of floats representing the embedding
        """
        if self._model is None:
            await self.initialize()
            
        if not text.strip():
            # Return zero vector for empty text
            return [0.0] * (self._embedding_dim or 384)
        
        # Generate embedding in a thread to avoid blocking
        loop = asyncio.get_event_loop()
        embedding = await loop.run_in_executor(
            None,
            self._generate_single_embedding,
            text
        )
        
        return embedding.tolist()
    
    def _generate_single_embedding(self, text: str) -> object:
        """Generate embedding for a single text (synchronous)."""
        return self._model.encode(text, convert_to_numpy=True)
    
    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embeddings, each as a list of floats
        """
        if self._model is None:
            await self.initialize()
            
        if not texts:
            return []
        
        # Filter out empty texts and keep track of indices
        non_empty_texts = []
        text_indices = []
        
        for i, text in enumerate(texts):
            if text.strip():
                non_empty_texts.append(text)
                text_indices.append(i)
        
        if not non_empty_texts:
            # Return zero vectors for all empty texts
            zero_embedding = [0.0] * (self._embedding_dim or 384)
            return [zero_embedding] * len(texts)
        
        # Generate embeddings in a thread to avoid blocking
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(
            None,
            self._generate_batch_embeddings,
            non_empty_texts
        )
        
        # Reconstruct full list with zero vectors for empty texts
        result = []
        zero_embedding = [0.0] * len(embeddings[0]) if embeddings else [0.0] * (self._embedding_dim or 384)
        embedding_idx = 0
        
        for i in range(len(texts)):
            if i in text_indices:
                result.append(embeddings[embedding_idx].tolist())
                embedding_idx += 1
            else:
                result.append(zero_embedding)
        
        return result
    
    def _generate_batch_embeddings(self, texts: List[str]) -> object:
        """Generate embeddings for multiple texts (synchronous)."""
        return self._model.encode(texts, convert_to_numpy=True)
    
    @property
    def embedding_dimension(self) -> int:
        """Get the dimension of embeddings produced by this model."""
        if self._embedding_dim is None:
            # Default dimension for all-MiniLM-L6-v2
            return 384
        return self._embedding_dim
    
    @property
    def is_initialized(self) -> bool:
        """Check if the model is initialized."""
        return self._model is not None
    
    async def cleanup(self) -> None:
        """Clean up resources."""
        if self._model is not None:
            # Move model cleanup to thread to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._cleanup_model)
            self._model = None
            self._embedding_dim = None
    
    def _cleanup_model(self) -> None:
        """Clean up the model (synchronous)."""
        if hasattr(self._model, 'cpu'):
            self._model.cpu()
        del self._model
        
        # Clear CUDA cache if using GPU
        if torch.cuda.is_available():
            torch.cuda.empty_cache()