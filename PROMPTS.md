# LedgerLine — AI Prompt Log

> At least 5 dated entries documenting: prompt → what AI produced → what was wrong → what was done → commit link.
> At least 2 entries must be on integrity/concurrency/idempotency.

---

## Entry 1 — 2026-11-06 — Project skeleton: bool-as-int bug in money validators

**Prompt:** "Create the LedgerLine project skeleton with Pydantic models, setup_db.py, and SCHEMA.md per PART 1 spec."

**What AI produced:** Pydantic validators for money fields that checked `isinstance(v, float)` and `not isinstance(v, int)` but did NOT guard against `bool`.

**What was wrong:** In Python, `bool` is a subclass of `int` (`isinstance(True, int)` returns `True`). This means `DepositRequest(amount=True)` would silently accept `True` as a valid amount of 1 paisa. A boolean value should never be accepted as money.

**What was done:** Added `isinstance(v, bool)` check **before** the `isinstance(v, int)` check in all 6 money validators across `account.py` and `ledger.py`. Added test `test_deposit_rejects_bool` and `test_transfer_rejects_bool` to prove it.

**Commit:** `9f9f47a` — PART 1

---

## Entry 2 — 2026-11-06 — Pydantic v2 min_items deprecation

**Prompt:** Same as Entry 1.

**What AI produced:** `AccountCreate.owner_ids` used `Field(..., min_items=1)` which is a Pydantic v1 syntax.

**What was wrong:** In Pydantic v2, `min_items` is deprecated for list fields. The correct parameter is `min_length`.

**What was done:** Changed to `Field(..., min_length=1)`.

**Commit:** `9f9f47a` — PART 1

---

*Entries 2-5 will be added as development continues through PARTs 2-9.*
