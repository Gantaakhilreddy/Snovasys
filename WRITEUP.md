# LedgerLine — Write-Up

> What was built, what was deliberately not built, the integrity and concurrency model,
> how AI was used and where it was wrong, and what is unfinished.

## What Was Built

*To be completed as each PART is delivered.*

### PART 1: Project Skeleton and Data Model
- FastAPI application structure with Motor async MongoDB driver
- Pydantic models for all collections with strict integer paise validation
- Idempotent `setup_db.py` that creates collections, validators, and indexes
- EXTERNAL clearing account for two-legged deposits/withdrawals
- JSON schema validator on accounts (defence-in-depth balance floor)
- Comprehensive SCHEMA.md documenting every index and which attack it blocks

## What Was Deliberately Not Built

- **Multi-currency:** Currency field exists on every money document but only INR is accepted in v1. Validator rejects non-INR.
- **Scheduled/batch transfers:** Not in scope for v1.
- **Holds/maker-checker:** Marked as stretch in PART 3. Fields exist (`held` on accounts) but may be skipped if time is short.
- **Real payment gateway integration:** Deposits/withdrawals are simulated via the EXTERNAL account.
- **Multi-tenant isolation:** Single-tenant system in v1.

## Integrity and Concurrency Model

*To be written after PART 3 (the money engine).*

### Why Double-Entry
*TBD*

### Why Transactions + Conditional $inc + Same-Transaction Idempotency
*TBD*

### How In-Flight Duplicates Behave
*TBD*

## How AI Was Used and Where It Was Wrong

*To be updated throughout development. See PROMPTS.md for the detailed log.*

## What Is Unfinished

*To be updated as development progresses.*
