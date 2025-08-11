"""
Pytest configuration and shared fixtures for comprehensive test suite.
"""

import pytest
import asyncio
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, AsyncMock


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def temp_directory():
    """Create a temporary directory for testing."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
async def temp_database():
    """Create a temporary database file."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_db:
        db_path = tmp_db.name
    yield db_path
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def mock_embedding_service():
    """Create a mock embedding service for testing."""
    mock = Mock()
    mock.initialize = AsyncMock()
    mock.cleanup = AsyncMock()
    mock.generate_embedding = AsyncMock()
    mock.generate_embeddings = AsyncMock()
    mock.embedding_dimension = 384
    mock.is_initialized = True
    return mock


@pytest.fixture
def performance_thresholds():
    """Define performance thresholds for testing."""
    return {
        "max_storage_time_per_doc": 0.01,  # 10ms per document
        "max_search_time": 0.2,            # 200ms for search
        "max_concurrent_operation_time": 5.0,  # 5s for concurrent ops
        "min_success_rate": 0.95,          # 95% success rate
        "max_memory_increase_mb": 100,     # 100MB memory increase
    }


# Pytest markers for different test categories
def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers", "performance: mark test as a performance test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "e2e: mark test as an end-to-end test"
    )
    config.addinivalue_line(
        "markers", "load: mark test as a load test"
    )
    config.addinivalue_line(
        "markers", "requirements: mark test as a requirements validation test"
    )


# Skip slow tests by default unless explicitly requested
def pytest_collection_modifyitems(config, items):
    """Modify test collection to handle slow tests."""
    if config.getoption("--run-slow"):
        return
    
    skip_slow = pytest.mark.skip(reason="need --run-slow option to run")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip_slow)


def pytest_addoption(parser):
    """Add custom command line options."""
    parser.addoption(
        "--run-slow", action="store_true", default=False, help="run slow tests"
    )
    parser.addoption(
        "--run-performance", action="store_true", default=False, help="run performance tests"
    )
    parser.addoption(
        "--run-load", action="store_true", default=False, help="run load tests"
    )