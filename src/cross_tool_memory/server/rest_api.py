"""
REST API server for cross-tool memory.

This module implements a FastAPI-based REST API that provides the same functionality
as the MCP server for tools that don't support the Model Context Protocol.
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field
import uvicorn

from ..config.database import DatabaseManager, DatabaseConfig
from ..security.access_control import (
    AccessControlMiddleware, APIKeyAuth, SecureHTTPBearer,
    create_api_key_auth, create_access_control_middleware
)
from ..security.rate_limiting import (
    RateLimitingMiddleware, RateLimiter,
    create_rate_limiter, create_rate_limiting_middleware
)
from ..security.tls_config import get_uvicorn_ssl_config
from ..services.encryption_service import get_encryption_service
from ..repositories.conversation_repository import ConversationRepository
from ..repositories.project_repository import ProjectRepository
from ..repositories.preferences_repository import PreferencesRepository
from ..services.context_manager import ContextManager
from ..services.search_engine import SearchEngine
from ..services.embedding_service import EmbeddingService
from ..services.vector_store import VectorStore
from ..models.schemas import (
    ConversationCreate, ConversationResponse, ConversationUpdate,
    ProjectCreate, ProjectResponse, ProjectUpdate,
    PreferenceCreate, PreferenceResponse, PreferenceUpdate,
    MemoryQuery, SearchResponse, SearchResult,
    HealthStatus, DatabaseStats
)

logger = logging.getLogger(__name__)

# Security (will be replaced by instance-specific security in __init__)
security = HTTPBearer(auto_error=False)

# Request/Response models specific to REST API
class StoreContextRequest(BaseModel):
    """Request model for storing context."""
    content: str = Field(..., min_length=1, description="The conversation content to store")
    tool_name: str = Field(..., description="Name of the AI tool")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Optional metadata")
    project_id: Optional[str] = Field(None, description="Optional project ID")


class StoreContextResponse(BaseModel):
    """Response model for storing context."""
    conversation_id: str
    stored_at: str
    project_detected: bool
    project_id: Optional[str]
    categories: Dict[str, Any]
    related_conversations: int
    context_links_created: int


class RetrieveContextRequest(BaseModel):
    """Request model for retrieving context."""
    query: str = Field(..., min_length=1, description="Search query")
    project_id: Optional[str] = Field(None, description="Optional project ID filter")
    tool_name: Optional[str] = Field(None, description="Optional tool name filter")
    limit: int = Field(10, ge=1, le=100, description="Maximum results")
    search_type: str = Field("hybrid", description="Search type: semantic, keyword, or hybrid")


class RetrieveContextResponse(BaseModel):
    """Response model for retrieving context."""
    query: str
    search_type: str
    filters: Dict[str, Any]
    total_results: int
    results: List[Dict[str, Any]]


class ProjectContextResponse(BaseModel):
    """Response model for project context."""
    project: Dict[str, Any]
    conversations: List[Dict[str, Any]]
    total_conversations: int
    statistics: Optional[Dict[str, Any]] = None


class ConversationHistoryRequest(BaseModel):
    """Request model for conversation history."""
    tool_name: str = Field(..., description="Tool name to get history for")
    hours: int = Field(24, ge=1, le=168, description="Hours to look back")
    limit: int = Field(20, ge=1, le=100, description="Maximum conversations")


class ConversationHistoryResponse(BaseModel):
    """Response model for conversation history."""
    tool_name: str
    time_range_hours: int
    total_conversations: int
    conversations: List[Dict[str, Any]]


class ErrorResponse(BaseModel):
    """Standard error response model."""
    error: str
    detail: Optional[str] = None
    timestamp: str


class MemoryRestAPI:
    """REST API server for cross-tool memory management."""
    
    def __init__(
        self, 
        db_path: str = "memory.db", 
        api_key: Optional[str] = None,
        encryption_passphrase: Optional[str] = None,
        enable_https: bool = False,
        cert_file: Optional[str] = None,
        key_file: Optional[str] = None,
        rate_limit_requests: int = 100,
        rate_limit_window: int = 60,
        allowed_origins: Optional[List[str]] = None,
        allowed_ips: Optional[List[str]] = None
    ):
        """
        Initialize the REST API server.
        
        Args:
            db_path: Path to the SQLite database file
            api_key: Optional API key for authentication
            encryption_passphrase: Passphrase for data encryption
            enable_https: Whether to enable HTTPS
            cert_file: Path to SSL certificate file
            key_file: Path to SSL private key file
            rate_limit_requests: Maximum requests per time window
            rate_limit_window: Rate limit time window in seconds
            allowed_origins: List of allowed CORS origins
            allowed_ips: List of allowed IP addresses
        """
        self.db_path = db_path
        self.api_key = api_key
        self.encryption_passphrase = encryption_passphrase
        self.enable_https = enable_https
        self.cert_file = cert_file
        self.key_file = key_file
        self.rate_limit_requests = rate_limit_requests
        self.rate_limit_window = rate_limit_window
        self.allowed_origins = allowed_origins
        self.allowed_ips = allowed_ips
        self.app = FastAPI(
            title="Cross-Tool Memory API",
            description="REST API for intelligent, persistent memory storage across AI development tools",
            version="0.1.0",
            docs_url="/docs",
            redoc_url="/redoc"
        )
        
        # Initialize components
        self.db_manager: Optional[DatabaseManager] = None
        self.conversation_repo: Optional[ConversationRepository] = None
        self.project_repo: Optional[ProjectRepository] = None
        self.preferences_repo: Optional[PreferencesRepository] = None
        self.context_manager: Optional[ContextManager] = None
        self.search_engine: Optional[SearchEngine] = None
        
        # Security components
        self.api_key_auth: Optional[APIKeyAuth] = None
        self.rate_limiter: Optional[RateLimiter] = None
        self.security: Optional[SecureHTTPBearer] = None
        
        # Setup security, middleware and routes
        self._setup_security()
        self._setup_middleware()
        self._setup_routes()
        self._setup_events()
    
    def _setup_security(self) -> None:
        """Setup security components."""
        # Initialize API key authentication
        api_keys = [self.api_key] if self.api_key else None
        self.api_key_auth = create_api_key_auth(api_keys=api_keys)
        
        # Initialize rate limiter
        self.rate_limiter = create_rate_limiter(
            max_requests=self.rate_limit_requests,
            time_window=self.rate_limit_window
        )
        
        # Initialize secure HTTP Bearer
        self.security = SecureHTTPBearer(self.api_key_auth, auto_error=False)
        
        logger.info("Security components initialized")
    
    def _setup_middleware(self) -> None:
        """Setup FastAPI middleware."""
        # Rate limiting middleware (first to prevent abuse)
        rate_limiting_middleware = create_rate_limiting_middleware(
            rate_limiter=self.rate_limiter
        )
        self.app.add_middleware(rate_limiting_middleware)
        
        # Access control middleware
        access_control_middleware = create_access_control_middleware(
            api_key_auth=self.api_key_auth,
            allowed_origins=self.allowed_origins,
            allowed_ips=self.allowed_ips,
            require_https=self.enable_https,
            security_headers=True
        )
        self.app.add_middleware(access_control_middleware)
        
        # CORS middleware
        cors_origins = self.allowed_origins or ["http://localhost:*", "http://127.0.0.1:*"]
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE"],
            allow_headers=["*"],
        )
        
        # Trusted host middleware for security
        allowed_hosts = ["localhost", "127.0.0.1", "*.localhost", "testserver"]
        if self.allowed_origins:
            # Extract hosts from allowed origins
            for origin in self.allowed_origins:
                host = origin.replace("http://", "").replace("https://", "").split(":")[0]
                allowed_hosts.append(host)
        
        self.app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=allowed_hosts
        )
        
        # Custom error handler
        @self.app.exception_handler(HTTPException)
        async def http_exception_handler(request: Request, exc: HTTPException):
            return JSONResponse(
                status_code=exc.status_code,
                content=ErrorResponse(
                    error=exc.detail or "HTTP Exception",
                    timestamp=datetime.utcnow().isoformat()
                ).model_dump()
            )
        
        @self.app.exception_handler(Exception)
        async def general_exception_handler(request: Request, exc: Exception):
            logger.error(f"Unhandled exception: {exc}")
            return JSONResponse(
                status_code=500,
                content=ErrorResponse(
                    error="Internal server error",
                    detail=str(exc) if os.getenv("DEBUG") else None,
                    timestamp=datetime.utcnow().isoformat()
                ).model_dump()
            )
    
    def _setup_routes(self) -> None:
        """Setup FastAPI routes."""
        logger.info("Setting up routes...")
        
        # Web interface will be added via router at root level
        
        logger.info("Landing page route added")
        
        # Add web interface routes
        from .web_interface import create_web_interface_router
        web_router = create_web_interface_router(self)
        self.app.include_router(web_router)
        
        # Add monitoring routes
        from .monitoring_api import create_monitoring_router
        monitoring_router = create_monitoring_router(self)
        self.app.include_router(monitoring_router)
        
        # Health check endpoint
        @self.app.get("/health", response_model=HealthStatus)
        async def health_check():
            """Health check endpoint."""
            return await self._health_check()
        
        @self.app.get("/stats", response_model=DatabaseStats)
        async def get_stats(credentials: Optional[HTTPAuthorizationCredentials] = Depends(self.security)):
            """Get database statistics."""
            self._ensure_initialized()
            return await self._get_database_stats()
        
        # Core memory endpoints
        @self.app.post("/context", response_model=StoreContextResponse)
        async def store_context(
            request: StoreContextRequest,
            credentials: Optional[HTTPAuthorizationCredentials] = Depends(self.security)
        ):
            """Store conversation context."""
            return await self._store_context(request)
        
        @self.app.post("/context/search", response_model=RetrieveContextResponse)
        async def retrieve_context(
            request: RetrieveContextRequest,
            credentials: Optional[HTTPAuthorizationCredentials] = Depends(self.security)
        ):
            """Search and retrieve relevant context."""
            return await self._retrieve_context(request)
        
        @self.app.get("/projects/{project_id}/context", response_model=ProjectContextResponse)
        async def get_project_context(
            project_id: str,
            limit: int = 50,
            include_stats: bool = True,
            credentials: Optional[HTTPAuthorizationCredentials] = Depends(self.security)
        ):
            """Get all context for a specific project."""
            return await self._get_project_context(project_id, limit, include_stats)
        
        @self.app.post("/history", response_model=ConversationHistoryResponse)
        async def get_conversation_history(
            request: ConversationHistoryRequest,
            credentials: Optional[HTTPAuthorizationCredentials] = Depends(self.security)
        ):
            """Get conversation history for a tool."""
            return await self._get_conversation_history(request)
        
        # CRUD endpoints for conversations
        @self.app.post("/conversations", response_model=ConversationResponse)
        async def create_conversation(
            conversation: ConversationCreate,
            credentials: Optional[HTTPAuthorizationCredentials] = Depends(self.security)
        ):
            """Create a new conversation."""
            return self.conversation_repo.create(conversation)
        
        @self.app.get("/conversations/{conversation_id}", response_model=ConversationResponse)
        async def get_conversation(
            conversation_id: str,
            credentials: Optional[HTTPAuthorizationCredentials] = Depends(self.security)
        ):
            """Get a conversation by ID."""
            self._ensure_initialized()
            conversation = self.conversation_repo.get_by_id(conversation_id)
            if not conversation:
                raise HTTPException(status_code=404, detail="Conversation not found")
            return conversation
        
        @self.app.put("/conversations/{conversation_id}", response_model=ConversationResponse)
        async def update_conversation(
            conversation_id: str,
            update_data: ConversationUpdate,
            credentials: Optional[HTTPAuthorizationCredentials] = Depends(self.security)
        ):
            """Update a conversation."""
            conversation = self.conversation_repo.update(conversation_id, update_data)
            if not conversation:
                raise HTTPException(status_code=404, detail="Conversation not found")
            return conversation
        
        @self.app.delete("/conversations/{conversation_id}")
        async def delete_conversation(
            conversation_id: str,
            credentials: Optional[HTTPAuthorizationCredentials] = Depends(self.security)
        ):
            """Delete a conversation."""
            success = self.conversation_repo.delete(conversation_id)
            if not success:
                raise HTTPException(status_code=404, detail="Conversation not found")
            return {"message": "Conversation deleted successfully"}
        
        # CRUD endpoints for projects
        @self.app.post("/projects", response_model=ProjectResponse)
        async def create_project(
            project: ProjectCreate,
            credentials: Optional[HTTPAuthorizationCredentials] = Depends(self.security)
        ):
            """Create a new project."""
            return self.project_repo.create(project)
        
        @self.app.get("/projects", response_model=List[ProjectResponse])
        async def list_projects(
            limit: int = 50,
            credentials: Optional[HTTPAuthorizationCredentials] = Depends(self.security)
        ):
            """List all projects."""
            return self.project_repo.get_all(limit=limit)
        
        @self.app.get("/projects/{project_id}", response_model=ProjectResponse)
        async def get_project(
            project_id: str,
            credentials: Optional[HTTPAuthorizationCredentials] = Depends(self.security)
        ):
            """Get a project by ID."""
            self._ensure_initialized()
            project = self.project_repo.get_by_id(project_id)
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            return project
        
        @self.app.put("/projects/{project_id}", response_model=ProjectResponse)
        async def update_project(
            project_id: str,
            update_data: ProjectUpdate,
            credentials: Optional[HTTPAuthorizationCredentials] = Depends(self.security)
        ):
            """Update a project."""
            project = self.project_repo.update(project_id, update_data)
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            return project
        
        @self.app.delete("/projects/{project_id}")
        async def delete_project(
            project_id: str,
            credentials: Optional[HTTPAuthorizationCredentials] = Depends(self.security)
        ):
            """Delete a project."""
            success = self.project_repo.delete(project_id)
            if not success:
                raise HTTPException(status_code=404, detail="Project not found")
            return {"message": "Project deleted successfully"}
        
        # Preferences endpoints
        @self.app.post("/preferences", response_model=PreferenceResponse)
        async def create_preference(
            preference: PreferenceCreate,
            credentials: Optional[HTTPAuthorizationCredentials] = Depends(self.security)
        ):
            """Create or update a preference."""
            existing = self.preferences_repo.get_by_key(preference.key)
            if existing:
                update_data = PreferenceUpdate(value=preference.value, category=preference.category)
                return self.preferences_repo.update(preference.key, update_data)
            else:
                return self.preferences_repo.create(preference)
        
        @self.app.get("/preferences", response_model=List[PreferenceResponse])
        async def list_preferences(
            category: Optional[str] = None,
            credentials: Optional[HTTPAuthorizationCredentials] = Depends(self.security)
        ):
            """List all preferences."""
            return self.preferences_repo.get_all(category=category)
        
        @self.app.get("/preferences/{key}", response_model=PreferenceResponse)
        async def get_preference(
            key: str,
            credentials: Optional[HTTPAuthorizationCredentials] = Depends(self.security)
        ):
            """Get a preference by key."""
            preference = self.preferences_repo.get_by_key(key)
            if not preference:
                raise HTTPException(status_code=404, detail="Preference not found")
            return preference
        
        @self.app.put("/preferences/{key}", response_model=PreferenceResponse)
        async def update_preference(
            key: str,
            update_data: PreferenceUpdate,
            credentials: Optional[HTTPAuthorizationCredentials] = Depends(self.security)
        ):
            """Update a preference."""
            preference = self.preferences_repo.update(key, update_data)
            if not preference:
                raise HTTPException(status_code=404, detail="Preference not found")
            return preference
        
        @self.app.delete("/preferences/{key}")
        async def delete_preference(
            key: str,
            credentials: Optional[HTTPAuthorizationCredentials] = Depends(self.security)
        ):
            """Delete a preference."""
            success = self.preferences_repo.delete(key)
            if not success:
                raise HTTPException(status_code=404, detail="Preference not found")
            return {"message": "Preference deleted successfully"}
    
    def _setup_events(self) -> None:
        """Setup FastAPI lifecycle events."""
        
        @self.app.on_event("startup")
        async def startup_event():
            """Initialize server components on startup."""
            if not self.db_manager:  # Only initialize if not already done
                await self.initialize()
            
            # Start rate limiter cleanup task
            if self.rate_limiter:
                await self.rate_limiter.start_cleanup_task()
        
        @self.app.on_event("shutdown")
        async def shutdown_event():
            """Clean up server resources on shutdown."""
            # Stop rate limiter cleanup task
            if self.rate_limiter:
                await self.rate_limiter.stop_cleanup_task()
            
            await self.cleanup()
    
    def _ensure_initialized(self) -> None:
        """Ensure server components are initialized."""
        if not self.db_manager:
            raise HTTPException(
                status_code=503,
                detail="Server not initialized. Please wait for startup to complete."
            )
    

    
    async def initialize(self) -> None:
        """Initialize the server components."""
        try:
            # Initialize encryption service
            if self.encryption_passphrase:
                encryption_service = get_encryption_service(self.encryption_passphrase)
                encryption_service.initialize()
                logger.info("Encryption service initialized")
            
            # Initialize database
            db_config = DatabaseConfig(database_path=self.db_path)
            self.db_manager = DatabaseManager(db_config)
            self.db_manager.initialize_database()
            
            # Initialize repositories
            self.conversation_repo = ConversationRepository(self.db_manager)
            self.project_repo = ProjectRepository(self.db_manager)
            self.preferences_repo = PreferencesRepository(self.db_manager)
            
            # Initialize services
            self.context_manager = ContextManager(
                self.db_manager,
                self.conversation_repo,
                self.project_repo
            )
            
            # Initialize search engine with embedding service
            try:
                embedding_service = EmbeddingService()
                await embedding_service.initialize()
                vector_store = VectorStore(dimension=384)  # all-MiniLM-L6-v2 dimension
                await vector_store.initialize()
                
                self.search_engine = SearchEngine(
                    embedding_service=embedding_service,
                    vector_store=vector_store
                )
                await self.search_engine.initialize()
                
                logger.info("Search engine initialized with embeddings")
            except Exception as e:
                logger.warning(f"Failed to initialize search engine with embeddings: {e}")
                # Fallback to keyword-only search
                vector_store = VectorStore(dimension=384)
                await vector_store.initialize()
                
                self.search_engine = SearchEngine(
                    embedding_service=None,
                    vector_store=vector_store
                )
                await self.search_engine.initialize()
                
                logger.info("Search engine initialized in keyword-only mode")
            
            logger.info("REST API Memory Server initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize REST API Memory Server: {e}")
            raise
    
    def run(
        self,
        host: str = "127.0.0.1",
        port: int = 8000,
        reload: bool = False,
        log_level: str = "info"
    ) -> None:
        """
        Run the REST API server.
        
        Args:
            host: Host to bind to
            port: Port to bind to
            reload: Enable auto-reload for development
            log_level: Logging level
        """
        # Prepare uvicorn configuration
        config = {
            "app": self.app,
            "host": host,
            "port": port,
            "reload": reload,
            "log_level": log_level,
            "access_log": True,
        }
        
        # Add SSL configuration if HTTPS is enabled
        if self.enable_https:
            try:
                ssl_config = get_uvicorn_ssl_config(
                    cert_file=self.cert_file,
                    key_file=self.key_file,
                    auto_generate=True
                )
                config.update(ssl_config)
                logger.info(f"Starting HTTPS server on https://{host}:{port}")
            except Exception as e:
                logger.error(f"Failed to configure HTTPS: {e}")
                logger.info(f"Falling back to HTTP on http://{host}:{port}")
        else:
            logger.info(f"Starting HTTP server on http://{host}:{port}")
        
        # Start the server
        uvicorn.run(**config)
    
    async def _health_check(self) -> HealthStatus:
        """Perform health check."""
        try:
            # Check database connection
            db_connected = self.db_manager is not None
            if db_connected:
                try:
                    # Simple query to test connection
                    self.conversation_repo.get_recent_by_tool("test", hours=1, limit=1)
                except Exception:
                    db_connected = False
            
            # Check vector store
            vector_ready = self.search_engine is not None
            
            # Check if model is loaded
            model_loaded = (
                self.search_engine is not None and 
                self.search_engine.embedding_service is not None
            )
            
            return HealthStatus(
                status="healthy" if db_connected and vector_ready else "degraded",
                timestamp=datetime.utcnow(),
                database_connected=db_connected,
                vector_store_ready=vector_ready,
                model_loaded=model_loaded,
                version="0.1.0"
            )
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return HealthStatus(
                status="unhealthy",
                timestamp=datetime.utcnow(),
                database_connected=False,
                vector_store_ready=False,
                model_loaded=False,
                version="0.1.0"
            )
    
    async def _get_database_stats(self) -> DatabaseStats:
        """Get database statistics."""
        try:
            total_conversations = self.conversation_repo.count_all()
            total_projects = self.project_repo.count_all()
            total_preferences = self.preferences_repo.count_all()
            
            # Get oldest and newest conversations
            oldest_conv = self.conversation_repo.get_oldest()
            newest_conv = self.conversation_repo.get_newest()
            
            # Calculate database size (approximate)
            import os
            db_size_mb = 0.0
            if os.path.exists(self.db_path):
                db_size_mb = os.path.getsize(self.db_path) / (1024 * 1024)
            
            return DatabaseStats(
                total_conversations=total_conversations,
                total_projects=total_projects,
                total_preferences=total_preferences,
                total_context_links=0,  # TODO: Implement context links count
                database_size_mb=round(db_size_mb, 2),
                oldest_conversation=oldest_conv.timestamp if oldest_conv else None,
                newest_conversation=newest_conv.timestamp if newest_conv else None
            )
        except Exception as e:
            logger.error(f"Error getting database stats: {e}")
            raise HTTPException(status_code=500, detail="Failed to get database statistics")
    
    async def _store_context(self, request: StoreContextRequest) -> StoreContextResponse:
        """Store conversation context."""
        try:
            # Extract tags from metadata
            tags = request.metadata.get("tags", []) if request.metadata else []
            
            # Create conversation
            conversation_data = ConversationCreate(
                tool_name=request.tool_name,
                content=request.content,
                conversation_metadata=request.metadata,
                project_id=request.project_id,
                tags=tags
            )
            
            conversation = self.conversation_repo.create(conversation_data)
            
            # Process context (project detection, categorization, linking)
            context_results = await self.context_manager.process_conversation_context(conversation)
            
            # Add to search index
            search_metadata = {
                "conversation_id": conversation.id,
                "tool_name": request.tool_name,
                "project_id": conversation.project_id,
                "timestamp": conversation.timestamp.isoformat(),
                "tags": tags
            }
            
            await self.search_engine.add_document(
                content=request.content,
                metadata=search_metadata,
                document_id=conversation.id
            )
            
            return StoreContextResponse(
                conversation_id=conversation.id,
                stored_at=conversation.timestamp.isoformat(),
                project_detected=context_results.get("project_detected", False),
                project_id=context_results.get("project_id"),
                categories=context_results.get("categories", {}),
                related_conversations=len(context_results.get("related_conversations", [])),
                context_links_created=context_results.get("context_links_created", 0)
            )
            
        except Exception as e:
            logger.error(f"Error storing context: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to store context: {str(e)}")
    
    async def _retrieve_context(self, request: RetrieveContextRequest) -> RetrieveContextResponse:
        """Search and retrieve relevant context."""
        try:
            # Build search filters
            filters = {}
            if request.project_id:
                filters["project_id"] = request.project_id
            if request.tool_name:
                filters["tool_name"] = request.tool_name.lower()
            
            # Perform search
            search_results = await self.search_engine.search(
                query=request.query,
                limit=request.limit,
                filters=filters if filters else None,
                search_type=request.search_type
            )
            
            # Format results
            formatted_results = []
            for result in search_results:
                conversation_id = result.metadata.get("conversation_id")
                conversation = self.conversation_repo.get_by_id(conversation_id) if conversation_id else None
                
                result_data = {
                    "conversation_id": conversation_id,
                    "content": result.content[:500] + "..." if len(result.content) > 500 else result.content,
                    "tool_name": result.metadata.get("tool_name"),
                    "project_id": result.metadata.get("project_id"),
                    "timestamp": result.metadata.get("timestamp"),
                    "tags": result.metadata.get("tags", []),
                    "relevance_score": round(result.combined_score, 3),
                    "scores": {
                        "semantic": round(result.semantic_score, 3),
                        "keyword": round(result.keyword_score, 3),
                        "recency": round(result.recency_score, 3)
                    }
                }
                
                if conversation and conversation.conversation_metadata:
                    result_data["metadata"] = conversation.conversation_metadata
                
                formatted_results.append(result_data)
            
            return RetrieveContextResponse(
                query=request.query,
                search_type=request.search_type,
                filters=filters,
                total_results=len(formatted_results),
                results=formatted_results
            )
            
        except Exception as e:
            logger.error(f"Error retrieving context: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to retrieve context: {str(e)}")
    
    async def _get_project_context(self, project_id: str, limit: int, include_stats: bool) -> ProjectContextResponse:
        """Get all context for a specific project."""
        try:
            # Get project information
            project = self.project_repo.get_by_id(project_id)
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            
            # Get project conversations
            conversations = self.conversation_repo.get_by_project(project_id, limit=limit)
            
            # Format conversations
            formatted_conversations = []
            for conv in conversations:
                conv_data = {
                    "conversation_id": conv.id,
                    "tool_name": conv.tool_name,
                    "timestamp": conv.timestamp.isoformat(),
                    "content": conv.content[:300] + "..." if len(conv.content) > 300 else conv.content,
                    "tags": conv.tags_list if conv.tags else []
                }
                
                if conv.conversation_metadata:
                    conv_data["metadata"] = conv.conversation_metadata
                
                formatted_conversations.append(conv_data)
            
            # Prepare project data
            project_data = {
                "id": project.id,
                "name": project.name,
                "description": project.description,
                "path": project.path,
                "technologies": project.technologies_list if project.technologies else [],
                "created_at": project.created_at.isoformat(),
                "last_accessed": project.last_accessed.isoformat()
            }
            
            response = ProjectContextResponse(
                project=project_data,
                conversations=formatted_conversations,
                total_conversations=len(formatted_conversations)
            )
            
            # Add statistics if requested
            if include_stats:
                total_conversations = self.conversation_repo.count_by_project(project_id)
                response.statistics = {
                    "total_conversations": total_conversations,
                    "conversations_returned": len(formatted_conversations),
                    "tools_used": list(set(conv["tool_name"] for conv in formatted_conversations))
                }
            
            return response
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting project context: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to get project context: {str(e)}")
    
    async def _get_conversation_history(self, request: ConversationHistoryRequest) -> ConversationHistoryResponse:
        """Get conversation history for a tool."""
        try:
            # Get recent conversations
            conversations = self.conversation_repo.get_recent_by_tool(
                tool_name=request.tool_name.lower(),
                hours=request.hours,
                limit=request.limit
            )
            
            # Format conversations
            formatted_conversations = []
            for conv in conversations:
                conv_data = {
                    "conversation_id": conv.id,
                    "timestamp": conv.timestamp.isoformat(),
                    "project_id": conv.project_id,
                    "content": conv.content[:200] + "..." if len(conv.content) > 200 else conv.content,
                    "tags": conv.tags_list if conv.tags else []
                }
                
                if conv.conversation_metadata:
                    conv_data["metadata"] = conv.conversation_metadata
                
                formatted_conversations.append(conv_data)
            
            return ConversationHistoryResponse(
                tool_name=request.tool_name,
                time_range_hours=request.hours,
                total_conversations=len(formatted_conversations),
                conversations=formatted_conversations
            )
            
        except Exception as e:
            logger.error(f"Error getting conversation history: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to get conversation history: {str(e)}")
    
    async def cleanup(self) -> None:
        """Clean up server resources."""
        try:
            if self.search_engine:
                await self.search_engine.cleanup()
            
            if self.db_manager:
                self.db_manager.close()
            
            logger.info("REST API Memory Server cleaned up")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


def create_app(db_path: str = "memory.db", api_key: Optional[str] = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    api_server = MemoryRestAPI(db_path=db_path, api_key=api_key)
    return api_server.app


async def run_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    db_path: str = "memory.db",
    api_key: Optional[str] = None,
    reload: bool = False
) -> None:
    """Run the REST API server."""
    api_server = MemoryRestAPI(db_path=db_path, api_key=api_key)
    
    try:
        await api_server.initialize()
        
        config = uvicorn.Config(
            app=api_server.app,
            host=host,
            port=port,
            reload=reload,
            log_level="info"
        )
        
        server = uvicorn.Server(config)
        await server.serve()
        
    except KeyboardInterrupt:
        logger.info("Server interrupted by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise
    finally:
        await api_server.cleanup()


if __name__ == "__main__":
    import asyncio
    
    # Get configuration from environment
    host = os.getenv("API_HOST", "127.0.0.1")
    port = int(os.getenv("API_PORT", "8000"))
    db_path = os.getenv("MEMORY_DB_PATH", "memory.db")
    api_key = os.getenv("API_KEY")
    
    asyncio.run(run_server(
        host=host,
        port=port,
        db_path=db_path,
        api_key=api_key
    ))
