# Design Document

## Overview

This document describes the architectural and algorithmic decisions behind the Trade Recorder & PnL Service.

---

## Cost-Basis Method: Average Cost (Weighted Average)

### Why Average Cost?

The **Average Cost** method was selected because:

1. **Simplicity & clarity**: All holdings of a symbol share a single blended cost. There are no individual lots to track.
2. **Correctness**: The method is widely used in crypto exchanges, FX platforms, and commodity trading.
3. **Auditability**: The formula is straightforward and easy to verify.

### How It Works

- **On BUY**: The total cost increases by `quantity × price`, and the net quantity increases by `quantity`. The average cost is `total_cost / net_quantity`.
- **On SELL**: The realized profit is `quantity × (sell_price - average_cost)`. The total cost decreases by `quantity × average_cost`, and the net quantity decreases by `quantity`.

### Worked Example

| Step | Action | Net Qty | Total Cost | Avg Cost | Realized PnL |
|---|---|---|---|---|---|
| 1 | BUY 10 @ 100 | 10 | 1,000 | 100 | 0 |
| 2 | BUY 10 @ 110 | 20 | 2,100 | 105 | 0 |
| 3 | SELL 5 @ 120 | 15 | 1,575 | 105 | 75 |

At latest price 125:
- **Unrealized PnL** = (125 − 105) × 15 = **300**
- **Total PnL** = 75 + 300 = **375**

---

## Idempotency

### Strategy

Two layers, so the same `(venue, trade_id)` is counted once **even when sent simultaneously**:

1. **Per-symbol lock + check**: the service first locks the symbol's `positions` row (see below), then looks for an existing `(venue, trade_id)`. Concurrent requests for the same symbol queue behind the lock, so later ones see the committed first trade.
2. **Database `UNIQUE` constraint** on `(venue, trade_id)` as the final arbiter. If the same trade id races in under a *different* symbol (different lock), the losing insert hits the constraint; the transaction is rolled back (position change undone) and it is reported as a duplicate.

### Flow

1. Lock the position row for the symbol.
2. If `(venue, trade_id)` exists: return the existing trade with HTTP 200 and `status: "duplicate_ignored"`. No position changes occur.
3. Otherwise insert the trade. An `IntegrityError` on the constraint is also treated as a duplicate (HTTP 200).

`tests/test_concurrency.py` fires 20 simultaneous identical requests and asserts exactly one `201`, nineteen `200`s, one stored trade and an unchanged position.

---

## Oversell Prevention

### Strategy

The oversell check happens **inside the same database transaction** as the trade insertion and position update, **while holding a lock on the symbol's position row**. This guarantees atomicity — two concurrent SELLs cannot both read the same available quantity.

### Locking

- The position row is created with `INSERT ... ON CONFLICT DO NOTHING` (race-free creation), then read with `SELECT ... FOR UPDATE` (PostgreSQL row lock held until commit/rollback).
- On SQLite the initial INSERT takes the database write lock, and SQLite serializes writers.

### Flow

1. For a `SELL` trade, the service holds the lock and reads the current position.
2. If `position.net_quantity < trade.quantity`, the trade is rejected with HTTP 409 Conflict.
3. The transaction is rolled back, and the position remains completely unchanged.
4. A clear error message is returned: `"Oversell rejected for BTC-USD: available=10, requested=15"`.

`tests/test_concurrency.py` runs five simultaneous SELLs of 4 against a position of 10: exactly two succeed, three get 409, and 2 remains.

---

## Decimal Precision

### Why Not Float?

Floating-point arithmetic introduces rounding errors. For example, `0.1 + 0.2 = 0.30000000000000004` in standard float. In a financial system, these tiny errors accumulate over millions of trades and can lead to material accounting discrepancies.

### Implementation

- All monetary fields (`quantity`, `price`, `total_cost`, `realized_pnl`, etc.) use Python's `decimal.Decimal` type.
- In the database, these fields are stored as `Numeric(20, 8)` — 20 total digits with 8 decimal places.
- Pydantic schemas accept `Decimal` inputs and serialize them back as strings to avoid JSON floating-point issues.

---

## Database

### Default: SQLite

SQLite was chosen as the default database because:
- **Zero setup**: No server installation, no Docker, no credentials.
- **ACID compliant**: SQLite provides full transaction support.
- **Write serialization**: SQLite serializes all writes; combined with the up-front position INSERT, this makes the oversell and idempotency checks race-free (verified by `tests/test_concurrency.py`).

### Optional: PostgreSQL

The application supports PostgreSQL by changing a single environment variable:
```
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/trades
```
No code changes are required. SQLAlchemy's ORM abstraction handles both databases identically. For PostgreSQL, the `UNIQUE` constraint and transaction isolation provide the same atomicity guarantees.

---

## Architecture

The application follows a **three-layer architecture**:

1. **API Layer** (`app/api/`): FastAPI route handlers. Responsible for HTTP concerns (request parsing, status codes, error responses). Each route wraps its logic in a try-except block.
2. **Service Layer** (`app/services/`): Business logic. Trade ingestion, position updates, PnL calculations, and reconciliation. This layer is database-aware but HTTP-unaware.
3. **Data Layer** (`app/models.py`, `app/db.py`): SQLAlchemy ORM models and async session management.

### Error Handling

- **Custom domain exceptions** (`OversellException`, `DuplicateTradeException`, `SymbolNotFoundException`) are raised in the service layer.
- **Global exception handlers** in `app/main.py` map exceptions to HTTP status codes and consistent JSON error responses.
- **Route-level try-except** blocks catch unexpected errors and return 500 with a generic message (avoiding stack trace leaks).
- **Python `logging`** is used throughout (no `print()` statements).

---

## Reconciliation

The reconciliation endpoint compares an external venue's trade statement against our internal records:

1. Load all stored trades for the specified venue.
2. Index both sets of trades by `trade_id`.
3. For each trade in the external statement:
   - If it's not in our DB: mark it as **missing**.
   - If it is in our DB but fields differ: mark it as **mismatched** (with a list of differing fields).
4. For each trade in our DB that's not in the external statement: mark it as **extra**.

The response provides three lists (`missing_trades`, `extra_trades`, `mismatched_trades`) so an operations team can investigate and resolve discrepancies.

---

## Trade-offs & Future Improvements

| Decision | Trade-off | Future Alternative |
|---|---|---|
| Average Cost (not FIFO) | Simpler, but doesn't track individual purchase lots | FIFO with a `buy_lots` table for tax-lot tracking |
| SQLite default | No setup, but single-writer | PostgreSQL for production concurrency |
| In-memory position table | Fast reads, but computed from trades on each update | Event sourcing with snapshots for audit trail |
| Single-trade ingestion | Simple API, but slower for bulk imports | Batch `POST /trades/bulk` endpoint |
| Arrival-order processing | Trades applied in arrival order (standard for real-time REST) | Event sequencer / buffered window for out-of-order timestamps |
| Reconciliation field comparison | Matches on `trade_id`, validates `symbol`, `side`, `qty`, `price` | Configurable timestamp tolerance window (e.g., $\pm 5$s) |
