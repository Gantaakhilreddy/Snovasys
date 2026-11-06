"""
seed.py — Seed initial data for LedgerLine.

Creates one admin, one holder (with 2 accounts), one auditor, and
a few sample transactions. Prints credentials for the README.

Usage:
    python -m app.scripts.seed
"""
import asyncio
import sys
import os
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from motor.motor_asyncio import AsyncIOMotorClient
from app.config import get_settings
from app.security import hash_password


async def seed() -> None:
    settings = get_settings()
    client = AsyncIOMotorClient(settings.mongodb_uri, w="majority", readConcernLevel="majority")
    db = client[settings.db_name]

    now = datetime.now(timezone.utc)

    # ── Users ─────────────────────────────────────────────────────────
    users = [
        {
            "_id": str(uuid.uuid4()),
            "email": "admin@ledgerline.com",
            "password_hash": hash_password("Admin@123456"),
            "role": "admin",
            "active": True,
            "failed_login_attempts": 0,
            "locked_until": None,
            "created_at": now,
        },
        {
            "_id": str(uuid.uuid4()),
            "email": "holder@ledgerline.com",
            "password_hash": hash_password("Holder@123456"),
            "role": "holder",
            "active": True,
            "failed_login_attempts": 0,
            "locked_until": None,
            "created_at": now,
        },
        {
            "_id": str(uuid.uuid4()),
            "email": "auditor@ledgerline.com",
            "password_hash": hash_password("Auditor@123456"),
            "role": "auditor",
            "active": True,
            "failed_login_attempts": 0,
            "locked_until": None,
            "created_at": now,
        },
    ]

    for user in users:
        existing = await db.users.find_one({"email": user["email"]})
        if existing:
            print(f"  User {user['email']} already exists, skipping")
            user["_id"] = existing["_id"]
        else:
            await db.users.insert_one(user)
            print(f"  Created user: {user['email']} (role: {user['role']})")

    admin_id = users[0]["_id"]
    holder_id = users[1]["_id"]

    # ── Accounts ──────────────────────────────────────────────────────
    accounts = [
        {
            "_id": str(uuid.uuid4()),
            "number": "ACCT-001",
            "name": "Holder Savings",
            "owner_ids": [holder_id],
            "balance": 500_000,  # 5,000.00 INR
            "version": 0,
            "overdraft_limit": 0,
            "currency": "INR",
            "status": "active",
            "held": 0,
            "latest_entry_hash": None,
            "created_at": now,
        },
        {
            "_id": str(uuid.uuid4()),
            "number": "ACCT-002",
            "name": "Holder Current",
            "owner_ids": [holder_id],
            "balance": 200_000,  # 2,000.00 INR
            "version": 0,
            "overdraft_limit": 0,
            "currency": "INR",
            "status": "active",
            "held": 0,
            "latest_entry_hash": None,
            "created_at": now,
        },
    ]

    for acct in accounts:
        existing = await db.accounts.find_one({"number": acct["number"]})
        if existing:
            print(f"  Account {acct['number']} already exists, skipping")
            acct["_id"] = existing["_id"]
        else:
            await db.accounts.insert_one(acct)
            print(f"  Created account: {acct['number']} ({acct['name']}) balance={acct['balance']} paise")

    print("\n═══════════════════════════════════════════════")
    print("  SEED CREDENTIALS (put in README)")
    print("═══════════════════════════════════════════════")
    print(f"  admin:   admin@ledgerline.com   / Admin@123456")
    print(f"  holder:  holder@ledgerline.com  / Holder@123456")
    print(f"  auditor: auditor@ledgerline.com / Auditor@123456")
    print(f"")
    print(f"  Accounts: ACCT-001 (5000 INR), ACCT-002 (2000 INR)")
    print("═══════════════════════════════════════════════\n")

    client.close()


if __name__ == "__main__":
    asyncio.run(seed())

