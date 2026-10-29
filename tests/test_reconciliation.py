"""
Tests for reconciliation.
Verifies detection of missing, extra, and mismatched trades.
"""

import pytest
from decimal import Decimal


@pytest.mark.asyncio
async def test_reconciliation_spec_example(client):
    """
    Assignment's reconciliation example:
      Stored: T1 (10 @ 100), T2 (5 @ 101)
      Venue statement: T1 (10 @ 100), T2 (6 @ 101), T3 (1 @ 99)

    Expected:
      - T2: quantity mismatch (stored=5, statement=6)
      - T3: missing from our records
    """
    # Store T1 and T2
    await client.post("/trades", json={
        "venue": "binance",
        "trade_id": "T1",
        "symbol": "BTC-USD",
        "side": "BUY",
        "quantity": "10",
        "price": "100",
        "timestamp": "2026-10-28T10:00:00Z",
    })
    await client.post("/trades", json={
        "venue": "binance",
        "trade_id": "T2",
        "symbol": "BTC-USD",
        "side": "BUY",
        "quantity": "5",
        "price": "101",
        "timestamp": "2026-10-28T11:00:00Z",
    })

    # Reconcile against venue statement
    response = await client.post("/reconcile", json={
        "venue": "binance",
        "trades": [
            {
                "trade_id": "T1",
                "symbol": "BTC-USD",
                "side": "BUY",
                "quantity": "10",
                "price": "100",
                "timestamp": "2026-10-28T10:00:00Z",
            },
            {
                "trade_id": "T2",
                "symbol": "BTC-USD",
                "side": "BUY",
                "quantity": "6",
                "price": "101",
                "timestamp": "2026-10-28T11:00:00Z",
            },
            {
                "trade_id": "T3",
                "symbol": "BTC-USD",
                "side": "BUY",
                "quantity": "1",
                "price": "99",
                "timestamp": "2026-10-28T12:00:00Z",
            },
        ],
    })

    assert response.status_code == 200
    data = response.json()
    assert data["venue"] == "binance"

    # T3 is missing from our records
    missing_ids = [t["trade_id"] for t in data["missing_trades"]]
    assert "T3" in missing_ids

    # T2 has a quantity mismatch
    mismatch_ids = [t["trade_id"] for t in data["mismatched_trades"]]
    assert "T2" in mismatch_ids

    # Find the T2 mismatch details
    t2_mismatch = next(m for m in data["mismatched_trades"] if m["trade_id"] == "T2")
    assert "quantity" in t2_mismatch["differences"]
    assert Decimal(t2_mismatch["stored"]["quantity"]) == Decimal("5")
    assert Decimal(t2_mismatch["venue_statement"]["quantity"]) == Decimal("6")

    # No extra trades (all our stored trades are in the statement)
    assert len(data["extra_trades"]) == 0


@pytest.mark.asyncio
async def test_reconciliation_extra_trades(client):
    """Trades in our DB but not in the venue statement should be reported as extra."""
    # Store T1 and T2
    await client.post("/trades", json={
        "venue": "coinbase",
        "trade_id": "T1",
        "symbol": "ETH-USD",
        "side": "BUY",
        "quantity": "10",
        "price": "200",
        "timestamp": "2026-10-28T10:00:00Z",
    })
    await client.post("/trades", json={
        "venue": "coinbase",
        "trade_id": "T2",
        "symbol": "ETH-USD",
        "side": "BUY",
        "quantity": "5",
        "price": "210",
        "timestamp": "2026-10-28T11:00:00Z",
    })

    # Venue statement only includes T1 (T2 is missing from statement = extra in our DB)
    response = await client.post("/reconcile", json={
        "venue": "coinbase",
        "trades": [
            {
                "trade_id": "T1",
                "symbol": "ETH-USD",
                "side": "BUY",
                "quantity": "10",
                "price": "200",
                "timestamp": "2026-10-28T10:00:00Z",
            },
        ],
    })

    assert response.status_code == 200
    data = response.json()

    extra_ids = [t["trade_id"] for t in data["extra_trades"]]
    assert "T2" in extra_ids
    assert len(data["missing_trades"]) == 0
