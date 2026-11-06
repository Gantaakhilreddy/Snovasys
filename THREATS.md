# LedgerLine Threat Model

> This document tracks every known threat, how it's mitigated, and which test proves it.
> Status: ✅ Closed | ⚠️ Accepted (with reason) | 🔲 Open

## Threat Table

| # | Attack | How It Would Work | Mitigation in Code | Test That Proves It | Status |
|---|---|---|---|---|---|
| T1 | Concurrent overdraw (check-then-act) | Two withdrawals read balance=100, both see >=50, both debit → balance goes to 0 or negative | Atomic conditional `$inc` with `$gte` guard in a single `update_one` inside the transaction. No Python-side `if balance >= amount`. | `test_concurrent_overdraw` | 🔲 |
| T2 | Double-spend by replay | Client replays a successful transfer request → money moves twice | Idempotency key inserted inside the same transaction as the money move. Replay returns stored `response_snapshot`. | `test_idempotent_replay_sequential` | 🔲 |
| T3 | Replay with altered payload | Client reuses an idempotency key with a different amount/account | `request_hash` comparison: if key exists with a different hash → 422 `idempotency_key_reuse_mismatch` | `test_key_reuse_different_payload` | 🔲 |
| T4 | In-flight duplicate | Same key fired concurrently → two transactions start simultaneously | Idempotency insert inside the transaction causes a write conflict on the second attempt; MongoDB retries it, and on retry it sees the committed record and replays. | `test_idempotent_replay_concurrent` | 🔲 |
| T5 | Transfer from another user's account (IDOR) | Holder A specifies Holder B's account as `from_account_id` | Service layer checks `user_id in owner_ids`; returns **404** (not 403) to prevent enumeration. | `test_authorization_idor` | 🔲 |
| T6 | Transfer from frozen/closed account | Attacker transfers from a frozen account | Conditional update includes `status: "active"` filter. Frozen/closed accounts fail the conditional. | `test_frozen_account` | 🔲 |
| T7 | Negative/zero/float/overflow amounts | Client sends -100, 0, 3.14, or 2^64 as amount | Pydantic validator: `int`, `gt=0`, rejects float, max transaction limit. | `test_validation_amounts` | 🔲 |
| T8 | Transfer to self | Client sets `from == to` account | Explicit check in `post_transaction`: `from != to`. | `test_transfer_to_self` | 🔲 |
| T9 | Deadlock / opposing transfers | A→B and B→A fired simultaneously | MongoDB transaction write conflicts cause one to retry. Bounded retry with clean 409/503. | `test_opposing_transfers` | 🔲 |
| T10 | Partial failure (debit without credit) | Exception between debit and credit legs | Both inside one `with_transaction`; any exception → full rollback. | `test_failure_halfway` | 🔲 |
| T11 | Crash after commit, before response | Server crashes after MongoDB commit but before HTTP response; client retries | Idempotency key is committed with `response_snapshot`; retry returns stored result. | `test_crash_after_commit` | 🔲 |
| T12 | Refusal logging fails | Refusal recording raises an exception | Refusal is written in a separate small write outside the aborted transaction. Failure to log refusal does not cause money to move (the transaction already aborted). | `test_refusal_logging` | 🔲 |
| T13 | Ledger row edit/delete | Insider or bug modifies a ledger entry | (a) No update/delete code path. (b) DB role: `find`+`insert` only. (c) Hash chain: `verify_ledger.py` detects any modified row. | `test_append_only`, `test_verify_ledger_tamper` | 🔲 |
| T14 | Direct DB access by insider | Someone with Atlas admin credentials modifies data directly | ⚠️ **Accepted:** Cannot prevent an Atlas admin from modifying data. **Detectable** via hash chain verification and reconciliation. `verify_ledger.py` will report the first broken link. | — | ⚠️ Accepted |
| T15 | Hash-chain head truncation | Attacker deletes the latest entries and rewrites the chain from a point | `latest_entry_hash` stored on the `accounts` document. Verification starts from the account's stored hash and walks the chain. | `test_verify_ledger` | 🔲 |
| T16 | Idempotency key expiry → double-pay | After 48h TTL, the key is deleted. A replay is treated as new. | 48h window is generous for retries. Documented residual risk. Clients should not retry after 48h. | — | ⚠️ Accepted |
| T17 | Idempotency key squatting across users | User A sends key "abc", then User B reuses "abc" | Keys are namespaced: `_id = actor_id:key`. Different users have different namespaces. | `test_idempotency_namespacing` | 🔲 |
| T18 | JWT theft/replay | Attacker steals a JWT and makes requests | Short expiry (30min default). Role re-checked from DB on money routes. | — | 🔲 |
| T19 | Weak JWT secret | Brute-force the HMAC key | Config requires a strong secret. `.env.example` says "at least 32 chars". | — | 🔲 |
| T20 | Role escalation by token tampering | Modify the JWT `role` claim | JWT is signed with HMAC; tampering invalidates the signature. Role is re-fetched from DB on money routes. | `test_role_escalation` | 🔲 |
| T21 | Brute-force login | Automated password guessing | Rate limit: max 5 attempts, 15min lockout. `failed_login_attempts` counter + `locked_until`. | `test_login_lockout` | 🔲 |
| T22 | Mass assignment | Extra JSON fields like `balance`, `role` in request body | Pydantic models with explicit fields only. Extra fields are ignored. Server sets `initiated_by`, `balance`, `version`. | `test_mass_assignment` | 🔲 |
| T23 | NoSQL operator injection | `{"$gt": ""}` in login email field | Pydantic `EmailStr` validates email format. Query parameters are typed. No raw `dict` queries from user input. | `test_nosql_injection` | 🔲 |
| T24 | Rounding/unit confusion (rupees vs paise) | API accepts "100" meaning rupees but stores as paise | API boundary is always paise (int). Documentation and error messages state "paise". No conversion layer. | — | ✅ By design |
| T25 | Clock skew in statements | Entries ordered by timestamp show wrong order | Statements ordered by `seq` (per-account monotonic), not by `created_at`. Time is informational only. | — | ✅ By design |
| T26 | Reversal abuse | Multiple concurrent reversals of the same transaction | Unique sparse index `reverses_txn_id` on `ledger_entries`: only one reversal per original transaction. | `test_double_reversal` | 🔲 |
| T27 | Admin abuse | Admin moves money without oversight | Maker-checker on high-value transfers (stretch). All admin actions logged in `audit_log`. | — | 🔲 |
| T28 | CORS misconfiguration | Cross-origin requests from malicious sites | `CORS_ORIGINS` explicitly configured, not `*`. | — | ✅ |
| T29 | Transaction retry exhaustion | Heavy contention causes retry limit exceeded | Bounded retry with clean 409/503 and retry hint. Never a partial write. | `test_contention_retry` | 🔲 |
| T30 | Read-your-writes inconsistency | Statement shows stale data after a write | `readConcern: majority`, `writeConcern: majority` set explicitly on the client. | — | ✅ By config |
| T31 | JWT stored in localStorage | XSS steals the token | JWT stored in memory (React state). Trade-off documented: page refresh requires re-login. httpOnly cookie is an alternative with CSRF protection. | — | ⚠️ Accepted |

## Notes

- Tests marked 🔲 will be implemented in PART 7.
- Status will be updated as tests are written and pass.
- New threats discovered during development will be added here.
