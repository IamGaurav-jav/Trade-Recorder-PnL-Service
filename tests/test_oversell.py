"""
Tests for oversell prevention.
Selling more than you own must be rejected with 409, position unchanged.
"""

import pytest
from decimal import Decimal


@pytest.mark.asyncio
async def test_oversell_rejected(client):
    """Selling 15 when position is 10 should return 409."""
    # Build position of 10
    await client.post("/trades", json={
        "venue": "binance",
        "trade_id": "T-1",
        "symbol": "BTC-USD",
        "side": "BUY",
        "quantity": "10",
        "price": "100",
        "timestamp": "2026-10-28T10:00:00Z",
    })

    # Try to sell 15 — should fail
    response = await client.post("/trades", json={
        "venue": "binance",
        "trade_id": "T-2",
        "symbol": "BTC-USD",
        "side": "SELL",
        "quantity": "15",
        "price": "120",
        "timestamp": "2026-10-28T11:00:00Z",
    })
    assert response.status_code == 409
    data = response.json()
    assert "oversell" in data["error"].lower()


@pytest.mark.asyncio
async def test_oversell_position_unchanged(client):
    """After a rejected oversell, the position must remain unchanged."""
    # Build position of 10
    await client.post("/trades", json={
        "venue": "binance",
        "trade_id": "T-1",
        "symbol": "BTC-USD",
        "side": "BUY",
        "quantity": "10",
        "price": "100",
        "timestamp": "2026-10-28T10:00:00Z",
    })

    # Attempt oversell (should fail)
    await client.post("/trades", json={
        "venue": "binance",
        "trade_id": "T-2",
        "symbol": "BTC-USD",
        "side": "SELL",
        "quantity": "15",
        "price": "120",
        "timestamp": "2026-10-28T11:00:00Z",
    })

    # Position should still be 10
    response = await client.get("/positions/BTC-USD")
    data = response.json()
    assert Decimal(data["net_quantity"]) == Decimal("10")
    assert Decimal(data["total_cost"]) == Decimal("1000")


@pytest.mark.asyncio
async def test_sell_exact_position(client):
    """Selling exactly the full position should succeed and set qty to 0."""
    # Build position of 10
    await client.post("/trades", json={
        "venue": "binance",
        "trade_id": "T-1",
        "symbol": "BTC-USD",
        "side": "BUY",
        "quantity": "10",
        "price": "100",
        "timestamp": "2026-10-28T10:00:00Z",
    })

    # Sell exactly 10
    response = await client.post("/trades", json={
        "venue": "binance",
        "trade_id": "T-2",
        "symbol": "BTC-USD",
        "side": "SELL",
        "quantity": "10",
        "price": "120",
        "timestamp": "2026-10-28T11:00:00Z",
    })
    assert response.status_code == 201

    # Position should be 0
    pos = await client.get("/positions/BTC-USD")
    data = pos.json()
    assert Decimal(data["net_quantity"]) == Decimal("0")


@pytest.mark.asyncio
async def test_sell_with_no_position(client):
    """Selling when no position exists should return 409."""
    response = await client.post("/trades", json={
        "venue": "binance",
        "trade_id": "T-1",
        "symbol": "DOGE-USD",
        "side": "SELL",
        "quantity": "5",
        "price": "50",
        "timestamp": "2026-10-28T10:00:00Z",
    })
    assert response.status_code == 409
