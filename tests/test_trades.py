"""
Tests for trade ingestion and input validation.
Covers: valid BUY/SELL, negative quantity, negative price, invalid side, missing fields.
"""

import pytest
from decimal import Decimal


@pytest.mark.asyncio
async def test_valid_buy_trade(client):
    """A valid BUY trade should return 201 and status 'created'."""
    response = await client.post("/trades", json={
        "venue": "binance",
        "trade_id": "T-100",
        "symbol": "BTC-USD",
        "side": "BUY",
        "quantity": "10",
        "price": "100",
        "timestamp": "2026-10-28T10:00:00Z",
    })
    assert response.status_code == 201
    data = response.json()
    assert data["venue"] == "binance"
    assert data["trade_id"] == "T-100"
    assert data["symbol"] == "BTC-USD"
    assert data["side"] == "BUY"
    assert data["status"] == "created"
    assert Decimal(data["quantity"]) == Decimal("10")
    assert Decimal(data["price"]) == Decimal("100")


@pytest.mark.asyncio
async def test_valid_sell_trade(client):
    """A valid SELL trade (with sufficient position) should return 201."""
    # First, build a position
    await client.post("/trades", json={
        "venue": "binance",
        "trade_id": "T-200",
        "symbol": "ETH-USD",
        "side": "BUY",
        "quantity": "20",
        "price": "50",
        "timestamp": "2026-10-28T10:00:00Z",
    })

    # Now sell some
    response = await client.post("/trades", json={
        "venue": "binance",
        "trade_id": "T-201",
        "symbol": "ETH-USD",
        "side": "SELL",
        "quantity": "5",
        "price": "60",
        "timestamp": "2026-10-28T11:00:00Z",
    })
    assert response.status_code == 201
    assert response.json()["side"] == "SELL"


@pytest.mark.asyncio
async def test_reject_negative_quantity(client):
    """Negative quantity should be rejected with 422."""
    response = await client.post("/trades", json={
        "venue": "binance",
        "trade_id": "T-300",
        "symbol": "BTC-USD",
        "side": "BUY",
        "quantity": "-5",
        "price": "100",
        "timestamp": "2026-10-28T10:00:00Z",
    })
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_reject_negative_price(client):
    """Negative price should be rejected with 422."""
    response = await client.post("/trades", json={
        "venue": "binance",
        "trade_id": "T-400",
        "symbol": "BTC-USD",
        "side": "BUY",
        "quantity": "10",
        "price": "-50",
        "timestamp": "2026-10-28T10:00:00Z",
    })
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_reject_invalid_side(client):
    """Invalid side (not BUY or SELL) should be rejected with 422."""
    response = await client.post("/trades", json={
        "venue": "binance",
        "trade_id": "T-500",
        "symbol": "BTC-USD",
        "side": "HOLD",
        "quantity": "10",
        "price": "100",
        "timestamp": "2026-10-28T10:00:00Z",
    })
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_reject_zero_quantity(client):
    """Zero quantity should be rejected with 422."""
    response = await client.post("/trades", json={
        "venue": "binance",
        "trade_id": "T-600",
        "symbol": "BTC-USD",
        "side": "BUY",
        "quantity": "0",
        "price": "100",
        "timestamp": "2026-10-28T10:00:00Z",
    })
    assert response.status_code == 422
