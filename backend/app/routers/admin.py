"""
Admin router: user management (admin only).

All endpoints here require admin role.
"""
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.db import get_db
from app.deps import require_role
from app.models.user import UserResponse

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    user: Annotated[dict, Depends(require_role("admin"))],
):
    """List all users. Admin only."""
    db = get_db()
    users = await db.users.find({}).to_list(length=1000)
    return [
        UserResponse(
            _id=u["_id"],
            email=u["email"],
            role=u["role"],
            active=u["active"],
            created_at=u["created_at"],
        )
        for u in users
    ]


@router.patch("/users/{user_id}/deactivate")
async def deactivate_user(
    user_id: str,
    user: Annotated[dict, Depends(require_role("admin"))],
):
    """Deactivate a user. Admin only. Cannot deactivate yourself."""
    if user_id == user["_id"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "SELF_DEACTIVATION", "message": "Cannot deactivate yourself"},
        )

    db = get_db()
    result = await db.users.update_one(
        {"_id": user_id, "active": True},
        {"$set": {"active": False}},
    )

    if result.matched_count == 0:
        target = await db.users.find_one({"_id": user_id})
        if not target:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "NOT_FOUND", "message": "User not found"},
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "ALREADY_INACTIVE", "message": "User is already inactive"},
        )

    await db.audit_log.insert_one({
        "_id": str(uuid.uuid4()),
        "actor_id": user["_id"],
        "action": "deactivate_user",
        "target_type": "user",
        "target_id": user_id,
        "details": {},
        "created_at": datetime.now(timezone.utc),
    })

    return {"message": "User deactivated", "user_id": user_id}


@router.patch("/users/{user_id}/activate")
async def activate_user(
    user_id: str,
    user: Annotated[dict, Depends(require_role("admin"))],
):
    """Reactivate a user. Admin only."""
    db = get_db()
    result = await db.users.update_one(
        {"_id": user_id, "active": False},
        {"$set": {"active": True}},
    )

    if result.matched_count == 0:
        target = await db.users.find_one({"_id": user_id})
        if not target:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "NOT_FOUND", "message": "User not found"},
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "ALREADY_ACTIVE", "message": "User is already active"},
        )

    await db.audit_log.insert_one({
        "_id": str(uuid.uuid4()),
        "actor_id": user["_id"],
        "action": "activate_user",
        "target_type": "user",
        "target_id": user_id,
        "details": {},
        "created_at": datetime.now(timezone.utc),
    })

    return {"message": "User activated", "user_id": user_id}


@router.patch("/users/{user_id}/role")
async def change_role(
    user_id: str,
    role: str,
    user: Annotated[dict, Depends(require_role("admin"))],
):
    """Change a user's role. Admin only."""
    if role not in ("admin", "holder", "auditor"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "INVALID_ROLE", "message": "Role must be admin, holder, or auditor"},
        )

    db = get_db()
    target = await db.users.find_one({"_id": user_id})
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "User not found"},
        )

    old_role = target["role"]
    await db.users.update_one(
        {"_id": user_id},
        {"$set": {"role": role}},
    )

    await db.audit_log.insert_one({
        "_id": str(uuid.uuid4()),
        "actor_id": user["_id"],
        "action": "change_role",
        "target_type": "user",
        "target_id": user_id,
        "details": {"old_role": old_role, "new_role": role},
        "created_at": datetime.now(timezone.utc),
    })

    return {"message": "Role changed", "user_id": user_id, "old_role": old_role, "new_role": role}

