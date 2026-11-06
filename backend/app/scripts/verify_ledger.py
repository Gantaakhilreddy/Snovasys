"""
verify_ledger.py — Verify the integrity of ledger entry hash chains.

For each account, walks the per-account chain of ledger entries in seq order,
recomputes the hash of each entry, and reports the first broken link.

Usage:
    python -m app.scripts.verify_ledger
"""
import asyncio
import hashlib
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from motor.motor_asyncio import AsyncIOMotorClient
from app.config import get_settings


def compute_entry_hash(prev_hash: str | None, entry: dict) -> str:
    """Recompute the hash for a ledger entry from its canonical fields."""
    canonical = {
        "txn_id": entry["txn_id"],
        "account_id": entry["account_id"],
        "direction": entry["direction"],
        "amount": entry["amount"],
        "balance_after": entry["balance_after"],
        "seq": entry["seq"],
        "kind": entry["kind"],
        "counterparty_account_id": entry.get("counterparty_account_id"),
        "initiated_by": entry["initiated_by"],
        "idempotency_key": entry.get("idempotency_key"),
        "memo": entry.get("memo", ""),
        "created_at": entry["created_at"].isoformat() if entry.get("created_at") else "",
    }
    payload = (prev_hash or "") + json.dumps(canonical, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def verify() -> dict:
    """Verify all hash chains. Returns a report dict."""
    settings = get_settings()
    client = AsyncIOMotorClient(settings.mongodb_uri, w="majority", readConcernLevel="majority")
    db = client[settings.db_name]

    report = {"accounts_checked": 0, "entries_checked": 0, "broken_chains": [], "ok": True}

    # Get all accounts
    accounts = await db.accounts.find({}).to_list(length=None)

    for account in accounts:
        acct_id = account["_id"]
        report["accounts_checked"] += 1

        # Walk the chain in seq order
        entries = await db.ledger_entries.find(
            {"account_id": acct_id}
        ).sort("seq", 1).to_list(length=None)

        prev_hash = None
        for entry in entries:
            report["entries_checked"] += 1

            # Verify prev_hash linkage
            if entry.get("prev_hash") != prev_hash:
                report["broken_chains"].append({
                    "account_id": acct_id,
                    "seq": entry["seq"],
                    "error": "prev_hash mismatch",
                    "expected_prev_hash": prev_hash,
                    "actual_prev_hash": entry.get("prev_hash"),
                })
                report["ok"] = False
                break  # Report first broken link per account

            # Verify entry hash
            expected_hash = compute_entry_hash(prev_hash, entry)
            if entry.get("hash") != expected_hash:
                report["broken_chains"].append({
                    "account_id": acct_id,
                    "seq": entry["seq"],
                    "error": "hash mismatch",
                    "expected_hash": expected_hash,
                    "actual_hash": entry.get("hash"),
                })
                report["ok"] = False
                break

            prev_hash = entry["hash"]

        # Verify the head matches accounts.latest_entry_hash
        if entries and account.get("latest_entry_hash") != prev_hash:
            report["broken_chains"].append({
                "account_id": acct_id,
                "error": "latest_entry_hash mismatch on account document",
                "expected": prev_hash,
                "actual": account.get("latest_entry_hash"),
            })
            report["ok"] = False

    client.close()
    return report


async def main():
    report = await verify()
    if report["ok"]:
        print(f"✅ All hash chains verified. {report['accounts_checked']} accounts, {report['entries_checked']} entries.")
    else:
        print(f"❌ BROKEN CHAINS DETECTED!")
        for bc in report["broken_chains"]:
            print(f"   Account {bc['account_id']}, seq {bc.get('seq', 'N/A')}: {bc['error']}")
    return report


if __name__ == "__main__":
    asyncio.run(main())

