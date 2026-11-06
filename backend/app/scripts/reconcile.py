"""
reconcile.py — Reconciliation checks for LedgerLine.

Verifies:
1. Each account's balance matches the replay of its ledger entries.
2. Global sum of debits == sum of credits.
3. Sum of customer balances == EXTERNAL net inflow.

Usage:
    python -m app.scripts.reconcile
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from motor.motor_asyncio import AsyncIOMotorClient
from app.config import get_settings


async def reconcile() -> dict:
    """Run all reconciliation checks. Returns a report dict."""
    settings = get_settings()
    client = AsyncIOMotorClient(settings.mongodb_uri, w="majority", readConcernLevel="majority")
    db = client[settings.db_name]

    report = {
        "balance_mismatches": [],
        "global_debit_credit_match": True,
        "customer_external_match": True,
        "total_debits": 0,
        "total_credits": 0,
        "ok": True,
        "details": {},
    }

    # ── 1. Per-account balance from ledger replay ─────────────────────
    accounts = await db.accounts.find({}).to_list(length=None)

    for account in accounts:
        acct_id = account["_id"]

        # Compute balance from ledger entries
        pipeline = [
            {"$match": {"account_id": acct_id}},
            {"$group": {
                "_id": None,
                "total_credits": {
                    "$sum": {"$cond": [{"$eq": ["$direction", "credit"]}, "$amount", 0]}
                },
                "total_debits": {
                    "$sum": {"$cond": [{"$eq": ["$direction", "debit"]}, "$amount", 0]}
                },
            }},
        ]
        result = await db.ledger_entries.aggregate(pipeline).to_list(length=1)

        if result:
            computed_balance = result[0]["total_credits"] - result[0]["total_debits"]
        else:
            computed_balance = 0

        if computed_balance != account["balance"]:
            report["balance_mismatches"].append({
                "account_id": acct_id,
                "stored_balance": account["balance"],
                "computed_balance": computed_balance,
                "difference": account["balance"] - computed_balance,
            })
            report["ok"] = False

    # ── 2. Global debits == credits ───────────────────────────────────
    global_pipeline = [
        {"$group": {
            "_id": "$direction",
            "total": {"$sum": "$amount"},
        }},
    ]
    global_result = await db.ledger_entries.aggregate(global_pipeline).to_list(length=2)

    for item in global_result:
        if item["_id"] == "debit":
            report["total_debits"] = item["total"]
        elif item["_id"] == "credit":
            report["total_credits"] = item["total"]

    if report["total_debits"] != report["total_credits"]:
        report["global_debit_credit_match"] = False
        report["ok"] = False

    # ── 3. Sum(customer balances) == EXTERNAL net inflow ──────────────
    customer_balance_sum = sum(
        a["balance"] for a in accounts if a["_id"] != settings.external_account_id
    )
    external_account = await db.accounts.find_one({"_id": settings.external_account_id})
    if external_account:
        # EXTERNAL's balance should be the negative of customer balances
        # (what goes into customers comes out of EXTERNAL)
        external_balance = external_account["balance"]
        expected_external = -customer_balance_sum
        if external_balance != expected_external:
            report["customer_external_match"] = False
            report["ok"] = False
            report["details"]["customer_balance_sum"] = customer_balance_sum
            report["details"]["external_balance"] = external_balance
            report["details"]["expected_external"] = expected_external

    client.close()
    return report


async def main():
    report = await reconcile()
    if report["ok"]:
        print(f"✅ Reconciliation passed.")
        print(f"   Total debits:  {report['total_debits']} paise")
        print(f"   Total credits: {report['total_credits']} paise")
    else:
        print(f"❌ RECONCILIATION FAILED!")
        if report["balance_mismatches"]:
            for m in report["balance_mismatches"]:
                print(f"   Account {m['account_id']}: stored={m['stored_balance']}, computed={m['computed_balance']}, diff={m['difference']}")
        if not report["global_debit_credit_match"]:
            print(f"   Global mismatch: debits={report['total_debits']}, credits={report['total_credits']}")
        if not report["customer_external_match"]:
            d = report["details"]
            print(f"   Customer/EXTERNAL mismatch: customer_sum={d.get('customer_balance_sum')}, external={d.get('external_balance')}, expected_external={d.get('expected_external')}")
    return report


if __name__ == "__main__":
    asyncio.run(main())

