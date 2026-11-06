"""
ledger.py — The money engine.

Contains post_transaction(), the single function used by every money route.
All money movement runs inside one MongoDB transaction containing the
idempotency record, balance check-and-update, and all ledger entries.

Implementation in PART 3.
"""

