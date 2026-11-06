"""Audit log and flag models for LedgerLine."""
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field


class AuditLogEntry(BaseModel):
    """
    Append-only audit log for admin actions, role changes, freezes,
    approvals, AI suggestions and human decisions.
    """
    id: Optional[str] = Field(None, alias="_id")
    actor_id: str
    action: str  # e.g. "freeze_account", "unfreeze_account", "change_role", "approve_flag", "dismiss_flag", "set_overdraft_limit"
    target_type: str  # e.g. "account", "user", "flag", "transaction"
    target_id: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"populate_by_name": True}
