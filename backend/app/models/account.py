"""Account models for LedgerLine."""
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class AccountStatus(str, Enum):
    active = "active"
    frozen = "frozen"
    closed = "closed"


class AccountInDB(BaseModel):
    """Account document as stored in MongoDB."""
    id: Optional[str] = Field(None, alias="_id")
    number: str  # unique human-readable account number
    name: str
    owner_ids: list[str] = Field(default_factory=list)
    balance: int = 0  # paise, never float
    version: int = 0
    overdraft_limit: int = 0  # max negative balance in paise
    currency: str = "INR"
    status: AccountStatus = AccountStatus.active
    held: int = 0  # reserved funds for pending approvals
    latest_entry_hash: Optional[str] = None  # hash of the latest ledger entry for this account
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"populate_by_name": True}

    @field_validator("balance", "overdraft_limit", "held", mode="before")
    @classmethod
    def must_be_int(cls, v: object) -> int:
        if isinstance(v, bool) or not isinstance(v, int):
            raise ValueError(f"Money values must be integers (paise), got {type(v).__name__}")
        return v

    @field_validator("currency")
    @classmethod
    def only_inr(cls, v: str) -> str:
        if v != "INR":
            raise ValueError("Only INR is supported in v1")
        return v


class AccountCreate(BaseModel):
    """Request body for creating an account."""
    number: str = Field(..., min_length=1, max_length=30)
    name: str = Field(..., min_length=1, max_length=100)
    owner_ids: list[str] = Field(..., min_length=1)
    currency: str = "INR"
    overdraft_limit: int = 0

    @field_validator("currency")
    @classmethod
    def only_inr(cls, v: str) -> str:
        if v != "INR":
            raise ValueError("Only INR is supported in v1")
        return v

    @field_validator("overdraft_limit", mode="before")
    @classmethod
    def must_be_non_negative_int(cls, v: object) -> int:
        if isinstance(v, bool) or not isinstance(v, int):
            raise ValueError("overdraft_limit must be integer paise")
        if v < 0:
            raise ValueError("overdraft_limit must be >= 0")
        return v


class AccountResponse(BaseModel):
    id: str = Field(..., alias="_id")
    number: str
    name: str
    owner_ids: list[str]
    balance: int
    available: int = 0  # balance - held
    version: int
    overdraft_limit: int
    currency: str
    status: AccountStatus
    held: int
    created_at: datetime

    model_config = {"populate_by_name": True}


class DepositRequest(BaseModel):
    amount: int = Field(..., gt=0, description="Amount in paise, must be positive integer")
    memo: str = ""

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


class WithdrawRequest(BaseModel):
    amount: int = Field(..., gt=0, description="Amount in paise, must be positive integer")
    memo: str = ""

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


class TransferRequest(BaseModel):
    from_account_id: str
    to_account_id: str
    amount: int = Field(..., gt=0, description="Amount in paise, must be positive integer")
    memo: str = ""

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
