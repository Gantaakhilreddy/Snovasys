"""
Accounts router: CRUD + freeze/unfreeze.

Authorization:
- Create account: admin only
- List accounts: admin/auditor see all; holder sees own only
- Get account: admin/auditor see any; holder sees own (404 for others)
- Freeze/unfreeze: admin only
- Assign owners: admin only

Object-level auth: non-owned accounts return 404 (not 403) to prevent
enumeration. This is documented in THREATS.md (T5).
"""
import uuid
from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.db import get_db
from app.deps import get_current_user, require_role, require_account_access
from app.models.account import AccountCreate, AccountResponse, AccountStatus

router = APIRouter(prefix="/accounts", tags=["accounts"])


def _account_to_response(acct: dict) -> AccountResponse:
    """Convert a MongoDB account document to an AccountResponse."""
    return AccountResponse(
        _id=acct["_id"],
        number=acct["number"],
        name=acct["name"],
        owner_ids=acct.get("owner_ids", []),
        balance=acct["balance"],
        available=acct["balance"] - acct.get("held", 0),
        version=acct["version"],
        overdraft_limit=acct.get("overdraft_limit", 0),
        currency=acct["currency"],
        status=acct["status"],
        held=acct.get("held", 0),
        created_at=acct["created_at"],
    )


@router.post("", response_model=AccountResponse, status_code=201)
async def create_account(
    body: AccountCreate,
    user: Annotated[dict, Depends(require_role("admin"))],
):
    """Create a new account. Admin only."""
    db = get_db()

    # Validate that all owner_ids exist and are active holders
    for owner_id in body.owner_ids:
        owner = await db.users.find_one({"_id": owner_id})
        if not owner:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "OWNER_NOT_FOUND", "message": f"User {owner_id} not found"},
            )

    # Check for duplicate account number
    existing = await db.accounts.find_one({"number": body.number})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "ACCOUNT_NUMBER_EXISTS", "message": "Account number already exists"},
        )

    account_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    account_doc = {
        "_id": account_id,
        "number": body.number,
        "name": body.name,
        "owner_ids": body.owner_ids,
        "balance": 0,
        "version": 0,
        "overdraft_limit": body.overdraft_limit,
        "currency": body.currency,
        "status": "active",
        "held": 0,
        "latest_entry_hash": None,
        "created_at": now,
    }

    await db.accounts.insert_one(account_doc)

    # Audit log
    await db.audit_log.insert_one({
        "_id": str(uuid.uuid4()),
        "actor_id": user["_id"],
        "action": "create_account",
        "target_type": "account",
        "target_id": account_id,
        "details": {"number": body.number, "owner_ids": body.owner_ids},
        "created_at": now,
    })

    return _account_to_response(account_doc)


@router.get("", response_model=list[AccountResponse])
async def list_accounts(
    user: Annotated[dict, Depends(get_current_user)],
):
    """
    List accounts.
    - admin/auditor: see all accounts
    - holder: see only own accounts
    """
    db = get_db()

    if user["role"] in ("admin", "auditor"):
        cursor = db.accounts.find({"_id": {"$ne": "EXTERNAL"}})
    else:
        # Holder sees only accounts they own
        cursor = db.accounts.find({
            "owner_ids": user["_id"],
            "_id": {"$ne": "EXTERNAL"},
        })

    accounts = await cursor.to_list(length=1000)
    return [_account_to_response(a) for a in accounts]


@router.get("/{account_id}", response_model=AccountResponse)
async def get_account(
    account_id: str,
    user: Annotated[dict, Depends(get_current_user)],
):
    """
    Get a single account.
    Returns 404 for non-owned accounts (not 403) to prevent enumeration.
    """
    account = await require_account_access(account_id, user)
    return _account_to_response(account)


@router.patch("/{account_id}/freeze")
async def freeze_account(
    account_id: str,
    user: Annotated[dict, Depends(require_role("admin"))],
):
    """Freeze an account. Admin only. Frozen accounts cannot transact."""
    db = get_db()

    result = await db.accounts.update_one(
        {"_id": account_id, "status": "active"},
        {"$set": {"status": "frozen"}},
    )

    if result.matched_count == 0:
        # Either account doesn't exist or is already frozen/closed
        acct = await db.accounts.find_one({"_id": account_id})
        if not acct:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "NOT_FOUND", "message": "Account not found"},
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "INVALID_STATUS", "message": f"Account is {acct['status']}, cannot freeze"},
        )

    # Audit log
    await db.audit_log.insert_one({
        "_id": str(uuid.uuid4()),
        "actor_id": user["_id"],
        "action": "freeze_account",
        "target_type": "account",
        "target_id": account_id,
        "details": {},
        "created_at": datetime.now(timezone.utc),
    })

    return {"message": "Account frozen", "account_id": account_id}


@router.patch("/{account_id}/unfreeze")
async def unfreeze_account(
    account_id: str,
    user: Annotated[dict, Depends(require_role("admin"))],
):
    """Unfreeze a frozen account. Admin only."""
    db = get_db()

    result = await db.accounts.update_one(
        {"_id": account_id, "status": "frozen"},
        {"$set": {"status": "active"}},
    )

    if result.matched_count == 0:
        acct = await db.accounts.find_one({"_id": account_id})
        if not acct:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "NOT_FOUND", "message": "Account not found"},
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "INVALID_STATUS", "message": f"Account is {acct['status']}, cannot unfreeze"},
        )

    await db.audit_log.insert_one({
        "_id": str(uuid.uuid4()),
        "actor_id": user["_id"],
        "action": "unfreeze_account",
        "target_type": "account",
        "target_id": account_id,
        "details": {},
        "created_at": datetime.now(timezone.utc),
    })

    return {"message": "Account unfrozen", "account_id": account_id}


@router.patch("/{account_id}/owners")
async def update_owners(
    account_id: str,
    owner_ids: list[str],
    user: Annotated[dict, Depends(require_role("admin"))],
):
    """Update the owners of an account. Admin only."""
    db = get_db()

    acct = await db.accounts.find_one({"_id": account_id})
    if not acct:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Account not found"},
        )

    # Validate all owner_ids exist
    for oid in owner_ids:
        owner = await db.users.find_one({"_id": oid})
        if not owner:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "OWNER_NOT_FOUND", "message": f"User {oid} not found"},
            )

    old_owners = acct.get("owner_ids", [])
    await db.accounts.update_one(
        {"_id": account_id},
        {"$set": {"owner_ids": owner_ids}},
    )

    await db.audit_log.insert_one({
        "_id": str(uuid.uuid4()),
        "actor_id": user["_id"],
        "action": "update_owners",
        "target_type": "account",
        "target_id": account_id,
        "details": {"old_owners": old_owners, "new_owners": owner_ids},
        "created_at": datetime.now(timezone.utc),
    })

    return {"message": "Owners updated", "account_id": account_id, "owner_ids": owner_ids}


@router.patch("/{account_id}/overdraft")
async def set_overdraft_limit(
    account_id: str,
    overdraft_limit: int,
    user: Annotated[dict, Depends(require_role("admin"))],
):
    """Set the overdraft limit for an account. Admin only."""
    db = get_db()

    if not isinstance(overdraft_limit, int) or isinstance(overdraft_limit, bool):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "INVALID_AMOUNT", "message": "overdraft_limit must be integer paise"},
        )
    if overdraft_limit < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "INVALID_AMOUNT", "message": "overdraft_limit must be >= 0"},
        )

    acct = await db.accounts.find_one({"_id": account_id})
    if not acct:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Account not found"},
        )

    old_limit = acct.get("overdraft_limit", 0)
    await db.accounts.update_one(
        {"_id": account_id},
        {"$set": {"overdraft_limit": overdraft_limit}},
    )

    await db.audit_log.insert_one({
        "_id": str(uuid.uuid4()),
        "actor_id": user["_id"],
        "action": "set_overdraft_limit",
        "target_type": "account",
        "target_id": account_id,
        "details": {"old_limit": old_limit, "new_limit": overdraft_limit},
        "created_at": datetime.now(timezone.utc),
    })

    return {"message": "Overdraft limit updated", "account_id": account_id, "overdraft_limit": overdraft_limit}

