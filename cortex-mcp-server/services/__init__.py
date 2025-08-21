"""Core services for memory management, search, and learning."""

from .vector_store import VectorStore

__all__ = ["VectorStore"]

# Try to import optional dependencies
try:
    from .embedding_service import EmbeddingService
    __all__.append("EmbeddingService")
except ImportError:
    pass

try:
    from .search_engine import SearchEngine, SearchResult
    __all__.extend(["SearchEngine", "SearchResult"])
except ImportError:
    pass

# Context management and tagging services
try:
    from .context_manager import ContextManager
    from .tagging_service import TaggingService
    from .conversation_processor import ConversationProcessor
    __all__.extend(["ContextManager", "TaggingService", "ConversationProcessor"])
except ImportError:
    pass

# Learning engine
try:
    from .learning_engine import LearningEngine, PatternType, FeedbackType, DetectedPattern, UserFeedback
    __all__.extend(["LearningEngine", "PatternType", "FeedbackType", "DetectedPattern", "UserFeedback"])
except ImportError:
    pass

# Data export/import service
try:
    from .data_export_import import DataExportImportService
    __all__.append("DataExportImportService")
except ImportError:
    pass

# Storage analyzer service
try:
    from .storage_analyzer import StorageAnalyzer
    __all__.append("StorageAnalyzer")
except ImportError:
    pass