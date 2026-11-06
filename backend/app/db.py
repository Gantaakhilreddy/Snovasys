"""MongoDB connection and database handle using Motor (async driver)."""
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import get_settings

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


async def connect_db() -> None:
    """Open the Motor client. Called once at startup."""
    global _client, _db
    settings = get_settings()
    _client = AsyncIOMotorClient(
        settings.mongodb_uri,
        # Write concern majority ensures durability and is required for
        # multi-document transactions to be meaningful.
        w="majority",
        # Read concern majority ensures we only read committed data,
        # preventing dirty reads after a write in a transaction.
        readConcernLevel="majority",
    )
    _db = _client[settings.db_name]


async def close_db() -> None:
    """Close the Motor client. Called once at shutdown."""
    global _client, _db
    if _client:
        _client.close()
        _client = None
        _db = None


def get_db() -> AsyncIOMotorDatabase:
    """Return the database handle. Raises if not connected."""
    if _db is None:
        raise RuntimeError("Database not connected. Call connect_db() first.")
    return _db


def get_client() -> AsyncIOMotorClient:
    """Return the Motor client (needed for transactions)."""
    if _client is None:
        raise RuntimeError("Database not connected. Call connect_db() first.")
    return _client
