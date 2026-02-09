"""
Integration test fixtures for Risk Module.

Provides:
- Test database with clean state
- Auth fixtures that work with test users
- App fixtures for ASGI testing
"""

import os
import pytest
import sys
from pathlib import Path
from httpx import AsyncClient, ASGITransport

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

# Set AUTH_REQUIRED=false for testing (before importing app)
os.environ["AUTH_REQUIRED"] = "false"


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def app():
    """Create test app instance with auth disabled."""
    # Force reimport with AUTH_REQUIRED=false
    os.environ["AUTH_REQUIRED"] = "false"
    
    # Clear cached modules to pick up new env var
    for mod in list(sys.modules.keys()):
        if mod.startswith("api.") or mod.startswith("auth."):
            if mod in sys.modules:
                del sys.modules[mod]
    
    from api.main import app
    return app


@pytest.fixture
async def client(app):
    """Create async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
async def auth_client(client):
    """
    Create authenticated client.
    
    Since AUTH_REQUIRED=false, the endpoints fall back to get_optional_user
    which returns None (anonymous user). This is sufficient for testing
    the risk settings CRUD operations.
    """
    return client


@pytest.fixture
async def auth_headers():
    """
    Return empty auth headers for testing.
    
    With AUTH_REQUIRED=false, endpoints accept requests without auth
    and treat them as anonymous user requests.
    """
    return {}


@pytest.fixture
async def test_user_id():
    """Return test user ID for database operations."""
    return "test-user-risk-001"


# Clean up after tests
@pytest.fixture(autouse=True)
async def cleanup():
    """Clean up test data after each test."""
    yield
    # Cleanup happens automatically with test database
