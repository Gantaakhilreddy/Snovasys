# LedgerLine — AI Prompt Log

> At least 5 dated entries documenting: prompt → what AI produced → what was wrong → what was done → commit link.
> At least 2 entries must be on integrity/concurrency/idempotency.

---

## Entry 1 — 2026-11-06 — Project skeleton and data model

**Prompt:** "Create the LedgerLine project skeleton with Pydantic models, setup_db.py, and SCHEMA.md per PART 1 spec."

**What AI produced:** Initial project structure with all files.

**What was wrong:** TBD — reviewing generated code for common AI mistakes:
- [ ] Check: Are money fields truly `int` everywhere (no `float`, no `Decimal`)?
- [ ] Check: Does setup_db.py create the `$expr` validator correctly for `balance >= -overdraft_limit`?
- [ ] Check: Is the EXTERNAL account seeded with appropriate overdraft limit?
- [ ] Check: Are write/read concerns set to `majority` on the client?

**What was done:** Manual review and correction in progress.

**Commit:** `[PART 1]` (pending)

---

*Entries 2-5 will be added as development continues through PARTs 2-9.*
