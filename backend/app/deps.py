"""FastAPI dependencies for auth and authorization."""
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt as pyjwt

from app.db import get_db
from app.security import decode_access_token

security_scheme = HTTPBearer()


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security_scheme)],
) -> dict:
    """Decode JWT and return the user dict from DB.
    
    We re-fetch the user from DB on every money-touching request to ensure
    the role hasn't been changed since the token was issued (defence against
    role escalation via stale JWT).
    """
    try:
        payload = decode_access_token(credentials.credentials)
    except pyjwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_TOKEN", "message": "Invalid or expired token"},
        )
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_TOKEN", "message": "Token missing subject"},
        )
    
    db = get_db()
    user = await db.users.find_one({"_id": user_id})
    if not user or not user.get("active", False):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "USER_INACTIVE", "message": "User not found or inactive"},
        )
    
    return user


def require_role(*allowed_roles: str):
    """Dependency factory: returns 403 if the user's role is not in allowed_roles."""
    async def _check(user: Annotated[dict, Depends(get_current_user)]) -> dict:
        if user["role"] not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "FORBIDDEN", "message": "Insufficient role"},
            )
        return user
    return _check


async def require_account_access(
    account_id: str,
    user: dict,
) -> dict:
    """Check that the user owns the account or is admin/auditor.
    
    Returns 404 (not 403) for non-owned accounts to avoid enumeration.
    This is documented in THREATS.md.
    """
    db = get_db()
    account = await db.accounts.find_one({"_id": account_id})
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Account not found"},
        )
    
    # Admin and auditor can access all accounts
    if user["role"] in ("admin", "auditor"):
        return account
    
    # Holder must be in owner_ids
    if user["_id"] not in account.get("owner_ids", []):
        # Return 404, not 403, to prevent account enumeration
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Account not found"},
        )
    
    return account


def get_idempotency_key(idempotency_key: Annotated[str, Header(alias="Idempotency-Key")]) -> str:
    """Extract the Idempotency-Key header; reject requests without it."""
    if not idempotency_key or not idempotency_key.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "MISSING_IDEMPOTENCY_KEY", "message": "Idempotency-Key header is required"},
        )
    return idempotency_key.strip()
