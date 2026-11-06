"""Test the health endpoint."""
import os
import pytest
from httpx import AsyncClient, ASGITransport

# The health endpoint test requires MongoDB to be reachable (FastAPI lifespan
# connects to MongoDB on startup). Skip if MONGODB_URI is not configured.
pytestmark = pytest.mark.skipif(
    not os.environ.get("MONGODB_URI"),
    reason="MONGODB_URI not set; skipping integration tests"
)


@pytest.mark.asyncio
async def test_health():
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "ledgerline"
        assert "x-request-id" in resp.headers
