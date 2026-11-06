# LedgerLine

A money-movement system whose priority is **integrity over features**.
A small system whose balances are always right beats a large one that loses a rupee under load.

## Stack

- **Backend:** Python 3.11+, FastAPI, Motor (async MongoDB driver)
- **Database:** MongoDB Atlas (replica set — required for transactions)
- **Frontend:** React (Vite) + React Router
- **Auth:** JWT (bcrypt password hashing)
- **Tests:** pytest + httpx + asyncio against a real MongoDB replica set

## Quick Start (Clean Clone)

```bash
# 1. Clone
git clone <repo-url> && cd ledgerline

# 2. Backend setup
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 3. Configure
cp .env.example .env
# Edit .env with your MongoDB Atlas URI and JWT secret

# 4. Setup database (idempotent)
python -m app.scripts.setup_db

# 5. Seed test data
python -m app.scripts.seed

# 6. Run backend
uvicorn app.main:app --reload

# 7. Frontend setup (separate terminal)
cd ../frontend
npm install
npm run dev
```

## Seed Credentials

| Role | Email | Password |
|---|---|---|
| admin | admin@ledgerline.com | Admin@123456 |
| holder | holder@ledgerline.com | Holder@123456 |
| auditor | auditor@ledgerline.com | Auditor@123456 |

## Running Tests

```bash
cd backend
# Requires a real MongoDB replica set (Atlas or local single-node replica)
pytest -v
```

## MongoDB Atlas Least-Privilege Setup

1. Create a dedicated database user for the application with a custom role:
   - `find` and `insert` on `ledger_entries` (no update, no remove)
   - `find` and `insert` on `attempts` (no update, no remove)
   - `find`, `insert`, `update` on `accounts` (for balance updates)
   - `find`, `insert`, `update` on all other collections
2. Restrict the IP access list to your deployment host's IP(s).
3. Use the connection string with `retryWrites=true&w=majority`.

## Live URL

> To be added after deployment.

## Architecture

See [SCHEMA.md](docs/SCHEMA.md) for the data model,
[API.md](docs/API.md) for the endpoint reference,
[THREATS.md](THREATS.md) for the threat model,
and [WRITEUP.md](WRITEUP.md) for design decisions.
