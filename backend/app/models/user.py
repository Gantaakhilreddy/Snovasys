"""User models for LedgerLine."""
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserRole(str, Enum):
    admin = "admin"
    holder = "holder"
    auditor = "auditor"


class UserInDB(BaseModel):
    """User document as stored in MongoDB."""
    id: Optional[str] = Field(None, alias="_id")
    email: EmailStr
    password_hash: str
    role: UserRole
    active: bool = True
    failed_login_attempts: int = 0
    locked_until: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"populate_by_name": True}


class UserCreate(BaseModel):
    """Request body for creating a user (admin-only)."""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    role: UserRole


class UserResponse(BaseModel):
    """Public user response (never expose password_hash)."""
    id: str = Field(..., alias="_id")
    email: EmailStr
    role: UserRole
    active: bool
    created_at: datetime

    model_config = {"populate_by_name": True}


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
