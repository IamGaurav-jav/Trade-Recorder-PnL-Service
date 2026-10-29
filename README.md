# Trade Recorder & PnL Service

A production-ready backend service that ingests trades from multiple venues, tracks positions using **Average Cost**, and reports realized & unrealized PnL. Built with Python, FastAPI, and SQLAlchemy.

## Features

- **Trade Ingestion** — Record BUY/SELL trades from multiple venues with full validation
- **Idempotency** — Duplicate trades (same `venue` + `trade_id`) are safely ignored
- **Oversell Protection** — SELL orders exceeding the current position are rejected atomically
- **Position Tracking** — Real-time net quantity and weighted average cost per symbol
- **PnL Reporting** — Realized PnL (from closed trades) and unrealized PnL (from latest market prices)
- **Reconciliation** — Compare internal trade records against external venue statements
- **Decimal Precision** — All monetary values use Python's `Decimal` type (never floating-point)
- **Structured Logging** — Python `logging` module with timestamps and log levels (zero `print()` calls)

## Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3.11+ |
| Framework | FastAPI |
| Database | SQLite (default) / PostgreSQL (via env var) |
| ORM | SQLAlchemy 2.0 (async) |
| Validation | Pydantic v2 |
| Testing | pytest + httpx |

Everything is **100% free and open-source**.

---

## Quick Start

### 1. Clone & Setup

```bash
git clone <your-repo-url>
cd assignment

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# (Optional) Install dev/test dependencies
pip install -r requirements-dev.txt
```

### 2. Configure Environment

```bash
# Copy the example env file
cp .env.example .env

# Edit .env if needed (defaults work out of the box)
```

Default `.env`:
```
DATABASE_URL=sqlite+aiosqlite:///./trades.db
LOG_LEVEL=INFO
ENVIRONMENT=development
```

### 3. Run the Server

```bash
uvicorn app.main:app --reload
```

The server starts at **http://127.0.0.1:8000**

**Interactive API docs** (Swagger UI): http://127.0.0.1:8000/docs

### 4. Run Tests

```bash
pytest -v
```

---

## API Reference

### `POST /trades` — Ingest a Trade

```bash
curl -X POST http://127.0.0.1:8000/trades \
  -H "Content-Type: application/json" \
  -d '{
    "venue": "binance",
    "trade_id": "T-1001",
    "symbol": "BTC-USD",
    "side": "BUY",
    "quantity": "10",
    "price": "100",
    "timestamp": "2026-10-28T10:00:00Z"
  }'
```

| Status | Meaning |
|---|---|
| `201` | Trade created |
| `200` | Duplicate trade (idempotent, ignored) |
| `409` | Oversell rejected |
| `422` | Validation error (negative qty, invalid side, etc.) |

### `GET /trades` — List Trades

```bash
# All trades
curl http://127.0.0.1:8000/trades

# Filter by symbol
curl http://127.0.0.1:8000/trades?symbol=BTC-USD

# Filter by venue
curl http://127.0.0.1:8000/trades?venue=binance
```

### `GET /positions` — View All Positions

```bash
curl http://127.0.0.1:8000/positions
```

### `GET /positions/{symbol}` — View Position for Symbol

```bash
curl http://127.0.0.1:8000/positions/BTC-USD
```

### `POST /prices` — Set Latest Market Price

```bash
curl -X POST http://127.0.0.1:8000/prices \
  -H "Content-Type: application/json" \
  -d '{"symbol": "BTC-USD", "price": "125"}'
```

### `GET /pnl` — View PnL Report

```bash
# All symbols
curl http://127.0.0.1:8000/pnl

# Specific symbol
curl http://127.0.0.1:8000/pnl/BTC-USD
```

### `POST /reconcile` — Reconcile Against Venue Statement

```bash
curl -X POST http://127.0.0.1:8000/reconcile \
  -H "Content-Type: application/json" \
  -d '{
    "venue": "binance",
    "trades": [
      {"trade_id": "T1", "symbol": "BTC-USD", "side": "BUY", "quantity": "10", "price": "100", "timestamp": "2026-10-28T10:00:00Z"},
      {"trade_id": "T2", "symbol": "BTC-USD", "side": "BUY", "quantity": "6", "price": "101", "timestamp": "2026-10-28T11:00:00Z"},
      {"trade_id": "T3", "symbol": "BTC-USD", "side": "BUY", "quantity": "1", "price": "99", "timestamp": "2026-10-28T12:00:00Z"}
    ]
  }'
```

---

## Worked Example

Following the assignment specification:

```bash
# 1. BUY 10 @ 100
curl -X POST http://127.0.0.1:8000/trades -H "Content-Type: application/json" \
  -d '{"venue":"binance","trade_id":"T-1","symbol":"BTC-USD","side":"BUY","quantity":"10","price":"100","timestamp":"2026-10-28T10:00:00Z"}'

# 2. BUY 10 @ 110
curl -X POST http://127.0.0.1:8000/trades -H "Content-Type: application/json" \
  -d '{"venue":"binance","trade_id":"T-2","symbol":"BTC-USD","side":"BUY","quantity":"10","price":"110","timestamp":"2026-10-28T11:00:00Z"}'

# 3. SELL 5 @ 120
curl -X POST http://127.0.0.1:8000/trades -H "Content-Type: application/json" \
  -d '{"venue":"binance","trade_id":"T-3","symbol":"BTC-USD","side":"SELL","quantity":"5","price":"120","timestamp":"2026-10-28T12:00:00Z"}'

# 4. Set latest price to 125
curl -X POST http://127.0.0.1:8000/prices -H "Content-Type: application/json" \
  -d '{"symbol":"BTC-USD","price":"125"}'

# 5. Check PnL
curl http://127.0.0.1:8000/pnl/BTC-USD
```

**Expected PnL Response:**
```json
{
  "symbol": "BTC-USD",
  "net_quantity": "15",
  "average_cost": "105",
  "realized_pnl": "75",
  "unrealized_pnl": "300",
  "total_pnl": "375",
  "latest_price": "125"
}
```

---

## Using PostgreSQL (Optional)

To use PostgreSQL instead of SQLite:

1. Install the async PostgreSQL driver:
   ```bash
   pip install asyncpg
   ```

2. Update `.env`:
   ```
   DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/trades
   ```

3. Run the server as usual — tables are created automatically.

---

## Project Structure

```
assignment/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app, lifespan, exception handlers
│   ├── config.py             # Environment settings (.env)
│   ├── logger.py             # Centralized logging config
│   ├── exceptions.py         # Custom domain exceptions
│   ├── db.py                 # Async database engine & sessions
│   ├── models.py             # SQLAlchemy ORM models
│   ├── schemas.py            # Pydantic request/response schemas
│   ├── api/                  # API route handlers
│   │   ├── trades.py
│   │   ├── positions.py
│   │   ├── pnl.py
│   │   ├── prices.py
│   │   └── reconciliation.py
│   └── services/             # Business logic layer
│       ├── trade_service.py
│       ├── pnl_service.py
│       └── reconciliation_service.py
├── tests/                    # Automated test suite
│   ├── conftest.py
│   ├── test_trades.py
│   ├── test_idempotency.py
│   ├── test_positions.py
│   ├── test_pnl.py
│   ├── test_oversell.py
│   ├── test_concurrency.py
│   └── test_reconciliation.py
├── requirements.txt
├── requirements-dev.txt
├── .env.example
├── .gitignore
├── pyproject.toml
├── DESIGN.md
└── AI_USAGE.md
```
