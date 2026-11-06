"""
Auth router: register (admin-only) and login (JWT).

Security decisions:
- Registration is admin-only. Holders and auditors cannot self-register.
- Login returns a short-lived JWT (default 30min) with sub (user_id) and role.
- Rate-limiting: after N failed attempts, the account is locked for M minutes.
- The JWT sub is the user's _id, never the email, so email changes don't
  invalidate references in ledger entries.
"""
from datetime import datetime, timedelta, timezone
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Annotated

from app.db import get_db
from app.deps import get_current_user, require_role
from app.config import get_settings
from app.security import hash_password, verify_password, create_access_token
from app.models.user import UserCreate, UserResponse, LoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(
    body: UserCreate,
    user: Annotated[dict, Depends(require_role("admin"))],
):
    """
    Create a new user. Admin-only.

    The admin specifies the role (holder or auditor). Admins can also
    create other admins. The password is hashed with bcrypt server-side.
    """
    db = get_db()

    # Check for duplicate email
    existing = await db.users.find_one({"email": body.email})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "EMAIL_EXISTS", "message": "A user with this email already exists"},
        )

    user_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    user_doc = {
        "_id": user_id,
        "email": body.email,
        "password_hash": hash_password(body.password),
        "role": body.role.value,
        "active": True,
        "failed_login_attempts": 0,
        "locked_until": None,
        "created_at": now,
    }

    await db.users.insert_one(user_doc)

    # Log to audit_log
    await db.audit_log.insert_one({
        "_id": str(uuid.uuid4()),
        "actor_id": user["_id"],
        "action": "create_user",
        "target_type": "user",
        "target_id": user_id,
        "details": {"email": body.email, "role": body.role.value},
        "created_at": now,
    })

    return UserResponse(
        _id=user_id,
        email=body.email,
        role=body.role,
        active=True,
        created_at=now,
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    """
    Authenticate and return a JWT.

    Rate-limiting: after max_attempts failed logins, the account is locked
    for lockout_minutes. The counter resets on successful login.

    Defence against NoSQL injection: body.email is validated by Pydantic
    EmailStr, which rejects objects like {"$gt": ""}. We query with the
    validated string, never a raw dict.
    """
    db = get_db()
    settings = get_settings()

    # Pydantic EmailStr already validated the email format, blocking
    # NoSQL operator injection like {"$gt": ""}.
    user = await db.users.find_one({"email": body.email})

    if not user:
        # Return generic error to prevent user enumeration
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_CREDENTIALS", "message": "Invalid email or password"},
        )

    if not user.get("active", False):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "ACCOUNT_INACTIVE", "message": "Account is inactive"},
        )

    # Check lockout
    locked_until = user.get("locked_until")
    now = datetime.now(timezone.utc)
    if locked_until and locked_until > now:
        remaining = int((locked_until - now).total_seconds())
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "ACCOUNT_LOCKED",
                "message": f"Account locked. Try again in {remaining} seconds.",
            },
        )

    # Verify password
    if not verify_password(body.password, user["password_hash"]):
        # Increment failed attempts
        attempts = user.get("failed_login_attempts", 0) + 1
        update: dict = {"$inc": {"failed_login_attempts": 1}}

        if attempts >= settings.login_max_attempts:
            lock_until = now + timedelta(minutes=settings.login_lockout_minutes)
            update["$set"] = {"locked_until": lock_until}

        await db.users.update_one({"_id": user["_id"]}, update)

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_CREDENTIALS", "message": "Invalid email or password"},
        )

    # Successful login: reset failed attempts
    await db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"failed_login_attempts": 0, "locked_until": None}},
    )

    token = create_access_token(subject=user["_id"], role=user["role"])

    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def get_me(user: Annotated[dict, Depends(get_current_user)]):
    """Return the currently authenticated user's profile."""
    return UserResponse(
        _id=user["_id"],
        email=user["email"],
        role=user["role"],
        active=user["active"],
        created_at=user["created_at"],
    )

