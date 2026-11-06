# LedgerLine Database Schema

## Overview

LedgerLine uses MongoDB with a replica set (required for multi-document transactions).
All money values are stored as **integer paise** (`int`), never float or Decimal-as-string.
1 INR = 100 paise. The single currency (INR) is stored in a `currency` field on every
money document so multi-currency is a later extension.

---

## Collections

### 1. `users`

| Field | Type | Description |
|---|---|---|
| `_id` | string | Unique user identifier |
| `email` | string | Email address (unique) |
| `password_hash` | string | bcrypt hash |
| `role` | enum | `admin` \| `holder` \| `auditor` |
| `active` | bool | Whether the user can log in |
| `failed_login_attempts` | int | Counter for rate-limit/lockout |
| `locked_until` | datetime? | Lockout expiry |
| `created_at` | datetime | Account creation timestamp |

**Indexes:**

| Index | Fields | Properties | Attack Blocked |
|---|---|---|---|
| `idx_users_email_unique` | `email` | unique | Duplicate registration; enumeration via insert race |

---

### 2. `accounts`

| Field | Type | Description |
|---|---|---|
| `_id` | string | Unique account identifier |
| `number` | string | Human-readable account number (unique) |
| `name` | string | Display name |
| `owner_ids` | string[] | User IDs who own this account |
| `balance` | int | Balance in paise |
| `version` | int | Optimistic concurrency counter |
| `overdraft_limit` | int | Max overdraft in paise (default 0) |
| `currency` | string | Always "INR" in v1 |
| `status` | enum | `active` \| `frozen` \| `closed` |
| `held` | int | Reserved funds for pending approvals |
| `latest_entry_hash` | string? | Hash of the most recent ledger entry (for chain verification) |
| `created_at` | datetime | Creation timestamp |

**JSON Schema Validator (defence-in-depth):**
- `balance` must be `bsonType: "int"` — blocks float values at the DB level
- `overdraft_limit` must be `int >= 0`
- `currency` must be `"INR"`
- `status` must be one of `active`, `frozen`, `closed`
- `$expr` validator: `balance >= -overdraft_limit` — the DB itself refuses any update that would violate the overdraft floor, even if the application has a bug

**Indexes:**

| Index | Fields | Properties | Attack Blocked |
|---|---|---|---|
| `idx_accounts_number_unique` | `number` | unique | Duplicate account numbers; enumeration by guessing |
| `idx_accounts_owner_ids` | `owner_ids` | — | Fast ownership lookup for authorization checks |

---

### 3. `ledger_entries` (append-only, double-entry)

Every money movement creates exactly two entries: a debit and a credit. The invariant
`sum(debits) == sum(credits)` must hold at all times.

| Field | Type | Description |
|---|---|---|
| `_id` | string | Unique entry identifier |
| `txn_id` | string | Groups the debit+credit pair |
| `account_id` | string | Which account this entry belongs to |
| `direction` | enum | `debit` \| `credit` |
| `amount` | int > 0 | Amount in paise (always positive; direction says which way) |
| `balance_after` | int | Account balance after this entry |
| `seq` | int | Per-account monotonic sequence number |
| `prev_hash` | string? | Hash of the previous entry for this account |
| `hash` | string | `sha256(prev_hash + canonical fields)` |
| `kind` | enum | `deposit` \| `withdrawal` \| `transfer` \| `reversal` \| `adjustment` |
| `counterparty_account_id` | string? | The other account in a two-legged entry |
| `initiated_by` | string | User ID from JWT (never from request body) |
| `idempotency_key` | string? | Links to the idempotency record |
| `reverses_txn_id` | string? | For reversals: the original txn_id being reversed |
| `memo` | string | Human-readable note |
| `created_at` | datetime | Entry creation timestamp |

**Indexes:**

| Index | Fields | Properties | Attack Blocked |
|---|---|---|---|
| `idx_ledger_account_seq_unique` | `(account_id, seq)` | unique | Hash chain fork: prevents two entries with the same sequence number for one account. If a concurrent transaction tries to insert a duplicate seq, the unique index rejects it. |
| `idx_ledger_txn_id` | `txn_id` | — | Fast lookup of all legs of a transaction (for reconciliation, reversal lookup) |
| `idx_ledger_account_created` | `(account_id, created_at)` | — | Efficient cursor-paginated statements with time-range filtering |
| `idx_ledger_reverses_txn_unique` | `reverses_txn_id` | unique, sparse | At-most-once reversal: prevents a transaction from being reversed more than once, even under concurrent reversal attempts |

**Append-only enforcement (defence-in-depth):**
1. **Application:** No update or delete code path exists for `ledger_entries`.
2. **Database role:** A dedicated Atlas custom role grants only `find` and `insert` on this collection (no `update`, `remove`). See README for setup instructions.
3. **Tamper-evidence:** The per-account hash chain. `scripts/verify_ledger.py` recomputes every chain and reports the first broken link.

---

### 4. `idempotency_keys`

| Field | Type | Description |
|---|---|---|
| `_id` | string | `actor_id:key` (namespaced to prevent cross-user squatting) |
| `request_hash` | string | `sha256(canonical_json(kind, accounts, amount, memo))` |
| `status` | enum | `in_progress` \| `completed` |
| `response_snapshot` | object? | Stored response for replay |
| `txn_id` | string? | The transaction ID if completed successfully |
| `created_at` | datetime | When the key was first used |
| `expires_at` | datetime? | Set when completed; TTL fires on this field |

**Indexes:**

| Index | Fields | Properties | Attack Blocked |
|---|---|---|---|
| `idx_idempotency_ttl` | `expires_at` | TTL (expireAfterSeconds=0) | N/A (cleanup). **Residual risk:** after the 48h TTL expires and the document is deleted, a replay of the same key could cause a double-post. Mitigation: 48h is long enough for legitimate retries; document the window in THREATS.md. |

**Key namespacing:** The `_id` is `actor_id:key`, so user A cannot squat on user B's idempotency keys.

**After TTL expiry:** The idempotency document is deleted by MongoDB's TTL mechanism. If a client replays the same key after this, the system treats it as a new request and processes it again. This is a known residual risk documented in THREATS.md. Mitigation: the 48h window is generous for retries; clients should not retry after 48h.

---

### 5. `attempts` (append-only)

| Field | Type | Description |
|---|---|---|
| `_id` | string | Unique attempt identifier |
| `idempotency_key` | string? | The idempotency key used |
| `actor_id` | string | Who made the request |
| `kind` | string | `deposit`, `withdrawal`, `transfer`, `reversal`, `adjustment` |
| `params` | object | Request parameters (sanitised) |
| `request_hash` | string | Same hash as idempotency |
| `outcome` | enum | `posted` \| `refused` \| `duplicate_replay` \| `in_flight_conflict` |
| `reason_code` | string? | Why the request was refused |
| `txn_id` | string? | Transaction ID if posted |
| `created_at` | datetime | When the attempt was made |

**Indexes:**

| Index | Fields | Properties | Attack Blocked |
|---|---|---|---|
| `idx_attempts_actor` | `actor_id` | — | Fast lookup of attempts by actor |
| `idx_attempts_outcome` | `outcome` | — | Filter by outcome (refused, duplicate_replay, etc.) for audit review |
| `idx_attempts_idem_key` | `idempotency_key` | — | Correlate attempts with idempotency keys |
| `idx_attempts_created_at` | `created_at` | — | Time-range queries for audit |

**Append-only:** Same enforcement as `ledger_entries` — no update/delete code path, dedicated DB role.

---

### 6. `audit_log`

| Field | Type | Description |
|---|---|---|
| `_id` | string | Unique log entry identifier |
| `actor_id` | string | Who performed the action |
| `action` | string | e.g. `freeze_account`, `set_overdraft_limit`, `approve_flag` |
| `target_type` | string | e.g. `account`, `user`, `flag` |
| `target_id` | string | ID of the affected entity |
| `details` | object | Action-specific details |
| `created_at` | datetime | When the action was performed |

---

### 7. `flags`

| Field | Type | Description |
|---|---|---|
| `_id` | string | Unique flag identifier |
| `account_id` | string | Flagged account |
| `txn_id` | string? | Flagged transaction |
| `rule` | string | Which anomaly rule triggered |
| `severity` | string | `low`, `medium`, `high` |
| `description` | string | Human-readable description |
| `ai_summary` | string? | AI-generated explanation (text only) |
| `ai_model_version` | string? | Model version used |
| `ai_prompt` | string? | The prompt sent to the model |
| `status` | enum | `open` \| `confirmed` \| `dismissed` |
| `decided_by` | string? | Admin who decided |
| `decision_reason` | string? | Why |
| `decided_at` | datetime? | When |
| `created_at` | datetime | When the flag was raised |

---

## System Accounts

### EXTERNAL Clearing Account

- `_id`: `"EXTERNAL"`
- `number`: `"EXTERNAL"`
- Purpose: Makes deposits and withdrawals two-legged (EXTERNAL ↔ customer).
- The invariant is: **sum of all debits == sum of all credits, always.**
- Total of customer balances changes only through EXTERNAL.
- `overdraft_limit`: effectively unlimited (2^53 paise) so the system can always credit/debit.

---

## Index Summary: Which Attack Each Blocks

| Index | Attack | How It Blocks It |
|---|---|---|
| `idx_users_email_unique` | Duplicate registration | DB rejects second insert with same email |
| `idx_accounts_number_unique` | Account number collision | DB rejects duplicate account numbers |
| `idx_ledger_account_seq_unique` | Hash chain fork / double-entry | Two entries with same (account, seq) rejected; prevents forking the ledger |
| `idx_ledger_reverses_txn_unique` | Double reversal | Second reversal of same txn rejected by unique index, even under concurrency |
| Accounts JSON schema validator | Float balances, wrong currency | DB refuses writes with non-int balance or non-INR currency |
| Accounts `$expr` validator | Balance below overdraft floor | DB refuses any update that drops balance below `-overdraft_limit` |
| `idx_idempotency_ttl` | Stale key buildup | Cleanup only; see THREATS.md for residual risk after expiry |
