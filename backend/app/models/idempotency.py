"""Idempotency key models for LedgerLine."""
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class IdempotencyStatus(str, Enum):
    in_progress = "in_progress"
    completed = "completed"


class IdempotencyKeyInDB(BaseModel):
    """
    Idempotency key document.
    _id = actor_id + ":" + key (namespaced to prevent cross-user squatting).
    TTL index on expires_at fires only after status=completed.
    After expiry, a replay could double-pay: we mitigate by setting a 48h TTL
    and documenting the residual risk window.
    """
    id: str = Field(..., alias="_id")  # actor_id:key
    request_hash: str
    status: IdempotencyStatus = IdempotencyStatus.in_progress
    response_snapshot: Optional[dict[str, Any]] = None
    txn_id: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None  # set when completed

    model_config = {"populate_by_name": True}
