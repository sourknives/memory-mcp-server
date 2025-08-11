"""
Vector store implementation using FAISS for similarity search.
"""

import asyncio
import logging
import pickle
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import faiss
import numpy as np

logger = logging.getLogger(__name__)


class VectorStore:
    """FAISS-based vector store for similarity search."""
    
    def __init__(
        self,
        dimension: int,
        index_type: str = "flat",
        storage_path: Optional[str] = None
    ):
        """
        Initialize the vector store.
        
        Args:
            dimension: Dimension of the vectors
            index_type: Type of FAISS index ('flat', 'ivf', 'hnsw')
            storage_path: Path to store the index and metadata
        """
        self.dimension = dimension
        self.index_type = index_type
        self.storage_path = Path(storage_path) if storage_path else None
        
        self._index: Optional[faiss.Index] = None
        self._id_to_metadata: Dict[int, Dict] = {}
        self._next_id = 0
        self._is_trained = False
        
    async def initialize(self) -> None:
        """Initialize the vector store."""
        if self._index is not None:
            return
            
        # Create index based on type
        if self.index_type == "flat":
            self._index = faiss.IndexFlatIP(self.dimension)  # Inner product (cosine similarity)
        elif self.index_type == "ivf":
            # IVF index for larger datasets
            quantizer = faiss.IndexFlatIP(self.dimension)
            self._index = faiss.IndexIVFFlat(quantizer, self.dimension, 100)  # 100 clusters
        elif self.index_type == "hnsw":
            # HNSW index for fast approximate search
            self._index = faiss.IndexHNSWFlat(self.dimension, 32)  # 32 connections per node
        else:
            raise ValueError(f"Unsupported index type: {self.index_type}")
        
        # Load existing index if available
        if self.storage_path and self.storage_path.exists():
            await self.load()
        
        logger.info(f"Vector store initialized with {self.index_type} index, dimension {self.dimension}")
    
    async def add_vectors(
        self,
        vectors: Union[List[List[float]], np.ndarray],
        metadata: List[Dict],
        ids: Optional[List[str]] = None
    ) -> List[int]:
        """
        Add vectors to the store.
        
        Args:
            vectors: List of vectors or numpy array
            metadata: Metadata for each vector
            ids: Optional external IDs for the vectors
            
        Returns:
            List of internal IDs assigned to the vectors
        """
        if self._index is None:
            await self.initialize()
        
        # Convert to numpy array and normalize
        if isinstance(vectors, list):
            vectors = np.array(vectors, dtype=np.float32)
        else:
            vectors = vectors.astype(np.float32)
        
        # Normalize vectors for cosine similarity
        faiss.normalize_L2(vectors)
        
        # Train index if needed (for IVF)
        if self.index_type == "ivf" and not self._is_trained:
            if len(vectors) >= 100:  # Need enough vectors to train
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self._index.train, vectors)
                self._is_trained = True
            else:
                logger.warning("Not enough vectors to train IVF index, using flat index temporarily")
        
        # Add vectors to index
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._index.add, vectors)
        
        # Store metadata
        internal_ids = []
        for i, meta in enumerate(metadata):
            internal_id = self._next_id
            self._id_to_metadata[internal_id] = {
                **meta,
                "external_id": ids[i] if ids else None,
                "vector_index": self._index.ntotal - len(vectors) + i
            }
            internal_ids.append(internal_id)
            self._next_id += 1
        
        logger.debug(f"Added {len(vectors)} vectors to store")
        return internal_ids
    
    async def search(
        self,
        query_vector: Union[List[float], np.ndarray],
        k: int = 10,
        filters: Optional[Dict] = None
    ) -> List[Tuple[int, float, Dict]]:
        """
        Search for similar vectors.
        
        Args:
            query_vector: Query vector
            k: Number of results to return
            filters: Optional filters to apply to metadata
            
        Returns:
            List of tuples (internal_id, similarity_score, metadata)
        """
        if self._index is None:
            await self.initialize()
        
        if self._index.ntotal == 0:
            return []
        
        # Convert and normalize query vector
        if isinstance(query_vector, list):
            query_vector = np.array([query_vector], dtype=np.float32)
        else:
            query_vector = query_vector.reshape(1, -1).astype(np.float32)
        
        faiss.normalize_L2(query_vector)
        
        # Perform search
        search_k = min(k * 2, self._index.ntotal)  # Search more to account for filtering
        loop = asyncio.get_event_loop()
        similarities, indices = await loop.run_in_executor(
            None, self._index.search, query_vector, search_k
        )
        
        # Convert results and apply filters
        results = []
        for i, (similarity, vector_idx) in enumerate(zip(similarities[0], indices[0])):
            if vector_idx == -1:  # FAISS returns -1 for invalid results
                continue
                
            # Find internal ID by vector index
            internal_id = None
            metadata = None
            for iid, meta in self._id_to_metadata.items():
                if meta.get("vector_index") == vector_idx:
                    internal_id = iid
                    metadata = meta.copy()
                    break
            
            if internal_id is None or metadata is None:
                continue
            
            # Apply filters
            if filters and not self._matches_filters(metadata, filters):
                continue
            
            # Remove internal fields from metadata
            metadata.pop("vector_index", None)
            
            results.append((internal_id, float(similarity), metadata))
            
            if len(results) >= k:
                break
        
        return results
    
    def _matches_filters(self, metadata: Dict, filters: Dict) -> bool:
        """Check if metadata matches the given filters."""
        for key, value in filters.items():
            if key not in metadata:
                return False
            
            meta_value = metadata[key]
            
            # Handle different filter types
            if isinstance(value, list):
                # List means "any of these values"
                if meta_value not in value:
                    return False
            elif isinstance(value, dict):
                # Dict can contain operators like {"$gte": 10}
                if "$gte" in value and meta_value < value["$gte"]:
                    return False
                if "$lte" in value and meta_value > value["$lte"]:
                    return False
                if "$eq" in value and meta_value != value["$eq"]:
                    return False
            else:
                # Direct equality
                if meta_value != value:
                    return False
        
        return True
    
    async def remove_vectors(self, internal_ids: List[int]) -> None:
        """
        Remove vectors from the store.
        Note: FAISS doesn't support efficient removal, so this marks them as deleted.
        """
        for internal_id in internal_ids:
            if internal_id in self._id_to_metadata:
                self._id_to_metadata[internal_id]["deleted"] = True
        
        logger.debug(f"Marked {len(internal_ids)} vectors as deleted")
    
    async def get_metadata(self, internal_id: int) -> Optional[Dict]:
        """Get metadata for a vector by internal ID."""
        metadata = self._id_to_metadata.get(internal_id)
        if metadata and not metadata.get("deleted", False):
            result = metadata.copy()
            result.pop("vector_index", None)
            return result
        return None
    
    async def save(self) -> None:
        """Save the index and metadata to disk."""
        if not self.storage_path or self._index is None:
            return
        
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # Save FAISS index
        index_path = self.storage_path / "index.faiss"
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, faiss.write_index, self._index, str(index_path))
        
        # Save metadata
        metadata_path = self.storage_path / "metadata.pkl"
        metadata = {
            "id_to_metadata": self._id_to_metadata,
            "next_id": self._next_id,
            "is_trained": self._is_trained,
            "dimension": self.dimension,
            "index_type": self.index_type
        }
        
        with open(metadata_path, "wb") as f:
            pickle.dump(metadata, f)
        
        logger.info(f"Vector store saved to {self.storage_path}")
    
    async def load(self) -> None:
        """Load the index and metadata from disk."""
        if not self.storage_path or not self.storage_path.exists():
            return
        
        index_path = self.storage_path / "index.faiss"
        metadata_path = self.storage_path / "metadata.pkl"
        
        if not index_path.exists() or not metadata_path.exists():
            return
        
        # Load FAISS index
        loop = asyncio.get_event_loop()
        self._index = await loop.run_in_executor(None, faiss.read_index, str(index_path))
        
        # Load metadata
        with open(metadata_path, "rb") as f:
            metadata = pickle.load(f)
        
        self._id_to_metadata = metadata["id_to_metadata"]
        self._next_id = metadata["next_id"]
        self._is_trained = metadata["is_trained"]
        
        logger.info(f"Vector store loaded from {self.storage_path}")
    
    @property
    def size(self) -> int:
        """Get the number of vectors in the store."""
        if self._index is None:
            return 0
        return self._index.ntotal
    
    @property
    def active_size(self) -> int:
        """Get the number of non-deleted vectors in the store."""
        return sum(
            1 for meta in self._id_to_metadata.values()
            if not meta.get("deleted", False)
        )
    
    async def cleanup(self) -> None:
        """Clean up resources."""
        if self.storage_path:
            await self.save()
        
        self._index = None
        self._id_to_metadata.clear()
        self._next_id = 0
        self._is_trained = False