#!/usr/bin/env python3
"""
Demonstration of the semantic search engine functionality.

This script shows how to use the EmbeddingService, VectorStore, and SearchEngine
components together to create a working semantic search system.
"""

import asyncio
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

# Import our search components
from cross_tool_memory.services.vector_store import VectorStore
from cross_tool_memory.services.search_engine import SearchEngine

# Try to import embedding service, fall back to mock if not available
try:
    from cross_tool_memory.services.embedding_service import EmbeddingService
    EMBEDDING_AVAILABLE = True
except ImportError:
    EMBEDDING_AVAILABLE = False
    print("Note: sentence-transformers not available, using mock embeddings")


class MockEmbeddingService:
    """Mock embedding service for demonstration when ML dependencies aren't available."""
    
    def __init__(self):
        self.dimension = 4
        self._word_embeddings = {
            # Simple word-to-vector mappings for demo
            "python": [1.0, 0.0, 0.0, 0.0],
            "javascript": [0.0, 1.0, 0.0, 0.0],
            "machine": [0.0, 0.0, 1.0, 0.0],
            "learning": [0.0, 0.0, 0.8, 0.2],
            "programming": [0.8, 0.2, 0.0, 0.0],
            "web": [0.0, 0.8, 0.0, 0.2],
            "development": [0.2, 0.8, 0.0, 0.0],
            "data": [0.0, 0.0, 0.9, 0.1],
            "science": [0.0, 0.0, 0.7, 0.3],
        }
    
    async def initialize(self):
        print("Mock embedding service initialized")
    
    async def cleanup(self):
        pass
    
    def _text_to_embedding(self, text):
        """Convert text to embedding by averaging word embeddings."""
        words = text.lower().split()
        embeddings = []
        
        for word in words:
            if word in self._word_embeddings:
                embeddings.append(self._word_embeddings[word])
        
        if not embeddings:
            return [0.1, 0.1, 0.1, 0.1]  # Default embedding
        
        # Average the embeddings
        result = [0.0] * self.dimension
        for emb in embeddings:
            for i in range(self.dimension):
                result[i] += emb[i]
        
        # Normalize
        for i in range(self.dimension):
            result[i] /= len(embeddings)
        
        return result
    
    async def generate_embedding(self, text):
        return self._text_to_embedding(text)
    
    async def generate_embeddings(self, texts):
        return [self._text_to_embedding(text) for text in texts]
    
    @property
    def embedding_dimension(self):
        return self.dimension


async def main():
    """Demonstrate the semantic search engine."""
    print("🔍 Semantic Search Engine Demo")
    print("=" * 40)
    
    # Create temporary directory for storage
    temp_dir = tempfile.mkdtemp()
    print(f"Using temporary storage: {temp_dir}")
    
    try:
        # Initialize components
        # Use mock embedding service for demo (works without ML dependencies)
        print("Initializing mock embedding service...")
        embedding_service = MockEmbeddingService()
        
        vector_store = VectorStore(
            dimension=embedding_service.embedding_dimension,
            index_type="flat",
            storage_path=temp_dir
        )
        
        search_engine = SearchEngine(
            embedding_service=embedding_service,
            vector_store=vector_store,
            storage_path=temp_dir
        )
        
        await search_engine.initialize()
        print("✅ Search engine initialized")
        
        # Sample documents to index
        documents = [
            "Python is a powerful programming language for data science and machine learning",
            "JavaScript is essential for modern web development and frontend applications",
            "Machine learning algorithms can analyze large datasets to find patterns",
            "Web development with Python using Django framework for backend services",
            "Data science involves statistical analysis and machine learning techniques",
            "JavaScript frameworks like React make building user interfaces easier",
            "Python libraries like pandas and numpy are great for data manipulation",
            "Machine learning models require training data to make accurate predictions"
        ]
        
        metadata_list = [
            {"id": f"doc{i+1}", "topic": topic, "timestamp": datetime.now().isoformat()}
            for i, topic in enumerate([
                "python-data-science", "javascript-web", "machine-learning",
                "python-web", "data-science", "javascript-frameworks",
                "python-libraries", "machine-learning-models"
            ])
        ]
        
        print(f"\n📚 Adding {len(documents)} documents to the search index...")
        internal_ids = await search_engine.add_documents(documents, metadata_list)
        print(f"✅ Added documents with IDs: {internal_ids}")
        
        # Demonstrate different types of searches
        search_queries = [
            ("Python programming", "semantic"),
            ("machine learning", "keyword"),
            ("web development", "hybrid"),
            ("data analysis", "semantic")
        ]
        
        print("\n🔍 Performing searches...")
        print("-" * 40)
        
        for query, search_type in search_queries:
            print(f"\nQuery: '{query}' (type: {search_type})")
            results = await search_engine.search(
                query=query,
                limit=3,
                search_type=search_type
            )
            
            if results:
                for i, result in enumerate(results, 1):
                    print(f"  {i}. Score: {result.combined_score:.3f}")
                    print(f"     Content: {result.content[:60]}...")
                    print(f"     Semantic: {result.semantic_score:.3f}, "
                          f"Keyword: {result.keyword_score:.3f}, "
                          f"Recency: {result.recency_score:.3f}")
                    print(f"     Metadata: {result.metadata['topic']}")
            else:
                print("  No results found")
        
        # Demonstrate search with filters
        print(f"\n🎯 Filtered search for 'programming' in Python topics...")
        filtered_results = await search_engine.search(
            query="programming",
            limit=5,
            search_type="hybrid",
            filters={"topic": ["python-data-science", "python-web", "python-libraries"]}
        )
        
        print(f"Found {len(filtered_results)} filtered results:")
        for i, result in enumerate(filtered_results, 1):
            print(f"  {i}. {result.metadata['topic']}: {result.content[:50]}...")
        
        # Demonstrate document retrieval
        print(f"\n📄 Retrieving document by ID...")
        if internal_ids:
            doc = await search_engine.get_document(internal_ids[0])
            if doc:
                print(f"Document {doc['internal_id']}: {doc['content'][:60]}...")
                print(f"Metadata: {doc['metadata']}")
        
        # Show statistics
        print(f"\n📊 Search Engine Statistics:")
        print(f"  Total documents: {search_engine.document_count}")
        print(f"  Vector store size: {vector_store.size}")
        print(f"  Active vectors: {vector_store.active_size}")
        
        # Demonstrate saving and loading
        print(f"\n💾 Saving search index...")
        await search_engine.save()
        print("✅ Search index saved")
        
        print("\n🎉 Demo completed successfully!")
        
    except Exception as e:
        print(f"❌ Error during demo: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup
        try:
            await search_engine.cleanup()
        except:
            pass
        
        # Remove temporary directory
        shutil.rmtree(temp_dir, ignore_errors=True)
        print(f"🧹 Cleaned up temporary storage")


if __name__ == "__main__":
    asyncio.run(main())