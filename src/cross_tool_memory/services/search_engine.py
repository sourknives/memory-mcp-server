"""
Search engine that combines semantic and keyword search capabilities with graceful degradation.
"""

import asyncio
import logging
import re
import time
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple, Union

from .vector_store import VectorStore
from ..utils.error_handling import (
    graceful_degradation, 
    retry_with_backoff, 
    RetryConfig,
    error_recovery_manager,
    ServiceDegradedError
)
from ..utils.logging_config import get_component_logger, get_performance_logger, TimedOperation

try:
    from .embedding_service import EmbeddingService
    EMBEDDING_SERVICE_AVAILABLE = True
except ImportError:
    EMBEDDING_SERVICE_AVAILABLE = False
    EmbeddingService = None

logger = get_component_logger("search_engine")
perf_logger = get_performance_logger()


class SearchResult:
    """Represents a search result with combined scoring."""
    
    def __init__(
        self,
        internal_id: int,
        content: str,
        metadata: Dict,
        semantic_score: float = 0.0,
        keyword_score: float = 0.0,
        recency_score: float = 0.0
    ):
        self.internal_id = internal_id
        self.content = content
        self.metadata = metadata
        self.semantic_score = semantic_score
        self.keyword_score = keyword_score
        self.recency_score = recency_score
        self._combined_score: Optional[float] = None
    
    @property
    def combined_score(self) -> float:
        """Calculate combined score if not already computed."""
        if self._combined_score is None:
            # Weighted combination of different scores
            self._combined_score = (
                0.6 * self.semantic_score +
                0.3 * self.keyword_score +
                0.1 * self.recency_score
            )
        return self._combined_score
    
    def to_dict(self) -> Dict:
        """Convert to dictionary representation."""
        return {
            "internal_id": self.internal_id,
            "content": self.content,
            "metadata": self.metadata,
            "scores": {
                "semantic": self.semantic_score,
                "keyword": self.keyword_score,
                "recency": self.recency_score,
                "combined": self.combined_score
            }
        }


class SearchEngine:
    """Search engine combining semantic and keyword search."""
    
    def __init__(
        self,
        embedding_service: Optional[EmbeddingService],
        vector_store: VectorStore,
        storage_path: Optional[str] = None
    ):
        """
        Initialize the search engine.
        
        Args:
            embedding_service: Service for generating embeddings (optional)
            vector_store: Vector store for similarity search
            storage_path: Path for storing search indices
        """
        if embedding_service is not None and not EMBEDDING_SERVICE_AVAILABLE:
            raise ImportError("EmbeddingService dependencies not available")
            
        self.embedding_service = embedding_service
        self.vector_store = vector_store
        self.storage_path = storage_path
        
        # In-memory keyword index for fast text search
        self._keyword_index: Dict[str, Set[int]] = {}
        self._content_store: Dict[int, str] = {}
        
    async def initialize(self) -> None:
        """Initialize the search engine."""
        if self.embedding_service is not None:
            await self.embedding_service.initialize()
        await self.vector_store.initialize()
        logger.info("Search engine initialized")
    
    async def add_document(
        self,
        content: str,
        metadata: Dict,
        document_id: Optional[str] = None
    ) -> int:
        """
        Add a document to the search index.
        
        Args:
            content: Document content
            metadata: Document metadata
            document_id: Optional external document ID
            
        Returns:
            Internal ID assigned to the document
        """
        # Generate embedding if service is available
        if self.embedding_service is not None:
            embedding = await self.embedding_service.generate_embedding(content)
            
            # Add to vector store
            internal_ids = await self.vector_store.add_vectors(
                [embedding],
                [metadata],
                [document_id] if document_id else None
            )
            internal_id = internal_ids[0]
        else:
            # For keyword-only mode, create a dummy embedding
            dummy_embedding = [0.0] * self.vector_store.dimension
            internal_ids = await self.vector_store.add_vectors(
                [dummy_embedding],
                [metadata],
                [document_id] if document_id else None
            )
            internal_id = internal_ids[0]
        
        # Add to keyword index
        self._add_to_keyword_index(internal_id, content)
        self._content_store[internal_id] = content
        
        logger.debug(f"Added document {internal_id} to search index")
        return internal_id
    
    async def add_documents(
        self,
        contents: List[str],
        metadata_list: List[Dict],
        document_ids: Optional[List[str]] = None
    ) -> List[int]:
        """
        Add multiple documents to the search index.
        
        Args:
            contents: List of document contents
            metadata_list: List of document metadata
            document_ids: Optional list of external document IDs
            
        Returns:
            List of internal IDs assigned to the documents
        """
        # Generate embeddings in batch if service is available
        if self.embedding_service is not None:
            embeddings = await self.embedding_service.generate_embeddings(contents)
        else:
            # For keyword-only mode, create dummy embeddings
            embeddings = [[0.0] * self.vector_store.dimension for _ in contents]
        
        # Add to vector store
        internal_ids = await self.vector_store.add_vectors(
            embeddings,
            metadata_list,
            document_ids
        )
        
        # Add to keyword index
        for internal_id, content in zip(internal_ids, contents):
            self._add_to_keyword_index(internal_id, content)
            self._content_store[internal_id] = content
        
        logger.debug(f"Added {len(contents)} documents to search index")
        return internal_ids
    
    def _add_to_keyword_index(self, internal_id: int, content: str) -> None:
        """Add document to keyword index."""
        # Extract keywords (simple tokenization)
        keywords = self._extract_keywords(content)
        
        for keyword in keywords:
            if keyword not in self._keyword_index:
                self._keyword_index[keyword] = set()
            self._keyword_index[keyword].add(internal_id)
    
    def _extract_keywords(self, text: str) -> Set[str]:
        """Extract keywords from text."""
        # Convert to lowercase and extract words
        text = text.lower()
        words = re.findall(r'\b\w+\b', text)
        
        # Filter out very short words and common stop words
        stop_words = {
            'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from',
            'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on', 'that', 'the',
            'to', 'was', 'will', 'with', 'i', 'you', 'we', 'they', 'this',
            'but', 'or', 'not', 'have', 'had', 'do', 'does', 'did', 'can',
            'could', 'should', 'would', 'may', 'might', 'must', 'shall',
            'about', 'all', 'also', 'any', 'been', 'her', 'him', 'his',
            'how', 'into', 'more', 'now', 'only', 'our', 'out', 'over',
            'said', 'she', 'some', 'than', 'them', 'very', 'what', 'when',
            'where', 'who', 'why', 'your'
        }
        
        keywords = {
            word for word in words
            if len(word) >= 3 and word not in stop_words
        }
        
        return keywords
    
    @graceful_degradation(service_name="search_engine")
    async def search(
        self,
        query: str,
        limit: int = 10,
        filters: Optional[Dict] = None,
        search_type: str = "hybrid"  # "semantic", "keyword", "hybrid"
    ) -> List[SearchResult]:
        """
        Search for documents with graceful degradation.
        
        Args:
            query: Search query
            limit: Maximum number of results
            filters: Optional metadata filters
            search_type: Type of search ("semantic", "keyword", "hybrid")
            
        Returns:
            List of search results sorted by relevance
        """
        start_time = time.time()
        
        try:
            if search_type == "semantic":
                results = await self._semantic_search_with_fallback(query, limit, filters)
            elif search_type == "keyword":
                results = await self._keyword_search(query, limit, filters)
            else:  # hybrid
                results = await self._hybrid_search_with_fallback(query, limit, filters)
            
            # Log performance
            duration = time.time() - start_time
            perf_logger.log_search_performance(
                query=query,
                result_count=len(results) if results else 0,
                duration=duration,
                search_type=search_type
            )
            
            return results or []
            
        except Exception as e:
            logger.error(f"Search operation failed: {e}")
            error_recovery_manager.record_error("search_engine", e)
            
            # Fallback to keyword search if available
            if search_type != "keyword":
                logger.warning("Falling back to keyword-only search")
                try:
                    return await self._keyword_search(query, limit, filters) or []
                except Exception as fallback_error:
                    logger.error(f"Keyword search fallback also failed: {fallback_error}")
            
            return []
    
    async def _semantic_search_with_fallback(
        self,
        query: str,
        limit: int,
        filters: Optional[Dict] = None
    ) -> List[SearchResult]:
        """Perform semantic search with fallback to keyword search."""
        try:
            return await self._semantic_search(query, limit, filters)
        except Exception as e:
            logger.warning(f"Semantic search failed, falling back to keyword search: {e}")
            return await self._keyword_search(query, limit, filters)

    @retry_with_backoff(
        config=RetryConfig(max_attempts=2, base_delay=0.5),
        service_name="semantic_search"
    )
    async def _semantic_search(
        self,
        query: str,
        limit: int,
        filters: Optional[Dict] = None
    ) -> List[SearchResult]:
        """Perform semantic search using embeddings."""
        if self.embedding_service is None:
            logger.warning("Semantic search requested but embedding service not available")
            raise ServiceDegradedError("Embedding service not available")
            
        with TimedOperation("semantic_search_embedding", logger):
            # Generate query embedding
            query_embedding = await self.embedding_service.generate_embedding(query)
        
        with TimedOperation("semantic_search_vector_search", logger):
            # Search vector store
            vector_results = await self.vector_store.search(
                query_embedding,
                k=limit * 2,  # Get more results to account for filtering
                filters=filters
            )
        
        # Convert to SearchResult objects
        results = []
        for internal_id, similarity, metadata in vector_results:
            content = self._content_store.get(internal_id, "")
            recency_score = self._calculate_recency_score(metadata)
            
            result = SearchResult(
                internal_id=internal_id,
                content=content,
                metadata=metadata,
                semantic_score=similarity,
                keyword_score=0.0,
                recency_score=recency_score
            )
            results.append(result)
        
        # Sort by combined score and limit
        results.sort(key=lambda x: x.combined_score, reverse=True)
        return results[:limit]
    
    async def _keyword_search(
        self,
        query: str,
        limit: int,
        filters: Optional[Dict] = None
    ) -> List[SearchResult]:
        """Perform keyword-based search."""
        query_keywords = self._extract_keywords(query)
        
        if not query_keywords:
            return []
        
        # Find documents containing query keywords
        candidate_docs: Dict[int, int] = {}  # internal_id -> keyword_count
        
        for keyword in query_keywords:
            if keyword in self._keyword_index:
                for internal_id in self._keyword_index[keyword]:
                    candidate_docs[internal_id] = candidate_docs.get(internal_id, 0) + 1
        
        # Score and filter results
        results = []
        for internal_id, keyword_count in candidate_docs.items():
            # Get metadata and apply filters
            metadata = await self.vector_store.get_metadata(internal_id)
            if metadata is None:
                continue
            
            if filters and not self._matches_filters(metadata, filters):
                continue
            
            content = self._content_store.get(internal_id, "")
            
            # Calculate keyword score (normalized by query length)
            keyword_score = keyword_count / len(query_keywords)
            recency_score = self._calculate_recency_score(metadata)
            
            result = SearchResult(
                internal_id=internal_id,
                content=content,
                metadata=metadata,
                semantic_score=0.0,
                keyword_score=keyword_score,
                recency_score=recency_score
            )
            results.append(result)
        
        # Sort by combined score and limit
        results.sort(key=lambda x: x.combined_score, reverse=True)
        return results[:limit]
    
    async def _hybrid_search_with_fallback(
        self,
        query: str,
        limit: int,
        filters: Optional[Dict] = None
    ) -> List[SearchResult]:
        """Perform hybrid search with graceful degradation."""
        try:
            return await self._hybrid_search(query, limit, filters)
        except Exception as e:
            logger.warning(f"Hybrid search failed, falling back to keyword search: {e}")
            return await self._keyword_search(query, limit, filters)

    async def _hybrid_search(
        self,
        query: str,
        limit: int,
        filters: Optional[Dict] = None
    ) -> List[SearchResult]:
        """Perform hybrid search combining semantic and keyword search."""
        # Run both searches in parallel with error handling
        semantic_task = asyncio.create_task(
            self._semantic_search_safe(query, limit * 2, filters)
        )
        keyword_task = asyncio.create_task(
            self._keyword_search(query, limit * 2, filters)
        )
        
        try:
            semantic_results, keyword_results = await asyncio.gather(
                semantic_task, keyword_task, return_exceptions=True
            )
            
            # Handle exceptions from parallel tasks
            if isinstance(semantic_results, Exception):
                logger.warning(f"Semantic search failed in hybrid mode: {semantic_results}")
                semantic_results = []
            
            if isinstance(keyword_results, Exception):
                logger.warning(f"Keyword search failed in hybrid mode: {keyword_results}")
                keyword_results = []
            
            # If both failed, raise an exception
            if not semantic_results and not keyword_results:
                raise ServiceDegradedError("Both semantic and keyword search failed")
            
        except Exception as e:
            logger.error(f"Hybrid search parallel execution failed: {e}")
            # Fallback to sequential execution
            semantic_results = await self._semantic_search_safe(query, limit * 2, filters)
            keyword_results = await self._keyword_search(query, limit * 2, filters)
        
        # Combine results
        combined_results: Dict[int, SearchResult] = {}
        
        # Add semantic results
        for result in semantic_results or []:
            combined_results[result.internal_id] = result
        
        # Merge keyword results
        for result in keyword_results or []:
            if result.internal_id in combined_results:
                # Update existing result with keyword score
                existing = combined_results[result.internal_id]
                existing.keyword_score = result.keyword_score
                existing._combined_score = None  # Reset to recalculate
            else:
                # Add new result
                combined_results[result.internal_id] = result
        
        # Sort by combined score and limit
        final_results = list(combined_results.values())
        final_results.sort(key=lambda x: x.combined_score, reverse=True)
        return final_results[:limit]
    
    async def _semantic_search_safe(
        self,
        query: str,
        limit: int,
        filters: Optional[Dict] = None
    ) -> List[SearchResult]:
        """Safe semantic search that returns empty list on failure."""
        try:
            return await self._semantic_search(query, limit, filters)
        except Exception as e:
            logger.debug(f"Semantic search failed safely: {e}")
            return []
    
    def _calculate_recency_score(self, metadata: Dict) -> float:
        """Calculate recency score based on timestamp."""
        timestamp_str = metadata.get("timestamp")
        if not timestamp_str:
            return 0.0
        
        try:
            # Parse timestamp (assuming ISO format)
            if isinstance(timestamp_str, str):
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            else:
                timestamp = timestamp_str
            
            # Calculate days since timestamp
            days_ago = (datetime.now(timestamp.tzinfo) - timestamp).days
            
            # Exponential decay: score decreases as content gets older
            # Recent content (0-7 days) gets high score, older content gets lower
            if days_ago <= 7:
                return 1.0
            elif days_ago <= 30:
                return 0.7
            elif days_ago <= 90:
                return 0.4
            else:
                return 0.1
        except (ValueError, TypeError):
            return 0.0
    
    def _matches_filters(self, metadata: Dict, filters: Dict) -> bool:
        """Check if metadata matches the given filters."""
        for key, value in filters.items():
            if key not in metadata:
                return False
            
            meta_value = metadata[key]
            
            if isinstance(value, list):
                if meta_value not in value:
                    return False
            elif isinstance(value, dict):
                if "$gte" in value and meta_value < value["$gte"]:
                    return False
                if "$lte" in value and meta_value > value["$lte"]:
                    return False
                if "$eq" in value and meta_value != value["$eq"]:
                    return False
            else:
                if meta_value != value:
                    return False
        
        return True
    
    async def remove_document(self, internal_id: int) -> None:
        """Remove a document from the search index."""
        # Remove from vector store
        await self.vector_store.remove_vectors([internal_id])
        
        # Remove from keyword index
        content = self._content_store.get(internal_id, "")
        if content:
            keywords = self._extract_keywords(content)
            for keyword in keywords:
                if keyword in self._keyword_index:
                    self._keyword_index[keyword].discard(internal_id)
                    if not self._keyword_index[keyword]:
                        del self._keyword_index[keyword]
        
        # Remove from content store
        self._content_store.pop(internal_id, None)
        
        logger.debug(f"Removed document {internal_id} from search index")
    
    async def get_document(self, internal_id: int) -> Optional[Dict]:
        """Get a document by internal ID."""
        metadata = await self.vector_store.get_metadata(internal_id)
        if metadata is None:
            return None
        
        content = self._content_store.get(internal_id, "")
        return {
            "internal_id": internal_id,
            "content": content,
            "metadata": metadata
        }
    
    @property
    def document_count(self) -> int:
        """Get the number of documents in the index."""
        return len(self._content_store)
    
    async def save(self) -> None:
        """Save the search index to disk."""
        await self.vector_store.save()
        logger.info("Search engine saved")
    
    async def cleanup(self) -> None:
        """Clean up resources."""
        await self.vector_store.cleanup()
        if self.embedding_service is not None:
            await self.embedding_service.cleanup()
        
        self._keyword_index.clear()
        self._content_store.clear()
        
        logger.info("Search engine cleaned up")