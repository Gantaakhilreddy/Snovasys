# LedgerLine API Reference

> Full endpoint documentation will be completed in PART 4 and PART 8.
> This file is initialized in PART 1 with the role matrix and conventions.

## Base URL

`/api/v1` (to be added as router prefix)

## Authentication

All endpoints except `/health` and `/auth/login` require a valid JWT in the `Authorization: Bearer <token>` header.

### Role Matrix

| Endpoint | admin | holder | auditor |
|---|:---:|:---:|:---:|
| POST /auth/register | ✅ | ❌ | ❌ |
| POST /auth/login | ✅ | ✅ | ✅ |
| POST /accounts | ✅ | ❌ | ❌ |
| GET /accounts | ✅ (all) | ✅ (own) | ✅ (all) |
| GET /accounts/{id} | ✅ | ✅ (own) | ✅ |
| POST /accounts/{id}/deposit | ✅ | ❌ | ❌ |
| POST /accounts/{id}/withdraw | ✅ | ✅ (own) | ❌ |
| POST /transfers | ❌ | ✅ (own src) | ❌ |
| POST /transactions/{id}/reverse | ✅ | ❌ | ❌ |
| GET /accounts/{id}/statement | ✅ | ✅ (own) | ✅ |
| PATCH /accounts/{id}/freeze | ✅ | ❌ | ❌ |
| PATCH /accounts/{id}/unfreeze | ✅ | ❌ | ❌ |
| GET /attempts | ✅ | ❌ | ✅ |
| GET /audit-log | ✅ | ❌ | ✅ |
| GET /integrity/verify | ✅ | ❌ | ✅ |
| GET /integrity/reconcile | ✅ | ❌ | ✅ |
| GET /flags | ✅ | ❌ | ✅ |
| POST /flags/{id}/decision | ✅ | ❌ | ❌ |

### Authorization Rules

- **Object-level:** For any `account_id`, the service layer loads the account and checks `user_id in owner_ids`. Non-owned accounts return **404 (not 403)** to prevent account enumeration.
- **`initiated_by`:** Always taken from the JWT `sub` claim. Never accepted from the request body.
- **Role re-check:** On money-touching routes, the user's role is re-fetched from the DB (not just the JWT) to catch role changes since token issuance.

### Error Format

All errors return:

```json
{
  "code": "ERROR_CODE",
  "message": "Human-readable message",
  "request_id": "uuid"
}
```

### Required Headers

- `Authorization: Bearer <token>` (all protected endpoints)
- `Idempotency-Key: <uuid>` (all money-moving endpoints: deposit, withdraw, transfer, reverse)
