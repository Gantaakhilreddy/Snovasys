"""Ledger entry models for LedgerLine."""
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class Direction(str, Enum):
    debit = "debit"
    credit = "credit"


class EntryKind(str, Enum):
    deposit = "deposit"
    withdrawal = "withdrawal"
    transfer = "transfer"
    reversal = "reversal"
    adjustment = "adjustment"


class LedgerEntryInDB(BaseModel):
    """Ledger entry document as stored in MongoDB. Append-only."""
    id: Optional[str] = Field(None, alias="_id")
    txn_id: str
    account_id: str
    direction: Direction
    amount: int = Field(..., gt=0)  # always positive; direction says debit/credit
    balance_after: int
    seq: int  # per-account monotonic sequence number
    prev_hash: Optional[str] = None  # hash of previous entry for this account
    hash: str  # sha256(prev_hash + canonical fields)
    kind: EntryKind
    counterparty_account_id: Optional[str] = None
    initiated_by: str  # user_id from JWT, never from request body
    idempotency_key: Optional[str] = None
    memo: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"populate_by_name": True}

    @field_validator("amount", mode="before")
    @classmethod
    def must_be_int(cls, v: object) -> int:
        if isinstance(v, bool):
            raise ValueError("Amount must be integer paise, not bool")
        if isinstance(v, float):
            raise ValueError("Amount must be integer paise, not float")
        if not isinstance(v, int):
            raise ValueError("Amount must be integer paise")
        return v


class LedgerEntryResponse(BaseModel):
    id: str = Field(..., alias="_id")
    txn_id: str
    account_id: str
    direction: Direction
    amount: int
    balance_after: int
    seq: int
    kind: EntryKind
    counterparty_account_id: Optional[str] = None
    initiated_by: str
    memo: str
    created_at: datetime

    model_config = {"populate_by_name": True}
