"""
Tests for position tracking and average cost calculation.
"""

import pytest
from decimal import Decimal


@pytest.mark.asyncio
async def test_single_buy_position(client):
    """After one BUY, position should show correct quantity and cost."""
    await client.post("/trades", json={
        "venue": "binance",
        "trade_id": "T-1",
        "symbol": "BTC-USD",
        "side": "BUY",
        "quantity": "10",
        "price": "100",
        "timestamp": "2026-10-28T10:00:00Z",
    })

    response = await client.get("/positions/BTC-USD")
    assert response.status_code == 200
    data = response.json()
    assert Decimal(data["net_quantity"]) == Decimal("10")
    assert Decimal(data["average_cost"]) == Decimal("100")
    assert Decimal(data["total_cost"]) == Decimal("1000")


@pytest.mark.asyncio
async def test_multi_buy_average_cost(client):
    """After two BUYs at different prices, average cost should be weighted."""
    # BUY 10 @ 100
    await client.post("/trades", json={
        "venue": "binance",
        "trade_id": "T-1",
        "symbol": "BTC-USD",
        "side": "BUY",
        "quantity": "10",
        "price": "100",
        "timestamp": "2026-10-28T10:00:00Z",
    })
    # BUY 10 @ 110
    await client.post("/trades", json={
        "venue": "binance",
        "trade_id": "T-2",
        "symbol": "BTC-USD",
        "side": "BUY",
        "quantity": "10",
        "price": "110",
        "timestamp": "2026-10-28T11:00:00Z",
    })

    response = await client.get("/positions/BTC-USD")
    data = response.json()
    assert Decimal(data["net_quantity"]) == Decimal("20")
    assert Decimal(data["total_cost"]) == Decimal("2100")
    # Average cost = 2100 / 20 = 105
    assert Decimal(data["average_cost"]) == Decimal("105")


@pytest.mark.asyncio
async def test_buy_then_sell_position(client):
    """After BUY + partial SELL, position should show remaining quantity."""
    # BUY 10 @ 100
    await client.post("/trades", json={
        "venue": "binance",
        "trade_id": "T-1",
        "symbol": "BTC-USD",
        "side": "BUY",
        "quantity": "10",
        "price": "100",
        "timestamp": "2026-10-28T10:00:00Z",
    })
    # SELL 3 @ 120
    await client.post("/trades", json={
        "venue": "binance",
        "trade_id": "T-2",
        "symbol": "BTC-USD",
        "side": "SELL",
        "quantity": "3",
        "price": "120",
        "timestamp": "2026-10-28T11:00:00Z",
    })

    response = await client.get("/positions/BTC-USD")
    data = response.json()
    assert Decimal(data["net_quantity"]) == Decimal("7")
    # Average cost stays 100 (only one buy lot)
    assert Decimal(data["average_cost"]) == Decimal("100")
    # Realized PnL = 3 * (120 - 100) = 60
    assert Decimal(data["realized_pnl"]) == Decimal("60")


@pytest.mark.asyncio
async def test_position_not_found(client):
    """Requesting a position for a non-existent symbol returns 404."""
    response = await client.get("/positions/DOGE-USD")
    assert response.status_code == 404
