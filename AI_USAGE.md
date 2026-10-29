# AI Usage Disclosure

This document describes how AI tools were used during the development of this project.

---

## Tools Used

- **Antigravity (DeepMind)**: Used for architecture design, end-to-end service implementation, initial test matrix, and core documentation.
- **GitHub Copilot**: Used for secondary code review, identifying the simultaneous-duplicate race condition, and generating the dedicated concurrency test suite (`test_concurrency.py`).

## How AI Was Used

### 1. Planning & Architecture
- AI assisted in designing the three-layer architecture (API → Service → Data).
- AI helped evaluate the trade-offs between **Average Cost** and **FIFO** cost-basis methods.
- AI proposed the database schema and constraint design (e.g., `UNIQUE(venue, trade_id)` for idempotency).

### 2. Code Generation
- AI generated the initial scaffolding for:
  - FastAPI route handlers with error handling patterns
  - SQLAlchemy async models with `Decimal`/`Numeric` field types
  - Pydantic v2 schemas with field validators
  - Service layer business logic (trade ingestion, PnL calculation, reconciliation)
- All generated code was reviewed and tested before inclusion.

### 3. Test Design
- AI helped design the test matrix covering all six assignment requirements.
- AI generated test cases including the exact worked examples from the assignment specification.
- AI identified edge cases (zero-quantity sells, missing positions, concurrent duplicates).

### 4. Documentation
- AI assisted in drafting `README.md`, `DESIGN.md`, and this `AI_USAGE.md`.
- Content was reviewed and edited for accuracy.

## What Was Manually Verified

- All 25 automated tests pass (`pytest -v`), including concurrency tests that fire simultaneous duplicate trades, BUYs, and SELLs.
- A concurrency bug found during final review (simultaneous duplicate trades returned 500) was reproduced with a script, then fixed with a per-symbol position lock and covered by tests.
- The worked example produces the exact target numbers: Quantity=15, Average Cost=105, Realized PnL=75, Unrealized PnL=300.
- Oversell rejection correctly returns 409 and leaves the position unchanged.
- Idempotency correctly returns 200 on duplicate submissions.
- Reconciliation correctly identifies missing, extra, and mismatched trades.
