# 🧠 Cortex MCP Server

A comprehensive Model Context Protocol (MCP) server providing intelligent, persistent memory storage with a modern web interface. Cortex MCP enables AI assistants to store, retrieve, and manage contextual information across conversations and projects.

## ✨ Features

- **🧠 Intelligent Memory Storage**: Store and retrieve contextual information with semantic search
- **🌐 Modern Web Interface**: Full-featured web UI for memory and project management
- **🔍 Advanced Search**: Semantic, keyword, and hybrid search capabilities
- **📁 Project Management**: Organize memories by projects with metadata
- **🔐 Security**: API key authentication and secure data handling
- **📊 Monitoring**: Real-time performance metrics and system health monitoring
- **🔧 API Testing**: Built-in API testing interface
- **🗄️ Database Management**: Comprehensive database maintenance tools

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- pip or conda

### Installation

1. **Clone and setup:**
   ```bash
   cd cortex-mcp-server
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements-build.txt
   ```

2. **Start the server:**
   ```bash
   python3 start_server.py
   ```

3. **Access the web interface:**
   Open your browser to [http://127.0.0.1:8000](http://127.0.0.1:8000)

### Docker Installation (Alternative)

```bash
docker-compose up -d
```

## 🌐 Web Interface

The Cortex MCP Server includes a comprehensive web interface with:

- **📊 Dashboard**: System overview with real-time metrics
- **🧠 Memory Management**: Create, edit, and organize memories
- **📁 Project Management**: Manage projects and associate memories
- **🔍 Advanced Search**: Powerful search with multiple algorithms
- **⚙️ Settings**: System configuration and preferences
- **📈 Monitoring**: Performance metrics and system health
- **🔧 API Testing**: Interactive API endpoint testing
- **🔑 API Key Management**: Secure key generation and management
- **🗄️ Database Tools**: Maintenance and data management

### Navigation

The interface features a modern sidebar navigation that's fully responsive:
- **Desktop**: Fixed left sidebar with all features
- **Mobile**: Collapsible hamburger menu
- **Accessibility**: Full keyboard navigation and screen reader support

## 🔧 Configuration

### Environment Variables

Create a `.env` file or set environment variables:

```bash
# Server Configuration
CORTEX_HOST=127.0.0.1
CORTEX_PORT=8000
CORTEX_ENV=development

# Database
DATABASE_PATH=memory.db

# Security (Optional)
API_KEY=your-secure-api-key-here
ENABLE_ENCRYPTION=true
```

### Configuration File

Alternatively, use `config.yml`:

```yaml
server:
  host: "127.0.0.1"
  port: 8000
  debug: true

database:
  path: "memory.db"
  backup_interval: 3600

security:
  api_keys:
    - "your-api-key-here"
  enable_encryption: true
  
logging:
  level: "INFO"
  file: "cortex.log"
```

## 🛠️ API Endpoints

### Core Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Web interface (main dashboard) |
| `GET` | `/health` | Server health check |
| `GET` | `/conversations` | List all memories |
| `POST` | `/conversations` | Create new memory |
| `GET` | `/conversations/{id}` | Get specific memory |
| `PUT` | `/conversations/{id}` | Update memory |
| `DELETE` | `/conversations/{id}` | Delete memory |

### Search Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/context/search` | Semantic search |
| `POST` | `/search/keyword` | Keyword search |
| `POST` | `/search/hybrid` | Hybrid search |

### Project Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/projects` | List projects |
| `POST` | `/projects` | Create project |
| `GET` | `/projects/{id}` | Get project details |
| `PUT` | `/projects/{id}` | Update project |
| `DELETE` | `/projects/{id}` | Delete project |

### API Key Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/keys` | List API keys |
| `POST` | `/api/keys` | Generate new key |
| `DELETE` | `/api/keys/{id}` | Revoke API key |

## 🔐 Security

### API Key Authentication

Generate secure API keys for production use:

```bash
# Using the web interface (recommended)
# Go to http://127.0.0.1:8000 → API Keys tab

# Or using command line
python3 start_server.py --api-key your-secure-key
```

### Usage with API Key

```bash
curl -H "Authorization: Bearer your-api-key" \
     -H "Content-Type: application/json" \
     http://127.0.0.1:8000/health
```

## 📊 Monitoring & Maintenance

### Health Monitoring

The server provides comprehensive health monitoring:

- **System Health**: CPU, memory, and disk usage
- **Database Status**: Connection status and integrity
- **Performance Metrics**: Response times and throughput
- **Error Tracking**: Real-time error monitoring

### Database Maintenance

Access database tools via the web interface or API:

- **Integrity Checks**: Verify database consistency
- **Optimization**: Optimize database performance
- **Backup/Restore**: Data backup and recovery
- **Cleanup**: Remove old or orphaned data

## 🧪 Development

### Setup Development Environment

```bash
# Install development dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Run tests
pytest tests/

# Format code
black .
isort .
flake8 .
```

### Project Structure

```
cortex-mcp-server/
├── server/           # Core server implementation
├── static/           # Web interface assets
├── scripts/          # Utility scripts
├── tests/            # Test suite
├── config/           # Configuration files
├── docs/             # Documentation
└── requirements-build.txt
```

## 🐳 Docker Deployment

### Development

```bash
docker-compose up -d
```

### Production

```bash
# Build production image
docker build -t cortex-mcp-server:latest .

# Run with environment variables
docker run -d \
  -p 8000:8000 \
  -e CORTEX_ENV=production \
  -e API_KEY=your-production-key \
  -v cortex-data:/app/data \
  cortex-mcp-server:latest
```

## 📚 Usage Examples

### Storing Memories

```python
import requests

# Store a memory
response = requests.post('http://127.0.0.1:8000/conversations', json={
    'tool_name': 'my_tool',
    'project': 'my_project',
    'content': 'Important information to remember',
    'tags': ['important', 'project'],
    'metadata': {'source': 'user_input'}
})
```

### Searching Memories

```python
# Semantic search
response = requests.post('http://127.0.0.1:8000/context/search', json={
    'query': 'find information about the project',
    'search_type': 'semantic',
    'limit': 10
})
```

### Project Management

```python
# Create a project
response = requests.post('http://127.0.0.1:8000/projects', json={
    'name': 'My Project',
    'description': 'Project description',
    'path': '/path/to/project'
})
```

## 🔧 Troubleshooting

### Common Issues

1. **Port already in use**:
   ```bash
   # Find and kill process using port 8000
   lsof -ti:8000 | xargs kill -9
   ```

2. **Database locked**:
   ```bash
   # Remove database lock files
   rm memory.db-shm memory.db-wal
   ```

3. **Permission errors**:
   ```bash
   # Ensure proper permissions
   chmod 755 start_server.py
   ```

### Logs

Check logs for debugging:
```bash
# View server logs
tail -f cortex.log

# Check system health
curl http://127.0.0.1:8000/health
```

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📞 Support

- **Documentation**: Check the `/docs` directory
- **Issues**: Report bugs via GitHub Issues
- **Web Interface**: Use the built-in help and documentation

---

**🎉 Ready to use!** Start the server with `python3 start_server.py` and visit [http://127.0.0.1:8000](http://127.0.0.1:8000) to get started.