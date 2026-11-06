"""Anomaly flag models for LedgerLine."""
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class FlagStatus(str, Enum):
    open = "open"
    confirmed = "confirmed"
    dismissed = "dismissed"


class FlagInDB(BaseModel):
    """Anomaly flag raised by deterministic rules or AI summary."""
    id: Optional[str] = Field(None, alias="_id")
    account_id: str
    txn_id: Optional[str] = None
    rule: str  # which rule triggered this flag
    severity: str = "medium"  # low, medium, high
    description: str = ""
    ai_summary: Optional[str] = None
    ai_model_version: Optional[str] = None
    ai_prompt: Optional[str] = None
    status: FlagStatus = FlagStatus.open
    decided_by: Optional[str] = None
    decision_reason: Optional[str] = None
    decided_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"populate_by_name": True}


class FlagDecisionRequest(BaseModel):
    status: FlagStatus  # confirmed or dismissed
    reason: str = Field(..., min_length=1)
