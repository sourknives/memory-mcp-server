# Cross-Tool Memory REST API Documentation

The Cross-Tool Memory server provides a comprehensive REST API for tools that don't support the Model Context Protocol (MCP). This API mirrors all MCP functionality and provides additional CRUD operations for direct data management.

## Base URL

When running locally:
```
http://127.0.0.1:8000
```

## Authentication

The API supports optional Bearer token authentication. If an API key is configured, include it in the Authorization header:

```bash
curl -H "Authorization: Bearer your-api-key" http://localhost:8000/endpoint
```

## Content Type

All POST/PUT requests should use `application/json` content type:

```bash
curl -H "Content-Type: application/json" -d '{"key": "value"}' http://localhost:8000/endpoint
```

## Core Memory Operations

### Store Context

Store conversation context for future retrieval.

**Endpoint:** `POST /context`

**Request Body:**
```json
{
  "content": "The conversation content to store",
  "tool_name": "cursor",
  "metadata": {
    "user_query": "How do I implement authentication?",
    "ai_response": "You can use FastAPI's HTTPBearer...",
    "file_path": "/path/to/file.py",
    "project_name": "my-project",
    "code_snippets": ["def authenticate(token):"],
    "tags": ["authentication", "fastapi"]
  },
  "project_id": "optional-project-id"
}
```

**Response:**
```json
{
  "conversation_id": "conv-123",
  "stored_at": "2024-01-15T10:30:00Z",
  "project_detected": true,
  "project_id": "proj-456",
  "categories": {"type": "development", "topic": "authentication"},
  "related_conversations": 3,
  "context_links_created": 2
}
```

### Search Context

Search and retrieve relevant context based on a query.

**Endpoint:** `POST /context/search`

**Request Body:**
```json
{
  "query": "FastAPI authentication implementation",
  "project_id": "proj-456",
  "tool_name": "cursor",
  "limit": 10,
  "search_type": "hybrid"
}
```

**Parameters:**
- `query` (required): Search query string
- `project_id` (optional): Filter by project ID
- `tool_name` (optional): Filter by tool name
- `limit` (optional): Maximum results (1-100, default: 10)
- `search_type` (optional): "semantic", "keyword", or "hybrid" (default: "hybrid")

**Response:**
```json
{
  "query": "FastAPI authentication implementation",
  "search_type": "hybrid",
  "filters": {"project_id": "proj-456", "tool_name": "cursor"},
  "total_results": 5,
  "results": [
    {
      "conversation_id": "conv-123",
      "content": "To implement FastAPI authentication...",
      "tool_name": "cursor",
      "project_id": "proj-456",
      "timestamp": "2024-01-15T10:30:00Z",
      "tags": ["authentication", "fastapi"],
      "relevance_score": 0.95,
      "scores": {
        "semantic": 0.92,
        "keyword": 0.98,
        "recency": 0.85
      },
      "metadata": {
        "user_query": "How do I implement authentication?",
        "file_path": "/path/to/file.py"
      }
    }
  ]
}
```

### Get Project Context

Get all context and conversations for a specific project.

**Endpoint:** `GET /projects/{project_id}/context`

**Query Parameters:**
- `limit` (optional): Maximum conversations to return (default: 50)
- `include_stats` (optional): Include project statistics (default: true)

**Response:**
```json
{
  "project": {
    "id": "proj-456",
    "name": "My Web App",
    "description": "A FastAPI web application",
    "path": "/path/to/project",
    "technologies": ["python", "fastapi", "postgresql"],
    "created_at": "2024-01-01T00:00:00Z",
    "last_accessed": "2024-01-15T10:30:00Z"
  },
  "conversations": [
    {
      "conversation_id": "conv-123",
      "tool_name": "cursor",
      "timestamp": "2024-01-15T10:30:00Z",
      "content": "Implementing authentication...",
      "tags": ["authentication", "fastapi"],
      "metadata": {"file_path": "/auth.py"}
    }
  ],
  "total_conversations": 25,
  "statistics": {
    "total_conversations": 25,
    "conversations_returned": 25,
    "tools_used": ["cursor", "claude", "kiro"]
  }
}
```

### Get Conversation History

Get conversation history for a specific tool within a timeframe.

**Endpoint:** `POST /history`

**Request Body:**
```json
{
  "tool_name": "cursor",
  "hours": 24,
  "limit": 20
}
```

**Response:**
```json
{
  "tool_name": "cursor",
  "time_range_hours": 24,
  "total_conversations": 15,
  "conversations": [
    {
      "conversation_id": "conv-123",
      "timestamp": "2024-01-15T10:30:00Z",
      "project_id": "proj-456",
      "content": "Recent conversation content...",
      "tags": ["recent", "development"],
      "metadata": {"file_path": "/recent.py"}
    }
  ]
}
```

## CRUD Operations

### Conversations

#### Create Conversation
**Endpoint:** `POST /conversations`

**Request Body:**
```json
{
  "tool_name": "cursor",
  "content": "Conversation content",
  "conversation_metadata": {"key": "value"},
  "tags": ["tag1", "tag2"],
  "project_id": "proj-456"
}
```

#### Get Conversation
**Endpoint:** `GET /conversations/{conversation_id}`

#### Update Conversation
**Endpoint:** `PUT /conversations/{conversation_id}`

**Request Body:**
```json
{
  "content": "Updated content",
  "tags": ["updated", "tag"]
}
```

#### Delete Conversation
**Endpoint:** `DELETE /conversations/{conversation_id}`

### Projects

#### Create Project
**Endpoint:** `POST /projects`

**Request Body:**
```json
{
  "name": "My Project",
  "description": "Project description",
  "path": "/path/to/project"
}
```

#### List Projects
**Endpoint:** `GET /projects`

**Query Parameters:**
- `limit` (optional): Maximum projects to return (default: 50)

#### Get Project
**Endpoint:** `GET /projects/{project_id}`

#### Update Project
**Endpoint:** `PUT /projects/{project_id}`

#### Delete Project
**Endpoint:** `DELETE /projects/{project_id}`

### Preferences

#### Create/Update Preference
**Endpoint:** `POST /preferences`

**Request Body:**
```json
{
  "key": "preferred_search_type",
  "value": "hybrid",
  "category": "search"
}
```

#### List Preferences
**Endpoint:** `GET /preferences`

**Query Parameters:**
- `category` (optional): Filter by category

#### Get Preference
**Endpoint:** `GET /preferences/{key}`

#### Update Preference
**Endpoint:** `PUT /preferences/{key}`

#### Delete Preference
**Endpoint:** `DELETE /preferences/{key}`

## System Endpoints

### Health Check

Check server health and status.

**Endpoint:** `GET /health`

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "database_connected": true,
  "vector_store_ready": true,
  "model_loaded": true,
  "version": "0.1.0"
}
```

### Database Statistics

Get database statistics and metrics.

**Endpoint:** `GET /stats`

**Response:**
```json
{
  "total_conversations": 1250,
  "total_projects": 15,
  "total_preferences": 8,
  "total_context_links": 450,
  "database_size_mb": 12.5,
  "oldest_conversation": "2024-01-01T00:00:00Z",
  "newest_conversation": "2024-01-15T10:30:00Z"
}
```

### API Documentation

Interactive API documentation is available at:
- **Swagger UI:** `GET /docs`
- **ReDoc:** `GET /redoc`
- **OpenAPI Schema:** `GET /openapi.json`

## Error Responses

All errors follow a consistent format:

```json
{
  "error": "Error message",
  "detail": "Additional error details (optional)",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Common HTTP Status Codes

- `200` - Success
- `400` - Bad Request (invalid input)
- `401` - Unauthorized (invalid/missing API key)
- `404` - Not Found (resource doesn't exist)
- `422` - Validation Error (invalid request format)
- `500` - Internal Server Error
- `503` - Service Unavailable (server not initialized)

## Rate Limiting

Currently, no rate limiting is implemented, but it may be added in future versions for production deployments.

## CORS

The API includes CORS middleware configured to allow requests from:
- `http://localhost:*`
- `http://127.0.0.1:*`

## Example Usage

### Python with httpx

```python
import httpx
import asyncio

async def example():
    async with httpx.AsyncClient() as client:
        # Store context
        response = await client.post("http://localhost:8000/context", json={
            "content": "I'm implementing user authentication",
            "tool_name": "cursor",
            "metadata": {"tags": ["auth", "security"]}
        })
        print(f"Stored: {response.json()}")
        
        # Search for context
        response = await client.post("http://localhost:8000/context/search", json={
            "query": "authentication implementation",
            "limit": 5
        })
        print(f"Found: {response.json()}")

asyncio.run(example())
```

### JavaScript with fetch

```javascript
// Store context
const storeResponse = await fetch('http://localhost:8000/context', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer your-api-key' // if using authentication
  },
  body: JSON.stringify({
    content: 'I need help with React state management',
    tool_name: 'cursor',
    metadata: {
      tags: ['react', 'state'],
      file_path: '/src/components/App.js'
    }
  })
});

const storeResult = await storeResponse.json();
console.log('Stored:', storeResult);

// Search for context
const searchResponse = await fetch('http://localhost:8000/context/search', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer your-api-key'
  },
  body: JSON.stringify({
    query: 'React state management',
    limit: 10,
    search_type: 'hybrid'
  })
});

const searchResult = await searchResponse.json();
console.log('Found:', searchResult);
```

### cURL Examples

```bash
# Store context
curl -X POST http://localhost:8000/context \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{
    "content": "How to implement JWT authentication in FastAPI",
    "tool_name": "claude",
    "metadata": {
      "tags": ["jwt", "fastapi", "auth"],
      "project_name": "api-server"
    }
  }'

# Search context
curl -X POST http://localhost:8000/context/search \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{
    "query": "JWT FastAPI authentication",
    "limit": 5,
    "search_type": "hybrid"
  }'

# Health check
curl http://localhost:8000/health

# Get database stats
curl -H "Authorization: Bearer your-api-key" \
  http://localhost:8000/stats
```

## Integration Examples

See the `examples/rest_api_client.py` file for a complete Python client implementation that demonstrates all API endpoints.