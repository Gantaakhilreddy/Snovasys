"""
Shared test fixtures.

Tests run against a real MongoDB replica set (Atlas or local).
A mock cannot test transactions. Each test gets fresh accounts
via the provided fixtures.
"""
import asyncio
import os
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

# Set test environment before importing app
os.environ.setdefault("DB_NAME", "ledgerline_test")
os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-production")

from app.main import app
from app.db import connect_db, close_db, get_db, get_client
from app.config import get_settings


@pytest.fixture(scope="session")
def event_loop():
    """Create a session-scoped event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def setup_database():
    """Connect to the test database once per session."""
    await connect_db()
    yield
    # Clean up test database
    db = get_db()
    collections = await db.list_collection_names()
    for coll in collections:
        await db[coll].drop()
    await close_db()


@pytest_asyncio.fixture
async def client(setup_database) -> AsyncClient:
    """Async HTTP client for testing FastAPI endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def db(setup_database):
    """Direct database access for test setup/assertions."""
    return get_db()
