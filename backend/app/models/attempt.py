"""Attempt log models for LedgerLine."""
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class AttemptOutcome(str, Enum):
    posted = "posted"
    refused = "refused"
    duplicate_replay = "duplicate_replay"
    in_flight_conflict = "in_flight_conflict"


class AttemptInDB(BaseModel):
    """
    Append-only log of every request that touched money, including refused ones.
    No update or delete code path exists for this collection.
    """
    id: Optional[str] = Field(None, alias="_id")
    idempotency_key: Optional[str] = None
    actor_id: str
    kind: str  # deposit, withdrawal, transfer, reversal, adjustment
    params: dict[str, Any] = Field(default_factory=dict)
    request_hash: str
    outcome: AttemptOutcome
    reason_code: Optional[str] = None
    txn_id: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"populate_by_name": True}


class AttemptResponse(BaseModel):
    id: str = Field(..., alias="_id")
    idempotency_key: Optional[str] = None
    actor_id: str
    kind: str
    params: dict[str, Any]
    outcome: AttemptOutcome
    reason_code: Optional[str] = None
    txn_id: Optional[str] = None
    created_at: datetime

    model_config = {"populate_by_name": True}
