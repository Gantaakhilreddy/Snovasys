"""
setup_db.py — Idempotent database setup for LedgerLine.

Creates collections with JSON schema validators, indexes, and seeds the
EXTERNAL system account. Safe to run repeatedly from a clean clone.

Usage:
    python -m app.scripts.setup_db
"""
import asyncio
import sys
import os

# Add the backend directory to the path so we can import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import CollectionInvalid, OperationFailure
from pymongo import IndexModel, ASCENDING

from app.config import get_settings


async def setup() -> None:
    settings = get_settings()
    client = AsyncIOMotorClient(settings.mongodb_uri, w="majority", readConcernLevel="majority")
    db = client[settings.db_name]

    print(f"Setting up database: {settings.db_name}")

    # ── 1. users ──────────────────────────────────────────────────────
    try:
        await db.create_collection("users")
        print("  Created collection: users")
    except (CollectionInvalid, OperationFailure):
        print("  Collection users already exists")

    await db.users.create_index("email", unique=True, name="idx_users_email_unique")
    print("  Index: idx_users_email_unique (email, unique) — prevents duplicate registrations")

    # ── 2. accounts ───────────────────────────────────────────────────
    # JSON schema validator: balance must be int, balance >= -overdraft_limit
    # This is a defence-in-depth floor enforced by the DB itself.
    # NOTE: MongoDB JSON schema doesn't support cross-field comparison
    # (balance >= -overdraft_limit) directly in $jsonSchema. We use a
    # workaround with a $expr validator instead.
    accounts_validator = {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["balance", "version", "currency", "status"],
            "properties": {
                "balance": {
                    "bsonType": "int",
                    "description": "Balance in paise, must be integer"
                },
                "version": {
                    "bsonType": "int",
                    "description": "Optimistic concurrency version"
                },
                "overdraft_limit": {
                    "bsonType": "int",
                    "minimum": 0,
                    "description": "Maximum overdraft in paise"
                },
                "currency": {
                    "enum": ["INR"],
                    "description": "Only INR supported in v1"
                },
                "status": {
                    "enum": ["active", "frozen", "closed"],
                    "description": "Account lifecycle status"
                },
                "held": {
                    "bsonType": "int",
                    "minimum": 0,
                    "description": "Held/reserved funds in paise"
                }
            }
        }
    }

    try:
        await db.create_collection("accounts", validator=accounts_validator)
        print("  Created collection: accounts (with JSON schema validator)")
    except (CollectionInvalid, OperationFailure):
        # Collection exists; update the validator
        try:
            await db.command("collMod", "accounts", validator=accounts_validator)
            print("  Updated validator on accounts")
        except OperationFailure as e:
            print(f"  Warning: could not update accounts validator: {e}")

    # Add the $expr validator for balance >= -overdraft_limit as a separate validation
    # MongoDB doesn't support cross-field validation in $jsonSchema, so we add it
    # via $expr in the validator alongside $jsonSchema.
    accounts_full_validator = {
        "$and": [
            accounts_validator,
            {
                "$expr": {
                    "$gte": [
                        "$balance",
                        {"$multiply": ["$overdraft_limit", -1]}
                    ]
                }
            }
        ]
    }
    try:
        await db.command("collMod", "accounts", validator=accounts_full_validator)
        print("  Applied $expr validator: balance >= -overdraft_limit")
    except OperationFailure as e:
        print(f"  Warning: $expr validator on accounts not applied: {e}")

    await db.accounts.create_index("number", unique=True, name="idx_accounts_number_unique")
    print("  Index: idx_accounts_number_unique (number, unique) — prevents duplicate account numbers")
    await db.accounts.create_index("owner_ids", name="idx_accounts_owner_ids")
    print("  Index: idx_accounts_owner_ids — fast lookup of accounts by owner")

    # ── 3. ledger_entries ─────────────────────────────────────────────
    try:
        await db.create_collection("ledger_entries")
        print("  Created collection: ledger_entries")
    except (CollectionInvalid, OperationFailure):
        print("  Collection ledger_entries already exists")

    # Unique compound index: (account_id, seq) ensures per-account monotonic sequence.
    # Blocks: insertion of duplicate seq numbers per account (fork in the hash chain).
    await db.ledger_entries.create_index(
        [("account_id", ASCENDING), ("seq", ASCENDING)],
        unique=True,
        name="idx_ledger_account_seq_unique",
    )
    print("  Index: idx_ledger_account_seq_unique (account_id+seq, unique) — enforces per-account monotonic sequence, blocks hash chain forks")

    # Index on txn_id for looking up all legs of a transaction.
    await db.ledger_entries.create_index("txn_id", name="idx_ledger_txn_id")
    print("  Index: idx_ledger_txn_id — fast lookup of transaction legs")

    # Index for statement queries (account_id + created_at for time-range filtering)
    await db.ledger_entries.create_index(
        [("account_id", ASCENDING), ("created_at", ASCENDING)],
        name="idx_ledger_account_created",
    )
    print("  Index: idx_ledger_account_created — cursor-paginated statements")

    # ── 4. idempotency_keys ───────────────────────────────────────────
    try:
        await db.create_collection("idempotency_keys")
        print("  Created collection: idempotency_keys")
    except (CollectionInvalid, OperationFailure):
        print("  Collection idempotency_keys already exists")

    # TTL index: auto-delete completed keys after 48 hours.
    # After expiry, a replay of the same key could double-pay.
    # Mitigation: 48h is long enough that legitimate retries are covered.
    # Residual risk: a client that retries after 48h could cause a double-post.
    # This is documented in THREATS.md.
    # The TTL only fires on expires_at, which is set only when status=completed.
    # In-progress keys never expire (they have no expires_at).
    await db.idempotency_keys.create_index(
        "expires_at",
        expireAfterSeconds=0,
        name="idx_idempotency_ttl",
    )
    print("  Index: idx_idempotency_ttl (TTL on expires_at) — auto-cleanup after 48h, see THREATS.md for residual risk")

    # ── 5. attempts ───────────────────────────────────────────────────
    try:
        await db.create_collection("attempts")
        print("  Created collection: attempts")
    except (CollectionInvalid, OperationFailure):
        print("  Collection attempts already exists")

    await db.attempts.create_index("actor_id", name="idx_attempts_actor")
    print("  Index: idx_attempts_actor — filter by actor")
    await db.attempts.create_index("outcome", name="idx_attempts_outcome")
    print("  Index: idx_attempts_outcome — filter by outcome (refused, duplicate_replay, etc.)")
    await db.attempts.create_index("idempotency_key", name="idx_attempts_idem_key")
    print("  Index: idx_attempts_idem_key — correlate attempts with idempotency keys")
    await db.attempts.create_index("created_at", name="idx_attempts_created_at")
    print("  Index: idx_attempts_created_at — time-range queries on attempts")

    # ── 6. audit_log ──────────────────────────────────────────────────
    try:
        await db.create_collection("audit_log")
        print("  Created collection: audit_log")
    except (CollectionInvalid, OperationFailure):
        print("  Collection audit_log already exists")

    await db.audit_log.create_index("actor_id", name="idx_audit_actor")
    await db.audit_log.create_index("created_at", name="idx_audit_created_at")
    await db.audit_log.create_index("target_id", name="idx_audit_target")
    print("  Indexes on audit_log: actor_id, created_at, target_id")

    # ── 7. flags ──────────────────────────────────────────────────────
    try:
        await db.create_collection("flags")
        print("  Created collection: flags")
    except (CollectionInvalid, OperationFailure):
        print("  Collection flags already exists")

    await db.flags.create_index("status", name="idx_flags_status")
    await db.flags.create_index("account_id", name="idx_flags_account")
    print("  Indexes on flags: status, account_id")

    # ── 8. reversal tracking ─────────────────────────────────────────
    # Unique index to enforce at-most-once reversal per transaction.
    # This lives in ledger_entries using a sparse unique index on reverses_txn_id.
    await db.ledger_entries.create_index(
        "reverses_txn_id",
        unique=True,
        sparse=True,
        name="idx_ledger_reverses_txn_unique",
    )
    print("  Index: idx_ledger_reverses_txn_unique (sparse, unique) — at-most-once reversal per transaction")

    # ── 9. Seed EXTERNAL system account ───────────────────────────────
    external = await db.accounts.find_one({"_id": settings.external_account_id})
    if not external:
        await db.accounts.insert_one({
            "_id": settings.external_account_id,
            "number": "EXTERNAL",
            "name": "External Clearing Account",
            "owner_ids": [],
            "balance": 0,
            "version": 0,
            "overdraft_limit": 2**53,  # effectively unlimited for system account
            "currency": "INR",
            "status": "active",
            "held": 0,
            "latest_entry_hash": None,
            "created_at": None,  # system account, no meaningful creation time
        })
        print("  Seeded EXTERNAL clearing account")
    else:
        print("  EXTERNAL clearing account already exists")

    print("\nDatabase setup complete.")
    client.close()


if __name__ == "__main__":
    asyncio.run(setup())
